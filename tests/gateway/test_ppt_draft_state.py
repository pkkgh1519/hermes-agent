from types import SimpleNamespace

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.ppt_draft_state import (
    add_photo_batch,
    clear_session_draft_intake,
    get_session_draft_intake,
    set_latest_csv,
)
from gateway.platforms.base import MessageEvent, MessageType, SessionSource
from gateway.run import GatewayRunner
from gateway.session import build_session_key


@pytest.fixture(autouse=True)
def _clear_draft_state_between_tests():
    yield
    session_keys = [
        "agent:main:telegram:group:-1003586456169:3",
        build_session_key(_make_source()),
    ]
    for session_key in session_keys:
        clear_session_draft_intake(session_key)


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_runner() -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake-token")}
    )
    runner.adapters = {Platform.TELEGRAM: SimpleNamespace(send=None)}
    runner.hooks = SimpleNamespace(emit=None, loaded_hooks=False)
    runner._session_model_overrides = {}
    runner.session_store = None

    async def _identity(text, _paths):
        return text

    runner._enrich_message_with_vision = _identity
    runner._enrich_message_with_transcription = _identity
    return runner


def test_set_latest_csv_and_get_session_intake():
    session_key = "agent:main:telegram:group:-1003586456169:3"

    result = set_latest_csv(
        session_key,
        path="/home/hwan/.hermes/cache/documents/offers.csv",
        filename="offers.csv",
        message_id="101",
        uploaded_at=1710000000.0,
    )

    assert result is not None
    assert result.path == "/home/hwan/.hermes/cache/documents/offers.csv"
    assert result.filename == "offers.csv"
    assert result.message_id == "101"
    assert result.uploaded_at == 1710000000.0

    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert intake.latest_csv is not None
    assert intake.latest_csv.path == "/home/hwan/.hermes/cache/documents/offers.csv"
    assert intake.photo_batches == []



def test_add_photo_batches_preserves_order_and_clear():
    session_key = "agent:main:telegram:group:-1003586456169:3"

    first = add_photo_batch(
        session_key,
        tag="offer_01",
        image_paths=[
            "/home/hwan/.hermes/cache/images/a.jpg",
            "/home/hwan/.hermes/cache/images/b.jpg",
        ],
        message_id="201",
        uploaded_at=1710000001.0,
    )
    second = add_photo_batch(
        session_key,
        tag="offer_02",
        image_paths=["/home/hwan/.hermes/cache/images/c.jpg"],
        message_id="202",
        uploaded_at=1710000002.0,
    )

    assert first is not None
    assert second is not None
    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert [batch.tag for batch in intake.photo_batches] == ["offer_01", "offer_02"]
    assert intake.photo_batches[0].image_paths == [
        "/home/hwan/.hermes/cache/images/a.jpg",
        "/home/hwan/.hermes/cache/images/b.jpg",
    ]
    assert intake.photo_batches[1].image_paths == ["/home/hwan/.hermes/cache/images/c.jpg"]

    assert clear_session_draft_intake(session_key) is True
    assert get_session_draft_intake(session_key) is None
    assert clear_session_draft_intake(session_key) is False



def test_photo_batches_are_bounded_to_latest_twenty():
    session_key = "agent:main:telegram:group:-1003586456169:3"

    for idx in range(25):
        add_photo_batch(
            session_key,
            tag=f"offer_{idx:02d}",
            image_paths=[f"/home/hwan/.hermes/cache/images/{idx:02d}.jpg"],
            uploaded_at=1710001000.0 + idx,
        )

    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert len(intake.photo_batches) == 20
    assert intake.photo_batches[0].tag == "offer_05"
    assert intake.photo_batches[-1].tag == "offer_24"


