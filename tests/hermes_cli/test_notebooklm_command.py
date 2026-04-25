import json
import sys
from argparse import Namespace
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _isolate_notebooklm_home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_HOME", str(tmp_path / ".notebooklm"))



def _args(command, **overrides):
    defaults = {
        "notebooklm_command": command,
        "json": False,
        "browser": False,
        "profile": "default",
    }
    defaults.update(overrides)
    return Namespace(**defaults)



def test_collect_status_reports_needs_install(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "_module_available",
        lambda name: False,
    )
    monkeypatch.setattr(notebooklm_mod, "_chromium_installed", lambda: False)

    status = notebooklm_mod.collect_status("default")

    assert status["notebooklm_installed"] is False
    assert status["logged_in"] is False
    assert status["status"] == "needs-install"



def test_collect_status_reports_needs_login_when_profile_has_no_storage(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "_module_available",
        lambda name: name == "notebooklm",
    )
    monkeypatch.setattr(notebooklm_mod, "_chromium_installed", lambda: False)

    status = notebooklm_mod.collect_status("default")

    assert status["notebooklm_installed"] is True
    assert status["logged_in"] is False
    assert status["status"] == "needs-login"



def test_collect_status_reports_ready_when_everything_exists(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    storage_path = notebooklm_mod._storage_state_path("research")
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(notebooklm_mod, "_module_available", lambda name: True)
    monkeypatch.setattr(notebooklm_mod, "_chromium_installed", lambda: True)

    status = notebooklm_mod.collect_status("research")

    assert status["playwright_installed"] is True
    assert status["chromium_installed"] is True
    assert status["logged_in"] is True
    assert status["status"] == "ready"



def test_doctor_json_prints_machine_readable_status(monkeypatch, capsys):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "collect_status",
        lambda profile: {"profile": profile, "status": "needs-login", "logged_in": False},
    )

    notebooklm_mod.notebooklm_command(_args("doctor", json=True))
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert payload == {
        "profile": "default",
        "status": "needs-login",
        "logged_in": False,
    }



def test_install_with_browser_invokes_expected_commands(monkeypatch, capsys):
    import hermes_cli.notebooklm as notebooklm_mod

    calls = []

    def fake_run(cmd, check, env=None):
        calls.append({"cmd": cmd, "env": env})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(notebooklm_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        notebooklm_mod,
        "collect_status",
        lambda profile: {"profile": profile, "status": "ready"},
    )

    notebooklm_mod.notebooklm_command(_args("install", browser=True))
    out = capsys.readouterr().out

    assert calls[0]["cmd"] == [sys.executable, "-m", "pip", "install", "notebooklm-py[browser]"]
    assert calls[1]["cmd"] == [sys.executable, "-m", "playwright", "install", "chromium"]
    assert '"status": "ready"' in out



def test_login_uses_requested_profile(monkeypatch, capsys):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}

    def fake_run(cmd, check, env=None):
        recorded["cmd"] = cmd
        recorded["env"] = env
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(notebooklm_mod.subprocess, "run", fake_run)

    notebooklm_mod.notebooklm_command(_args("login", profile="nlm-lab"))
    out = capsys.readouterr().out

    assert recorded["cmd"] == [sys.executable, "-m", "notebooklm.notebooklm_cli", "login"]
    assert recorded["env"]["NOTEBOOKLM_PROFILE"] == "nlm-lab"
    assert "nlm-lab" in out



