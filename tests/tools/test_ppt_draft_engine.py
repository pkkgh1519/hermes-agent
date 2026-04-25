import base64
from pathlib import Path
from zipfile import ZipFile

import pytest

from gateway.ppt_draft_state import DraftPhotoBatch
from tools.ppt_draft_engine import (
    DraftInputError,
    build_draft_payload,
    create_draft_pptx,
    parse_offers_csv,
)


REQUIRED_HEADER = "id,name,location,size_floor,price,points,photo_tag\n"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_image(path: Path) -> str:
    path.write_bytes(PNG_1X1)
    return str(path)


def _count_slides(pptx_path: Path) -> int:
    with ZipFile(pptx_path) as zf:
        return len([name for name in zf.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")])


def test_parse_offers_csv_rejects_missing_required_columns(tmp_path):
    csv_path = _write_csv(
        tmp_path / "offers.csv",
        "id,name,location,size_floor,price,points\n"
        "offer_01,캐슬프라자 3층,성수동,3층 / 18평,2000/160/42,주차 1대\n",
    )

    with pytest.raises(DraftInputError) as exc:
        parse_offers_csv(csv_path)

    assert exc.value.code == "missing_columns"
    assert "photo_tag" in str(exc.value)



def test_build_draft_payload_rejects_unmatched_photo_tag(tmp_path):
    csv_path = _write_csv(
        tmp_path / "offers.csv",
        REQUIRED_HEADER
        + "offer_01,캐슬프라자 3층,성수동 2가 289-13 / 성수역 도보 2분,3층 / 18평,보증금 2000 / 월세 160 / 관리비 42,주차 1대; 공실,offer_01\n",
    )

    with pytest.raises(DraftInputError) as exc:
        build_draft_payload(
            csv_path,
            photo_batches=[
                DraftPhotoBatch(
                    tag="offer_02",
                    image_paths=["/tmp/offer_02_01.jpg"],
                    message_id="m1",
                    uploaded_at=1710000000.0,
                )
            ],
        )

    assert exc.value.code == "photo_tag_not_matched"
    assert "offer_01" in str(exc.value)



def test_build_draft_payload_normalizes_points_and_aggregates_photo_batches(tmp_path):
    csv_path = _write_csv(
        tmp_path / "offers.csv",
        REQUIRED_HEADER
        + "offer_01,캐슬프라자 3층,성수동 2가 289-13 / 성수역 도보 2분,3층 / 18평,보증금 2000 / 월세 160 / 관리비 42,주차 1대; 인테리어 있음; 공실,offer_01\n"
        + "offer_02,동성빌딩 4층,성수동 2가 277-50 / 성수역 도보 4분,4층 / 14평,보증금 1100 / 월세 105 / 관리비 16,주차 가능; 공실; 화물 EV 가능,offer_02\n",
    )

    payload = build_draft_payload(
        csv_path,
        photo_batches=[
            DraftPhotoBatch(
                tag=" offer_01 ",
                image_paths=["/tmp/offer_01_01.jpg", "/tmp/offer_01_02.jpg"],
                message_id="m1",
                uploaded_at=1710000000.0,
            ),
            DraftPhotoBatch(
                tag="offer_01",
                image_paths=["/tmp/offer_01_03.jpg"],
                message_id="m2",
                uploaded_at=1710000001.0,
            ),
            DraftPhotoBatch(
                tag="offer_02",
                image_paths=["/tmp/offer_02_01.jpg"],
                message_id="m3",
                uploaded_at=1710000002.0,
            ),
        ],
    )

    assert payload.csv_path == str(csv_path)
    assert payload.matched_photo_count == 4
    assert payload.unmatched_photo_tags == []
    assert [offer.id for offer in payload.offers] == ["offer_01", "offer_02"]
    assert payload.offers[0].points == ["주차 1대", "인테리어 있음", "공실"]
    assert payload.offers[0].photo_paths == [
        "/tmp/offer_01_01.jpg",
        "/tmp/offer_01_02.jpg",
        "/tmp/offer_01_03.jpg",
    ]
    assert payload.offers[1].photo_paths == ["/tmp/offer_02_01.jpg"]



def test_create_draft_pptx_writes_expected_slides_for_basic_payload(tmp_path):
    csv_path = _write_csv(
        tmp_path / "offers.csv",
        REQUIRED_HEADER
        + "offer_01,캐슬프라자 3층,성수동 2가 289-13 / 성수역 도보 2분,3층 / 18평,보증금 2000 / 월세 160 / 관리비 42,주차 1대; 인테리어 있음; 공실,offer_01\n"
        + "offer_02,동성빌딩 4층,성수동 2가 277-50 / 성수역 도보 4분,4층 / 14평,보증금 1100 / 월세 105 / 관리비 16,주차 가능; 공실; 화물 EV 가능,offer_02\n",
    )
    image_dir = tmp_path / "images"
    image_dir.mkdir()

    payload = build_draft_payload(
        csv_path,
        photo_batches=[
            DraftPhotoBatch(
                tag="offer_01",
                image_paths=[
                    _write_image(image_dir / "offer_01_01.png"),
                    _write_image(image_dir / "offer_01_02.png"),
                    _write_image(image_dir / "offer_01_03.png"),
                ],
            ),
            DraftPhotoBatch(
                tag="offer_02",
                image_paths=[
                    _write_image(image_dir / "offer_02_01.png"),
                    _write_image(image_dir / "offer_02_02.png"),
                    _write_image(image_dir / "offer_02_03.png"),
                    _write_image(image_dir / "offer_02_04.png"),
                    _write_image(image_dir / "offer_02_05.png"),
                ],
            ),
        ],
    )

    output_path = tmp_path / "draft-basic.pptx"
    created = create_draft_pptx(payload, output_path, title="성수 임대차 제안서", client="OO브랜드")

    assert Path(created) == output_path
    assert output_path.exists()
    assert _count_slides(output_path) == 7



def test_create_draft_pptx_splits_large_gallery_across_multiple_slides(tmp_path):
    csv_path = _write_csv(
        tmp_path / "offers.csv",
        REQUIRED_HEADER
        + "offer_01,캐슬프라자 7층,성수동 2가 289-13 / 성수역 도보 2분,7층 / 21평,보증금 2000 / 월세 160 / 관리비 42,주차 1대; 인테리어 있음; 공실,offer_01\n",
    )
    image_dir = tmp_path / "images"
    image_dir.mkdir()

    payload = build_draft_payload(
        csv_path,
        photo_batches=[
            DraftPhotoBatch(
                tag="offer_01",
                image_paths=[_write_image(image_dir / f"{idx:02d}.png") for idx in range(10)],
            ),
        ],
    )

    output_path = tmp_path / "draft-gallery-split.pptx"
    create_draft_pptx(payload, output_path)

    assert output_path.exists()
    assert _count_slides(output_path) == 6