@pytest.mark.asyncio
async def test_prepare_inbound_text_records_offers_csv_from_document_cache(tmp_path, monkeypatch):
    source = _make_source()
    session_key = build_session_key(source)
    runner = _make_runner()

    document_cache = tmp_path / "documents"
    document_cache.mkdir(parents=True)
    csv_path = document_cache / "offers.csv"
    csv_path.write_text("id,name\noffer_01,테스트\n", encoding="utf-8")

    monkeypatch.setattr("gateway.run.get_document_cache_dir", lambda: document_cache)
    monkeypatch.setattr("gateway.run.get_image_cache_dir", lambda: tmp_path / "images")

    event = MessageEvent(
        text="",
        message_type=MessageType.DOCUMENT,
        source=source,
        message_id="doc-1",
        media_urls=[str(csv_path)],
        media_types=["text/csv"],
    )

    prepared = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert intake.latest_csv is not None
    assert intake.latest_csv.filename == "offers.csv"
    assert intake.latest_csv.message_id == "doc-1"
    assert "Draft intake: file=offers.csv" in prepared


@pytest.mark.asyncio
async def test_prepare_inbound_text_records_xlsx_from_document_cache(tmp_path, monkeypatch):
    source = _make_source()
    session_key = build_session_key(source)
    runner = _make_runner()

    document_cache = tmp_path / "documents"
    document_cache.mkdir(parents=True)
    xlsx_path = document_cache / "매물.xlsx"
    xlsx_path.write_bytes(b"placeholder-xlsx")

    monkeypatch.setattr("gateway.run.get_document_cache_dir", lambda: document_cache)
    monkeypatch.setattr("gateway.run.get_image_cache_dir", lambda: tmp_path / "images")

    event = MessageEvent(
        text="",
        message_type=MessageType.DOCUMENT,
        source=source,
        message_id="doc-xlsx-1",
        media_urls=[str(xlsx_path)],
        media_types=["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    )

    prepared = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert intake.latest_csv is not None
    assert intake.latest_csv.filename == "매물.xlsx"
    assert intake.latest_csv.message_id == "doc-xlsx-1"
    assert "Draft intake: file=매물.xlsx" in prepared


@pytest.mark.asyncio
async def test_prepare_inbound_text_records_photo_batch_from_offer_tag(tmp_path, monkeypatch):
    source = _make_source()
    session_key = build_session_key(source)
    runner = _make_runner()

    image_cache = tmp_path / "images"
    image_cache.mkdir(parents=True)
    image_one = image_cache / "1.jpg"
    image_two = image_cache / "2.jpg"
    image_one.write_bytes(b"a")
    image_two.write_bytes(b"b")

    monkeypatch.setattr("gateway.run.get_document_cache_dir", lambda: tmp_path / "documents")
    monkeypatch.setattr("gateway.run.get_image_cache_dir", lambda: image_cache)

    event = MessageEvent(
        text="offer_01",
        message_type=MessageType.PHOTO,
        source=source,
        message_id="photo-1",
        media_urls=[str(image_one), str(image_two)],
        media_types=["image/jpeg", "image/jpeg"],
    )

    prepared = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    intake = get_session_draft_intake(session_key)
    assert intake is not None
    assert len(intake.photo_batches) == 1
    assert intake.photo_batches[0].tag == "offer_01"
    assert intake.photo_batches[0].image_paths == [str(image_one), str(image_two)]
    assert "offer_01(2)" in prepared


@pytest.mark.asyncio
async def test_prepare_inbound_text_injects_existing_draft_intake_summary():
    source = _make_source()
    session_key = build_session_key(source)
    runner = _make_runner()

    set_latest_csv(
        session_key,
        path="/home/hwan/.hermes/cache/documents/offers.csv",
        filename="offers.csv",
    )
    add_photo_batch(
        session_key,
        tag="offer_01",
        image_paths=[
            "/home/hwan/.hermes/cache/images/1.jpg",
            "/home/hwan/.hermes/cache/images/2.jpg",
        ],
    )
    add_photo_batch(
        session_key,
        tag="offer_02",
        image_paths=["/home/hwan/.hermes/cache/images/3.jpg"],
    )

    event = MessageEvent(
        text="생성해줘",
        message_type=MessageType.TEXT,
        source=source,
        message_id="msg-1",
    )

    prepared = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    assert "Draft intake: file=offers.csv" in prepared
    assert "offer_01(2)" in prepared
    assert "offer_02(1)" in prepared
    assert "생성해줘" in prepared
