"""Per-session NotebookLM hub selection state."""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix fallback
    fcntl = None


_HUB_STATE_LOCK = threading.Lock()



def _hermes_home() -> Path:
    raw = os.getenv("HERMES_HOME", "~/.hermes")
    return Path(raw).expanduser()



def _state_path() -> Path:
    return _hermes_home() / "notebooklm_hubs.json"


@contextmanager
def _locked_state_file():
    with _HUB_STATE_LOCK:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        with path.open("r+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield handle
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)



def _read_locked(handle) -> dict[str, Any]:
    handle.seek(0)
    raw = handle.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload



def _write_locked(handle, payload: dict[str, Any]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
    handle.flush()



def get_selected_notebook(session_key: str | None) -> dict[str, str] | None:
    if not session_key:
        return None
    with _locked_state_file() as handle:
        payload = _read_locked(handle)
    entry = payload.get(str(session_key))
    if not isinstance(entry, dict):
        return None
    notebook = entry.get("notebook")
    notebook_id = entry.get("notebook_id")
    if not notebook and not notebook_id:
        return None
    return {
        "notebook": str(notebook or ""),
        "notebook_id": str(notebook_id or ""),
    }



def set_selected_notebook(
    session_key: str | None,
    *,
    notebook: str | None,
    notebook_id: str | None,
) -> dict[str, str] | None:
    if not session_key:
        return None
    record = {
        "notebook": str(notebook or ""),
        "notebook_id": str(notebook_id or ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with _locked_state_file() as handle:
        payload = _read_locked(handle)
        payload[str(session_key)] = record
        _write_locked(handle, payload)
    return {
        "notebook": record["notebook"],
        "notebook_id": record["notebook_id"],
    }



def clear_selected_notebook(session_key: str | None) -> bool:
    if not session_key:
        return False
    removed = False
    with _locked_state_file() as handle:
        payload = _read_locked(handle)
        if str(session_key) in payload:
            removed = True
            payload.pop(str(session_key), None)
            _write_locked(handle, payload)
    return removed
