import base64
import json
from pathlib import Path

import pytest

from gateway.ppt_draft_state import add_photo_batch, clear_session_draft_intake, set_latest_csv
from gateway.session_context import clear_session_vars, set_session_vars
from tools.ppt_draft_tool import ppt_draft_tool


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def _reset_session_and_state():
    session_key = "agent:main:telegram:dm:c1:u1"
    tokens = set_session_vars(
        platform="telegram",
        chat_id="c1",
        user_id="u1",
        user_name="tester",
        session_key=session_key,
    )
    yield session_key
    clear_session_vars(tokens)
    clear_session_draft_intake(session_key)



def _write_png(path: Path) -> str:
    path.write_bytes(PNG_1X1)
    return str(path)



def test_status_reports_current_intake(tmp_path, monkeypatch, _reset_session_and_state):
    session_key = _reset_session_and_state
    csv_path = tmp_path / "offers.csv"
    csv_path.write_text(
        "id,name,location,size_floor,price,points,photo_tag\n"
        "offer_01,캐슬프라자 3층,성수동 / 성수역 2분,3층 / 18평,2000/160/42,주차 1대; 공실,offer_01\n",
        encoding="utf-8",
    )
    set_latest_csv(session_key, path=str(csv_path), filename="offers.csv")
    add_photo_batch(session_key, tag="offer_01", image_paths=["/tmp/a.jpg", "/tmp/b.jpg"])

    payload = json.loads(ppt_draft_tool(action="status"))

    assert payload["session_key"] == session_key
    assert payload["has_csv"] is True
    assert payload["csv_filename"] == "offers.csv"
    assert payload["photo_tags"] == {"offer_01": 2}



def test_clear_removes_current_session_intake(_reset_session_and_state):
    session_key = _reset_session_and_state
    set_latest_csv(session_key, path="/tmp/offers.csv", filename="offers.csv")
    add_photo_batch(session_key, tag="offer_01", image_paths=["/tmp/a.jpg"])

    payload = json.loads(ppt_draft_tool(action="clear"))

    assert payload["cleared"] is True
    assert payload["session_key"] == session_key



def test_build_generates_output_pptx_for_current_session(tmp_path, monkeypatch, _reset_session_and_state):
    session_key = _reset_session_and_state
    document_root = tmp_path / "documents"
    document_root.mkdir(parents=True)
    image_root = tmp_path / "images"
    image_root.mkdir(parents=True)

    csv_path = document_root / "offers.csv"
    csv_path.write_text(
        "id,name,location,size_floor,price,points,photo_tag\n"
        "offer_01,캐슬프라자 3층,성수동 / 성수역 2분,3층 / 18평,2000/160/42,주차 1대; 공실,offer_01\n",
        encoding="utf-8",
    )
    set_latest_csv(session_key, path=str(csv_path), filename="offers.csv")
    add_photo_batch(
        session_key,
        tag="offer_01",
        image_paths=[
            _write_png(image_root / "01.png"),
            _write_png(image_root / "02.png"),
            _write_png(image_root / "03.png"),
        ],
    )

    monkeypatch.setattr("tools.ppt_draft_tool.get_document_cache_dir", lambda: document_root)

    payload = json.loads(ppt_draft_tool(action="build", title="성수 제안서", client="OO브랜드"))

    assert payload["ok"] is True
    assert payload["offer_count"] == 1
    assert payload["matched_photo_count"] == 3
    assert Path(payload["output_path"]).exists()
    assert Path(payload["output_path"]).parent == document_root / "ppt_drafts"