def test_list_notebooks_parses_json_output(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    payload = {
        "notebooks": [
            {"id": "nb-1", "title": "NLM Lab / 제국 운영"},
            {"id": "nb-2", "title": "Other"},
        ]
    }

    monkeypatch.setattr(notebooklm_mod, "_module_available", lambda name: True)

    def fake_run(cmd, check, env=None, capture_output=None, text=None):
        assert cmd == [
            sys.executable,
            "-m",
            "notebooklm.notebooklm_cli",
            "--profile",
            "default",
            "list",
            "--json",
        ]
        return SimpleNamespace(stdout=json.dumps(payload), returncode=0)

    monkeypatch.setattr(notebooklm_mod.subprocess, "run", fake_run)

    notebooks = notebooklm_mod.list_notebooks("default")

    assert notebooks == payload["notebooks"]



def test_resolve_notebook_reference_matches_by_title(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "list_notebooks",
        lambda profile: [
            {"id": "nb-1", "title": "NLM Lab / 제국 운영"},
            {"id": "nb-2", "title": "Other"},
        ],
    )

    notebook = notebooklm_mod.resolve_notebook_reference("NLM Lab / 제국 운영", profile="default")

    assert notebook == {"id": "nb-1", "title": "NLM Lab / 제국 운영"}



def test_collect_status_uses_top_level_storage_state_fallback(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    storage_path = notebooklm_mod._notebooklm_home() / "storage_state.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        notebooklm_mod,
        "_module_available",
        lambda name: name in {"notebooklm", "playwright"},
    )
    monkeypatch.setattr(notebooklm_mod, "_chromium_installed", lambda: True)

    status = notebooklm_mod.collect_status("default")

    assert status["logged_in"] is True
    assert status["storage_state_path"] == str(storage_path)
    assert status["status"] == "ready"



def test_list_notebooks_falls_back_when_profile_flag_is_unsupported(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    payload = {"notebooks": [{"id": "nb-1", "title": "NLM Lab / 제국 운영"}]}
    calls = []

    monkeypatch.setattr(notebooklm_mod, "_module_available", lambda name: True)

    def fake_run(cmd, check, env=None, capture_output=None, text=None):
        calls.append(cmd)
        if "--profile" in cmd:
            return SimpleNamespace(returncode=2, stdout="", stderr="Error: No such option: --profile")
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(notebooklm_mod.subprocess, "run", fake_run)

    notebooks = notebooklm_mod.list_notebooks("default")

    assert notebooks == payload["notebooks"]
    assert calls == [
        [
            sys.executable,
            "-m",
            "notebooklm.notebooklm_cli",
            "--profile",
            "default",
            "list",
            "--json",
        ],
        [
            sys.executable,
            "-m",
            "notebooklm.notebooklm_cli",
            "list",
            "--json",
        ],
    ]



def test_ask_notebook_falls_back_to_use_when_notebook_flag_is_unsupported(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    calls = []

    class RecordingLock:
        def __enter__(self):
            calls.append(("lock", "enter"))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("lock", "exit"))
            return False

    def fake_run_cli_json(args, *, profile="default"):
        calls.append(("json", args, profile))
        if args == ["ask", "이번 주 변경점 뭐야?", "--notebook", "nb-478", "--json"]:
            raise notebooklm_mod.NotebookCommandError("Error: No such option: --notebook")
        if args == ["ask", "이번 주 변경점 뭐야?", "--json"]:
            return {"answer": "요약 답변", "conversation_id": "conv-1"}
        raise AssertionError(f"unexpected args: {args}")

    def fake_run_cli_capture(args, *, profile="default"):
        calls.append(("capture", args, profile))
        assert args == ["use", "nb-478"]
        return ""

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(notebooklm_mod, "_run_cli_capture", fake_run_cli_capture)
    monkeypatch.setattr(notebooklm_mod, "_STATEFUL_NOTEBOOK_CONTEXT_LOCK", RecordingLock())

    payload = notebooklm_mod.ask_notebook("이번 주 변경점 뭐야?", notebook_id="nb-478")

    assert payload == {"answer": "요약 답변", "conversation_id": "conv-1"}
    assert calls == [
        ("json", ["ask", "이번 주 변경점 뭐야?", "--notebook", "nb-478", "--json"], "default"),
        ("lock", "enter"),
        ("capture", ["use", "nb-478"], "default"),
        ("json", ["ask", "이번 주 변경점 뭐야?", "--json"], "default"),
        ("lock", "exit"),
    ]



def test_get_notebook_metadata_parses_json(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        return {"id": "nb-478", "title": "NLM Lab / 제국 운영"}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    payload = notebooklm_mod.get_notebook_metadata(notebook_id="nb-478")

    assert recorded == {
        "args": ["metadata", "--json", "--notebook", "nb-478"],
        "profile": "default",
    }
    assert payload == {"id": "nb-478", "title": "NLM Lab / 제국 운영"}



def test_get_notebook_metadata_falls_back_to_use_when_notebook_flag_is_unsupported(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    calls = []

    class RecordingLock:
        def __enter__(self):
            calls.append(("lock", "enter"))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("lock", "exit"))
            return False

    def fake_run_cli_json(args, *, profile="default"):
        calls.append(("json", args, profile))
        if args == ["metadata", "--json", "--notebook", "nb-478"]:
            raise notebooklm_mod.NotebookCommandError("Error: No such option: --notebook")
        if args == ["metadata", "--json"]:
            return {"id": "nb-478", "title": "NLM Lab / 제국 운영"}
        raise AssertionError(f"unexpected args: {args}")

    def fake_run_cli_capture(args, *, profile="default"):
        calls.append(("capture", args, profile))
        assert args == ["use", "nb-478"]
        return ""

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(notebooklm_mod, "_run_cli_capture", fake_run_cli_capture)
    monkeypatch.setattr(notebooklm_mod, "_STATEFUL_NOTEBOOK_CONTEXT_LOCK", RecordingLock())

    payload = notebooklm_mod.get_notebook_metadata(notebook_id="nb-478")

    assert payload == {"id": "nb-478", "title": "NLM Lab / 제국 운영"}
    assert calls == [
        ("json", ["metadata", "--json", "--notebook", "nb-478"], "default"),
        ("lock", "enter"),
        ("capture", ["use", "nb-478"], "default"),
        ("json", ["metadata", "--json"], "default"),
        ("lock", "exit"),
    ]



def test_list_sources_returns_array(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        return {"sources": [{"id": "src-1", "title": "RFC"}]}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    sources = notebooklm_mod.list_sources(notebook_id="nb-478")

    assert recorded == {
        "args": ["source", "list", "--notebook", "nb-478", "--json"],
        "profile": "default",
    }
    assert sources == [{"id": "src-1", "title": "RFC"}]



def test_list_sources_falls_back_to_use_when_notebook_flag_is_unsupported(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    calls = []

    class RecordingLock:
        def __enter__(self):
            calls.append(("lock", "enter"))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("lock", "exit"))
            return False

    def fake_run_cli_json(args, *, profile="default"):
        calls.append(("json", args, profile))
        if args == ["source", "list", "--notebook", "nb-478", "--json"]:
            raise notebooklm_mod.NotebookCommandError("Error: No such option: --notebook")
        if args == ["source", "list", "--json"]:
            return {"sources": [{"id": "src-1", "title": "RFC"}]}
        raise AssertionError(f"unexpected args: {args}")

    def fake_run_cli_capture(args, *, profile="default"):
        calls.append(("capture", args, profile))
        assert args == ["use", "nb-478"]
        return ""

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(notebooklm_mod, "_run_cli_capture", fake_run_cli_capture)
    monkeypatch.setattr(notebooklm_mod, "_STATEFUL_NOTEBOOK_CONTEXT_LOCK", RecordingLock())

    sources = notebooklm_mod.list_sources(notebook_id="nb-478")

    assert sources == [{"id": "src-1", "title": "RFC"}]
    assert calls == [
        ("json", ["source", "list", "--notebook", "nb-478", "--json"], "default"),
        ("lock", "enter"),
        ("capture", ["use", "nb-478"], "default"),
        ("json", ["source", "list", "--json"], "default"),
        ("lock", "exit"),
    ]



def test_add_source_url_builds_expected_command(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        return {"source": {"id": "src-1"}}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    payload = notebooklm_mod.add_source(
        notebook_id="nb-478",
        source_type="url",
        content="https://example.com",
    )

    assert recorded == {
        "args": ["source", "add", "https://example.com", "--notebook", "nb-478", "--json"],
        "profile": "default",
    }
    assert payload == {"source": {"id": "src-1"}}



def test_add_source_falls_back_to_use_when_notebook_flag_is_unsupported(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    calls = []

    class RecordingLock:
        def __enter__(self):
            calls.append(("lock", "enter"))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("lock", "exit"))
            return False

    def fake_run_cli_json(args, *, profile="default"):
        calls.append(("json", args, profile))
        if args == ["source", "add", "https://example.com", "--notebook", "nb-478", "--json"]:
            raise notebooklm_mod.NotebookCommandError("Error: No such option: --notebook")
        if args == ["source", "add", "https://example.com", "--json"]:
            return {"source": {"id": "src-1"}}
        raise AssertionError(f"unexpected args: {args}")

    def fake_run_cli_capture(args, *, profile="default"):
        calls.append(("capture", args, profile))
        assert args == ["use", "nb-478"]
        return ""

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)
    monkeypatch.setattr(notebooklm_mod, "_run_cli_capture", fake_run_cli_capture)
    monkeypatch.setattr(notebooklm_mod, "_STATEFUL_NOTEBOOK_CONTEXT_LOCK", RecordingLock())

    payload = notebooklm_mod.add_source(
        notebook_id="nb-478",
        source_type="url",
        content="https://example.com",
    )

    assert payload == {"source": {"id": "src-1"}}
    assert calls == [
        ("json", ["source", "add", "https://example.com", "--notebook", "nb-478", "--json"], "default"),
        ("lock", "enter"),
        ("capture", ["use", "nb-478"], "default"),
        ("json", ["source", "add", "https://example.com", "--json"], "default"),
        ("lock", "exit"),
    ]



def test_add_source_rejects_content_starting_with_dash(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "_run_cli_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run cli")),
    )

    with pytest.raises(ValueError, match="url content must not start with '-'"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="url",
            content="-sneaky",
        )



def test_add_source_text_writes_temp_file(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}
    temp_path = tmp_path / "source.txt"

    class FakeTempFile:
        name = str(temp_path)

        def write(self, text):
            temp_path.write_text(text, encoding="utf-8")

        def flush(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(notebooklm_mod.tempfile, "NamedTemporaryFile", lambda *args, **kwargs: FakeTempFile())

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        assert temp_path.exists() is True
        return {"source": {"id": "src-1"}}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    payload = notebooklm_mod.add_source(
        notebook_id="nb-478",
        source_type="text",
        content="hello notebooklm",
    )

    assert recorded == {
        "args": ["source", "add", str(temp_path), "--notebook", "nb-478", "--json"],
        "profile": "default",
    }
    assert payload == {"source": {"id": "src-1"}}
    assert temp_path.exists() is False



def test_add_source_rejects_whitespace_only_content(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "_run_cli_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run cli")),
    )

    with pytest.raises(ValueError, match="content must not be empty"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="text",
            content="   ",
        )



def test_add_source_file_builds_expected_command(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"%PDF-test")
    monkeypatch.chdir(tmp_path)

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        return {"source": {"id": "src-1"}}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    payload = notebooklm_mod.add_source(
        notebook_id="nb-478",
        source_type="file",
        content=str(file_path),
    )

    assert recorded == {
        "args": [
            "source",
            "add",
            str(file_path.resolve()),
            "--type",
            "file",
            "--notebook",
            "nb-478",
            "--json",
        ],
        "profile": "default",
    }
    assert payload == {"source": {"id": "src-1"}}



def test_add_source_file_includes_mime_type_when_provided(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    recorded = {}
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"%PDF-test")
    monkeypatch.chdir(tmp_path)

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        return {"source": {"id": "src-1"}}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    notebooklm_mod.add_source(
        notebook_id="nb-478",
        source_type="file",
        content=str(file_path),
        mime_type="application/pdf",
    )

    assert recorded["args"] == [
        "source",
        "add",
        str(file_path.resolve()),
        "--type",
        "file",
        "--notebook",
        "nb-478",
        "--mime-type",
        "application/pdf",
        "--json",
    ]



def test_add_source_rejects_mime_type_for_non_file_sources(monkeypatch):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.setattr(
        notebooklm_mod,
        "_run_cli_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run cli")),
    )

    with pytest.raises(ValueError, match="mime_type is only supported for file sources"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="url",
            content="https://example.com",
            mime_type="application/pdf",
        )



