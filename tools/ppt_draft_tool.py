#!/usr/bin/env python3
"""Session-aware PPT draft generation tool."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from gateway.ppt_draft_state import clear_session_draft_intake, get_session_draft_intake
from gateway.session_context import get_session_env
from gateway.platforms.base import get_document_cache_dir
from tools.ppt_draft_engine import DraftInputError, build_draft_payload, create_draft_pptx
from tools.registry import registry, tool_error, tool_result



def _current_session_key() -> str:
    return (get_session_env("HERMES_SESSION_KEY", "") or "").strip()



def _summarize_photo_tags(intake) -> dict[str, int]:
    counts: OrderedDict[str, int] = OrderedDict()
    for batch in intake.photo_batches:
        counts.setdefault(batch.tag, 0)
        counts[batch.tag] += len(batch.image_paths)
    return dict(counts)



def ppt_draft_tool(
    action: str = "status",
    title: str | None = None,
    client: str | None = None,
) -> str:
    action = (action or "status").strip().lower()
    session_key = _current_session_key()
    if not session_key:
        return tool_error("No active session_key is available for ppt_draft")

    if action == "clear":
        return tool_result(session_key=session_key, cleared=clear_session_draft_intake(session_key))

    intake = get_session_draft_intake(session_key)
    if action == "status":
        return tool_result(
            session_key=session_key,
            has_csv=bool(intake and intake.latest_csv),
            has_offer_file=bool(intake and intake.latest_csv),
            csv_filename=(intake.latest_csv.filename if intake and intake.latest_csv else None),
            offer_filename=(intake.latest_csv.filename if intake and intake.latest_csv else None),
            photo_batch_count=(len(intake.photo_batches) if intake else 0),
            photo_tags=(_summarize_photo_tags(intake) if intake else {}),
        )

    if action == "build":
        if intake is None or intake.latest_csv is None:
            return tool_error("No offers .csv/.xlsx file is registered for the current session")
        try:
            payload = build_draft_payload(
                intake.latest_csv.path,
                photo_batches=intake.photo_batches,
            )
            output_root = get_document_cache_dir() / "ppt_drafts"
            output_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            output_path = output_root / f"{timestamp}-draft.pptx"
            created = create_draft_pptx(payload, output_path, title=title, client=client)
            return tool_result(
                ok=True,
                session_key=session_key,
                output_path=created,
                media_path=created,
                send_instruction=f"Include MEDIA:{created} in the final response to deliver the PPTX file.",
                offer_count=len(payload.offers),
                matched_photo_count=payload.matched_photo_count,
                unmatched_photo_tags=payload.unmatched_photo_tags,
            )
        except DraftInputError as exc:
            return tool_error(str(exc), code=exc.code, details=exc.details)

    return tool_error(f"Unknown action: {action}")



def check_ppt_draft_requirements() -> bool:
    try:
        import pptx  # noqa: F401
        return True
    except Exception:
        return False


PPT_DRAFT_SCHEMA = {
    "name": "ppt_draft",
    "description": (
        "Build a draft PPTX from the current session's uploaded offers .csv/.xlsx file and tagged photo batches. "
        "Actions: status, build, clear."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "build", "clear"],
                "description": "Operation to perform",
            },
            "title": {
                "type": "string",
                "description": "Optional deck title override for action='build'.",
            },
            "client": {
                "type": "string",
                "description": "Optional client/company label for action='build'.",
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="ppt_draft",
    toolset="ppt_draft",
    schema=PPT_DRAFT_SCHEMA,
    handler=lambda args, **kw: ppt_draft_tool(
        action=args.get("action", "status"),
        title=args.get("title"),
        client=args.get("client"),
    ),
    check_fn=check_ppt_draft_requirements,
    emoji="📊",
)
