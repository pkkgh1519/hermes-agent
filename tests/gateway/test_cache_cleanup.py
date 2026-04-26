import os
import threading
import time
from pathlib import Path

from gateway.platforms import base
from gateway import run as gateway_run


def _write_file_with_age(path: Path, *, age_hours: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("cached", encoding="utf-8")
    timestamp = time.time() - (age_hours * 3600)
    os.utime(path, (timestamp, timestamp))


def test_cleanup_document_cache_recurses_and_defaults_to_48_hours(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "DOCUMENT_CACHE_DIR", tmp_path)

    stale_root = tmp_path / "old.pdf"
    stale_nested = tmp_path / "ppt_drafts" / "old.pptx"
    recent_root = tmp_path / "recent.pdf"
    recent_nested = tmp_path / "ppt_drafts" / "recent.pptx"

    _write_file_with_age(stale_root, age_hours=49)
    _write_file_with_age(stale_nested, age_hours=49)
    _write_file_with_age(recent_root, age_hours=47)
    _write_file_with_age(recent_nested, age_hours=47)

    removed = base.cleanup_document_cache()

    assert removed == 2
    assert not stale_root.exists()
    assert not stale_nested.exists()
    assert recent_root.exists()
    assert recent_nested.exists()


def test_cron_ticker_uses_48_hour_cache_retention(monkeypatch):
    import cron.scheduler as scheduler

    stop_event = threading.Event()
    tick_count = 0
    cleanup_calls: list[tuple[str, int]] = []

    def fake_tick(*, verbose=False, adapters=None, loop=None):
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 60:
            stop_event.set()

    def fake_cleanup_image_cache(*, max_age_hours: int):
        cleanup_calls.append(("image", max_age_hours))
        return 0

    def fake_cleanup_document_cache(*, max_age_hours: int):
        cleanup_calls.append(("document", max_age_hours))
        return 0

    monkeypatch.setattr(scheduler, "tick", fake_tick)
    monkeypatch.setattr(base, "cleanup_image_cache", fake_cleanup_image_cache)
    monkeypatch.setattr(base, "cleanup_document_cache", fake_cleanup_document_cache)

    gateway_run._start_cron_ticker(stop_event, interval=0)

    assert tick_count == 60
    assert cleanup_calls == [("image", 48), ("document", 48)]