def test_add_source_file_rejects_missing_local_file(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="existing local file"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="file",
            content=str(tmp_path / "missing.pdf"),
        )



def test_add_source_file_rejects_directory(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    directory_path = tmp_path / "docs"
    directory_path.mkdir()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="existing local file"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="file",
            content=str(directory_path),
        )



def test_add_source_file_rejects_broken_symlink(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod

    broken_link = tmp_path / "broken.pdf"
    broken_link.symlink_to(tmp_path / "missing-target.pdf")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="existing local file"):
        notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="file",
            content=str(broken_link),
        )



def test_add_source_file_rejects_outside_allowed_roots_for_gateway_session(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod
    from gateway.session_context import clear_session_vars, set_session_vars

    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    outside_path = tmp_path / "outside.pdf"
    outside_path.write_bytes(b"%PDF-outside")

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        thread_id="478",
        session_key="sess-1",
    )
    try:
        with pytest.raises(ValueError, match="allowed roots"):
            notebooklm_mod.add_source(
                notebook_id="nb-478",
                source_type="file",
                content=str(outside_path),
            )
    finally:
        clear_session_vars(tokens)



def test_add_source_file_accepts_cached_document_for_gateway_session(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod
    from gateway.session_context import clear_session_vars, set_session_vars

    recorded = {}
    hermes_home = tmp_path / ".hermes"
    cache_dir = hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_file = cache_dir / "doc_123456_report.pdf"
    cached_file.write_bytes(b"%PDF-cache")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    def fake_run_cli_json(args, *, profile="default"):
        recorded["args"] = args
        recorded["profile"] = profile
        return {"source": {"id": "src-1"}}

    monkeypatch.setattr(notebooklm_mod, "_run_cli_json", fake_run_cli_json)

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        thread_id="478",
        session_key="sess-1",
    )
    try:
        payload = notebooklm_mod.add_source(
            notebook_id="nb-478",
            source_type="file",
            content=str(cached_file),
        )
    finally:
        clear_session_vars(tokens)

    assert recorded == {
        "args": [
            "source",
            "add",
            str(cached_file.resolve()),
            "--type",
            "file",
            "--notebook",
            "nb-478",
            "--json",
        ],
        "profile": "default",
    }
    assert payload == {"source": {"id": "src-1"}}



