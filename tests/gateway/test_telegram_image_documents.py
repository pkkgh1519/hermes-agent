from types import SimpleNamespace

import pytest

from gateway.platforms.base import MessageEvent, MessageType, SessionSource
from gateway.platforms.telegram import TelegramAdapter


class _FakeTelegramFile:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def download_as_bytearray(self):
        return bytearray(self._payload)


class _FakeTelegramDocument:
    def __init__(self, *, file_name: str, mime_type: str, payload: bytes):
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_size = len(payload)
        self._payload = payload

    async def get_file(self):
        return _FakeTelegramFile(self._payload)


@pytest.mark.asyncio
async def test_png_document_upload_is_normalized_to_image_event(monkeypatch, tmp_path):
    """Telegram 'send as file' PNG uploads should behave like image uploads internally."""
    source = SessionSource(
        platform="telegram",
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )
    handled_events: list[MessageEvent] = []
    cached_calls: list[tuple[bytes, str]] = []
    cached_path = str(tmp_path / "images" / "img_original.png")

    def _fake_cache_image_from_bytes(data: bytes, ext: str = ".jpg") -> str:
        cached_calls.append((data, ext))
        return cached_path

    adapter = object.__new__(TelegramAdapter)
    adapter._should_process_message = lambda _message: True
    adapter._build_message_event = lambda _message, msg_type, update_id=None: MessageEvent(
        text="",
        message_type=msg_type,
        source=source,
        message_id="doc-image-1",
        platform_update_id=update_id,
    )

    async def _fake_handle_message(event: MessageEvent):
        handled_events.append(event)

    adapter.handle_message = _fake_handle_message
    monkeypatch.setattr(
        "gateway.platforms.telegram.cache_image_from_bytes",
        _fake_cache_image_from_bytes,
    )

    payload = b"\x89PNG\r\n\x1a\nnot-a-full-png-but-good-enough-for-this-branch-test"
    message = SimpleNamespace(
        sticker=None,
        photo=[],
        video=None,
        audio=None,
        voice=None,
        document=_FakeTelegramDocument(
            file_name="original-profile.png",
            mime_type="image/png",
            payload=payload,
        ),
        caption=None,
        media_group_id=None,
    )
    update = SimpleNamespace(message=message, update_id=12345)

    await TelegramAdapter._handle_media_message(adapter, update, SimpleNamespace())

    assert cached_calls == [(payload, ".png")]
    assert len(handled_events) == 1
    event = handled_events[0]
    assert event.message_type == MessageType.PHOTO
    assert event.media_urls == [cached_path]
    assert event.media_types == ["image/png"]
    assert "Unsupported document type" not in event.text
