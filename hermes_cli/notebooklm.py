"""NotebookLM / NLM Lab CLI helpers."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix fallback
    fcntl = None


class NotebookLookupUnavailable(RuntimeError):
    """Notebook list/lookup cannot run because NotebookLM CLI is unavailable."""


class NotebookCommandError(RuntimeError):
    """NotebookLM command failed or returned unusable output."""


_STATEFUL_NOTEBOOK_CONTEXT_LOCK = threading.Lock()


@contextmanager
def _stateful_notebook_context():
    with _STATEFUL_NOTEBOOK_CONTEXT_LOCK:
        if fcntl is None:
            yield
            return

        lock_path = _notebooklm_home() / ".stateful-cli.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)



def _notebooklm_home() -> Path:
    raw = os.getenv("NOTEBOOKLM_HOME", "~/.notebooklm")
    return Path(raw).expanduser()



def _candidate_storage_state_paths(profile: str = "default") -> list[Path]:
    home = _notebooklm_home()
    return [
        home / "profiles" / profile / "storage_state.json",
        home / "storage_state.json",
    ]



def _storage_state_path(profile: str = "default") -> Path:
    candidates = _candidate_storage_state_paths(profile)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]



def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None



def _chromium_installed() -> bool:
    browser_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    candidates = []
    if browser_root:
        candidates.append(Path(browser_root).expanduser())
    candidates.append(Path.home() / ".cache" / "ms-playwright")

    for root in candidates:
        try:
            if root.exists() and any(child.name.startswith("chromium") for child in root.iterdir()):
                return True
        except OSError:
            continue
    return False



def collect_status(profile: str = "default") -> dict:
    notebooklm_installed = _module_available("notebooklm")
    playwright_installed = _module_available("playwright")
    chromium_installed = _chromium_installed()
    storage_state = _storage_state_path(profile)
    logged_in = any(path.exists() for path in _candidate_storage_state_paths(profile))

    if not notebooklm_installed:
        overall = "needs-install"
    elif not logged_in:
        overall = "needs-login"
    elif playwright_installed and not chromium_installed:
        overall = "needs-browser"
    else:
        overall = "ready"

    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "profile": profile,
        "notebooklm_home": str(_notebooklm_home()),
        "storage_state_path": str(storage_state),
        "notebooklm_installed": notebooklm_installed,
        "playwright_installed": playwright_installed,
        "chromium_installed": chromium_installed,
        "logged_in": logged_in,
        "status": overall,
    }



def _print_status(status: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(status, ensure_ascii=False))
        return

    print(f"profile: {status['profile']}")
    print(f"python: {status['python_version']} ({status['python_executable']})")
    print(f"notebooklm_home: {status['notebooklm_home']}")
    print(f"storage_state_path: {status['storage_state_path']}")
    print(f"notebooklm_installed: {status['notebooklm_installed']}")
    print(f"playwright_installed: {status['playwright_installed']}")
    print(f"chromium_installed: {status['chromium_installed']}")
    print(f"logged_in: {status['logged_in']}")
    print(f"status: {status['status']}")



def _run_install(*, browser: bool = False) -> None:
    package = "notebooklm-py[browser]" if browser else "notebooklm-py"
    subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
    if browser:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)



def _run_login(*, profile: str = "default") -> None:
    env = os.environ.copy()
    env["NOTEBOOKLM_PROFILE"] = profile
    subprocess.run(
        [sys.executable, "-m", "notebooklm.notebooklm_cli", "login"],
        check=True,
        env=env,
    )



def _command_candidates(args: list[str], *, profile: str = "default") -> list[list[str]]:
    candidates = [
        [sys.executable, "-m", "notebooklm.notebooklm_cli", "--profile", profile, *args],
        [sys.executable, "-m", "notebooklm.notebooklm_cli", *args],
    ]
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique



def _looks_like_missing_option_error(text: str, option: str) -> bool:
    folded = text.casefold()
    return option.casefold() in folded and (
        "no such option" in folded
        or "unrecognized arguments" in folded
        or "got unexpected extra argument" in folded
    )



def _failure_message(stdout: str, stderr: str) -> str:
    for text in (stderr, stdout):
        cleaned = (text or "").strip()
        if not cleaned:
            continue
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return cleaned
        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("error") or cleaned)
        return cleaned
    return "NotebookLM command failed"



def _run_cli_capture(args: list[str], *, profile: str = "default") -> str:
    if not _module_available("notebooklm"):
        raise NotebookLookupUnavailable("NotebookLM is not installed")

    env = os.environ.copy()
    env["NOTEBOOKLM_PROFILE"] = profile
    failures: list[str] = []

    for idx, cmd in enumerate(_command_candidates(args, profile=profile)):
        result = subprocess.run(
            cmd,
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        if getattr(result, "returncode", 1) == 0:
            return stdout

        if idx == 0 and _looks_like_missing_option_error(f"{stdout}\n{stderr}", "--profile"):
            continue

        failures.append(_failure_message(stdout, stderr))

    joined = " | ".join(part for part in failures if part)
    raise NotebookCommandError(joined or "NotebookLM command failed")



def _run_cli_json(args: list[str], *, profile: str = "default") -> dict[str, Any] | list[Any]:
    stdout = _run_cli_capture(args, profile=profile)
    try:
        payload = json.loads((stdout or "").strip() or "{}")
    except json.JSONDecodeError as exc:
        raise NotebookCommandError("NotebookLM command returned invalid JSON") from exc
    if not isinstance(payload, (dict, list)):
        raise NotebookCommandError("NotebookLM command returned unsupported JSON payload")
    return payload



def list_notebooks(profile: str = "default") -> list[dict]:
    payload = _run_cli_json(["list", "--json"], profile=profile)
    if isinstance(payload, list):
        notebooks = payload
    else:
        notebooks = payload.get("notebooks")
    if not isinstance(notebooks, list):
        raise NotebookLookupUnavailable("NotebookLM list output did not include a notebooks array")
    return notebooks



def resolve_notebook_reference(notebook: str, *, profile: str = "default") -> dict:
    notebooks = list_notebooks(profile)

    exact_id = [nb for nb in notebooks if str(nb.get("id", "")) == notebook]
    if len(exact_id) == 1:
        return exact_id[0]

    exact = [nb for nb in notebooks if nb.get("title") == notebook]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"Notebook title is ambiguous: {notebook}")

    folded = [nb for nb in notebooks if str(nb.get("title", "")).casefold() == notebook.casefold()]
    if len(folded) == 1:
        return folded[0]
    if len(folded) > 1:
        raise ValueError(f"Notebook title is ambiguous: {notebook}")

    available = ", ".join(nb.get("title", "") for nb in notebooks[:5])
    raise ValueError(f"Notebook not found: {notebook}. Available: {available}")



def get_notebook_metadata(*, notebook_id: str | None = None, profile: str = "default") -> dict:
    args = ["metadata", "--json"]
    if notebook_id:
        args.extend(["--notebook", notebook_id])

    try:
        payload = _run_cli_json(args, profile=profile)
    except NotebookCommandError as exc:
        if notebook_id and _looks_like_missing_option_error(str(exc), "--notebook"):
            with _stateful_notebook_context():
                _run_cli_capture(["use", notebook_id], profile=profile)
                payload = _run_cli_json(["metadata", "--json"], profile=profile)
        else:
            raise

    if not isinstance(payload, dict):
        raise NotebookCommandError("NotebookLM metadata output did not return an object")
    return payload



def list_sources(*, notebook_id: str, profile: str = "default") -> list[dict]:
    try:
        payload = _run_cli_json(["source", "list", "--notebook", notebook_id, "--json"], profile=profile)
    except NotebookCommandError as exc:
        if _looks_like_missing_option_error(str(exc), "--notebook"):
            with _stateful_notebook_context():
                _run_cli_capture(["use", notebook_id], profile=profile)
                payload = _run_cli_json(["source", "list", "--json"], profile=profile)
        else:
            raise

    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        raise NotebookCommandError("NotebookLM source list output did not include a sources array")
    return sources



def add_source(*, notebook_id: str, source_type: str, content: str, profile: str = "default") -> dict:
    if source_type not in {"url", "text"}:
        raise ValueError("source_type must be one of: url, text")
    if not content.strip():
        raise ValueError("content must not be empty")
    if source_type == "url" and content.startswith("-"):
        raise ValueError("url content must not start with '-'")

    temp_path = None
    content_arg = content
    if source_type == "text":
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            temp_path = temp_file.name
            content_arg = temp_path

    try:
        args = ["source", "add", content_arg, "--notebook", notebook_id, "--json"]
        try:
            payload = _run_cli_json(args, profile=profile)
        except NotebookCommandError as exc:
            if _looks_like_missing_option_error(str(exc), "--notebook"):
                fallback_args = ["source", "add", content_arg, "--json"]
                with _stateful_notebook_context():
                    _run_cli_capture(["use", notebook_id], profile=profile)
                    payload = _run_cli_json(fallback_args, profile=profile)
            else:
                raise
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    if not isinstance(payload, dict):
        raise NotebookCommandError("NotebookLM source add output did not return an object")
    return payload



def ask_notebook(question: str, *, notebook_id: str, profile: str = "default") -> dict:
    try:
        payload = _run_cli_json(
            ["ask", question, "--notebook", notebook_id, "--json"],
            profile=profile,
        )
    except NotebookCommandError as exc:
        if _looks_like_missing_option_error(str(exc), "--notebook"):
            with _stateful_notebook_context():
                _run_cli_capture(["use", notebook_id], profile=profile)
                payload = _run_cli_json(["ask", question, "--json"], profile=profile)
        else:
            raise

    if not isinstance(payload, dict):
        raise NotebookCommandError("NotebookLM ask output did not return an object")
    return payload



def notebooklm_command(args) -> None:
    subcmd = getattr(args, "notebooklm_command", None)
    profile = getattr(args, "profile", "default")

    if subcmd in (None, "doctor", "status"):
        _print_status(collect_status(profile), as_json=getattr(args, "json", False))
        return

    if subcmd == "install":
        _run_install(browser=getattr(args, "browser", False))
        print(json.dumps(collect_status(profile), ensure_ascii=False))
        return

    if subcmd == "login":
        _run_login(profile=profile)
        print(f"NotebookLM login completed for profile: {profile}")
        return

    raise SystemExit(f"Unknown notebooklm command: {subcmd}")