def test_add_source_file_rejects_symlink_escape_for_gateway_session(monkeypatch, tmp_path):
    import hermes_cli.notebooklm as notebooklm_mod
    from gateway.session_context import clear_session_vars, set_session_vars

    hermes_home = tmp_path / ".hermes"
    cache_dir = hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    outside_path = tmp_path / "outside.pdf"
    outside_path.write_bytes(b"%PDF-outside")
    link_path = cache_dir / "doc_link.pdf"
    link_path.symlink_to(outside_path)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        thread_id="478",
        session_key="sess-1",
    )
    try:
        with pytest.raises(ValueError, match="allowed roots"):
            notebooklm_mod.add_source(
                notebook_id="nb-478",
                source_type="file",
                content=str(link_path),
            )
    finally:
        clear_session_vars(tokens)



def test_add_source_file_rejects_hard_link_in_gateway_cache(monkeypatch, tmp_path):
    import os
    import hermes_cli.notebooklm as notebooklm_mod
    from gateway.session_context import clear_session_vars, set_session_vars

    hermes_home = tmp_path / ".hermes"
    cache_dir = hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    outside_path = tmp_path / "outside.pdf"
    outside_path.write_bytes(b"%PDF-outside")
    hard_link_path = cache_dir / "doc_hardlink.pdf"
    os.link(outside_path, hard_link_path)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        thread_id="478",
        session_key="sess-1",
    )
    try:
        with pytest.raises(ValueError, match="hard-linked"):
            notebooklm_mod.add_source(
                notebook_id="nb-478",
                source_type="file",
                content=str(hard_link_path),
            )
    finally:
        clear_session_vars(tokens)
