"""CSV parsing, photo-tag matching, and PPT draft generation helpers."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from gateway.ppt_draft_state import DraftPhotoBatch


REQUIRED_COLUMNS = (
    "id",
    "name",
    "location",
    "size_floor",
    "price",
    "points",
    "photo_tag",
)


class DraftInputError(Exception):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(slots=True)
class ParsedOffer:
    id: str
    name: str
    location: str
    size_floor: str
    price: str
    points: list[str]
    photo_tag: str
    photo_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DraftBuildPayload:
    csv_path: str
    offers: list[ParsedOffer]
    matched_photo_count: int
    unmatched_photo_tags: list[str]


def _normalize_tag(value: str) -> str:
    return str(value or "").strip().lower()


def _split_points(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]



def parse_offers_csv(csv_path: str | Path) -> list[ParsedOffer]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            raise DraftInputError(
                "missing_columns",
                f"Missing required CSV columns: {', '.join(missing)}",
                details={"missing_columns": missing},
            )

        offers: list[ParsedOffer] = []
        for row in reader:
            if not row:
                continue
            if not any(str(value or "").strip() for value in row.values()):
                continue
            offers.append(
                ParsedOffer(
                    id=str(row.get("id") or "").strip(),
                    name=str(row.get("name") or "").strip(),
                    location=str(row.get("location") or "").strip(),
                    size_floor=str(row.get("size_floor") or "").strip(),
                    price=str(row.get("price") or "").strip(),
                    points=_split_points(str(row.get("points") or "")),
                    photo_tag=str(row.get("photo_tag") or "").strip(),
                )
            )
        return offers



def _aggregate_photo_batches(photo_batches: Iterable[DraftPhotoBatch]) -> dict[str, list[str]]:
    tag_to_paths: dict[str, list[str]] = {}
    for batch in photo_batches:
        tag = _normalize_tag(batch.tag)
        if not tag:
            continue
        paths = tag_to_paths.setdefault(tag, [])
        for path in batch.image_paths:
            value = str(path).strip()
            if value:
                paths.append(value)
    return tag_to_paths



def build_draft_payload(
    csv_path: str | Path,
    *,
    photo_batches: Iterable[DraftPhotoBatch],
) -> DraftBuildPayload:
    offers = parse_offers_csv(csv_path)
    tag_to_paths = _aggregate_photo_batches(photo_batches)
    required_tags = {_normalize_tag(offer.photo_tag) for offer in offers}

    unmatched_required = [
        offer.photo_tag
        for offer in offers
        if _normalize_tag(offer.photo_tag) not in tag_to_paths
    ]
    if unmatched_required:
        raise DraftInputError(
            "photo_tag_not_matched",
            f"No photo batch matched required tag(s): {', '.join(unmatched_required)}",
            details={"unmatched_required_tags": unmatched_required},
        )

    for offer in offers:
        offer.photo_paths = list(tag_to_paths.get(_normalize_tag(offer.photo_tag), []))

    unmatched_photo_tags = sorted(
        tag for tag in tag_to_paths.keys()
        if tag not in required_tags
    )
    matched_photo_count = sum(len(offer.photo_paths) for offer in offers)

    return DraftBuildPayload(
        csv_path=str(Path(csv_path)),
        offers=offers,
        matched_photo_count=matched_photo_count,
        unmatched_photo_tags=unmatched_photo_tags,
    )



def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]



def create_draft_pptx(
    payload: DraftBuildPayload,
    output_path: str | Path,
    *,
    title: str | None = None,
    client: str | None = None,
) -> str:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_title(slide, text: str, *, top: float = 0.35, size: int = 24):
        box = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.6))
        paragraph = box.text_frame.paragraphs[0]
        paragraph.text = text
        paragraph.font.size = Pt(size)
        paragraph.font.bold = True
        paragraph.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    def add_body_text(slide, text: str, *, left: float, top: float, width: float, height: float, size: int = 16):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        frame = box.text_frame
        frame.clear()
        for idx, line in enumerate([part for part in text.split("\n") if part.strip()] or [""]):
            paragraph = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.font.size = Pt(size)
            paragraph.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    def add_points(slide, points: list[str], *, left: float, top: float, width: float):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(2.2))
        frame = box.text_frame
        frame.clear()
        for idx, point in enumerate(points or ["포인트 없음"]):
            paragraph = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
            paragraph.text = point
            paragraph.level = 0
            paragraph.font.size = Pt(15)
            paragraph.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
            paragraph.bullet = True

    def add_picture_grid(slide, image_paths: list[str], *, left: float, top: float, width: float, height: float):
        count = len(image_paths)
        if count <= 1:
            cols = 1
        elif count <= 4:
            cols = 2
        else:
            cols = 3
        rows = math.ceil(count / cols)
        gap_x = 0.12
        gap_y = 0.12
        cell_w = (width - gap_x * (cols - 1)) / cols
        cell_h = (height - gap_y * (rows - 1)) / rows
        for idx, image_path in enumerate(image_paths):
            row = idx // cols
            col = idx % cols
            x = left + col * (cell_w + gap_x)
            y = top + row * (cell_h + gap_y)
            slide.shapes.add_picture(str(image_path), Inches(x), Inches(y), width=Inches(cell_w), height=Inches(cell_h))

    def add_offer_card(slide, offer: ParsedOffer, *, left: float, top: float, width: float, height: float):
        shape = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(left),
            Inches(top),
            Inches(width),
            Inches(height),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(0xF3, 0xF4, 0xF6)
        shape.line.color.rgb = RGBColor(0xD1, 0xD5, 0xDB)
        frame = shape.text_frame
        frame.clear()
        lines = [
            offer.name,
            offer.location,
            offer.size_floor,
            offer.price,
            ", ".join(offer.points[:3]) if offer.points else "포인트 없음",
        ]
        for idx, line in enumerate(lines):
            paragraph = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.font.size = Pt(14 if idx else 16)
            paragraph.font.bold = idx == 0
            paragraph.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    # Cover
    slide = prs.slides.add_slide(blank)
    add_title(slide, title or "매물 제안서", top=1.1, size=30)
    add_body_text(
        slide,
        f"고객사: {client or '-'}\n작성일: {datetime.now().strftime('%Y-%m-%d')}\n매물 수: {len(payload.offers)}건",
        left=0.8,
        top=2.1,
        width=4.5,
        height=1.8,
        size=18,
    )

    # Briefing table (6 offers per slide)
    for chunk_index, offer_chunk in enumerate(_chunk(payload.offers, 6), start=1):
        slide = prs.slides.add_slide(blank)
        add_title(slide, f"추천 매물 브리핑 {chunk_index}")
        rows = len(offer_chunk) + 1
        cols = 5
        table = slide.shapes.add_table(rows, cols, Inches(0.45), Inches(1.1), Inches(12.3), Inches(5.4)).table
        headers = ["매물명", "위치", "층/면적", "가격", "포인트"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
        for row, offer in enumerate(offer_chunk, start=1):
            table.cell(row, 0).text = offer.name
            table.cell(row, 1).text = offer.location
            table.cell(row, 2).text = offer.size_floor
            table.cell(row, 3).text = offer.price
            table.cell(row, 4).text = ", ".join(offer.points[:3]) if offer.points else "-"
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.size = Pt(11)
                    paragraph.alignment = PP_ALIGN.LEFT

    # Offer summary + gallery
    for offer in payload.offers:
        slide = prs.slides.add_slide(blank)
        add_title(slide, offer.name)
        add_body_text(
            slide,
            f"위치\n{offer.location}\n\n층/면적\n{offer.size_floor}\n\n가격\n{offer.price}",
            left=0.7,
            top=1.2,
            width=4.0,
            height=3.5,
            size=16,
        )
        add_points(slide, offer.points, left=0.7, top=4.7, width=4.2)
        add_picture_grid(slide, offer.photo_paths[: min(3, len(offer.photo_paths))], left=5.1, top=1.2, width=7.5, height=5.5)

        gallery_chunks = _chunk(offer.photo_paths, 9)
        for chunk_index, gallery_paths in enumerate(gallery_chunks, start=1):
            slide = prs.slides.add_slide(blank)
            add_title(slide, f"{offer.name} 사진 {chunk_index}")
            add_picture_grid(slide, gallery_paths, left=0.55, top=1.2, width=12.2, height=5.7)

    # Closing
    slide = prs.slides.add_slide(blank)
    add_title(slide, "검토 후 세부 조건은 PPT에서 수정해 사용하세요.", top=2.0, size=24)
    add_body_text(
        slide,
        "초안 자동 생성 완료\n- 가격/표현은 최종 검토\n- 사진 순서는 필요 시 수동 조정\n- 고객 맞춤 멘트만 추가하면 바로 사용 가능",
        left=1.0,
        top=3.0,
        width=11.0,
        height=2.0,
        size=18,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output))
    return str(output)
