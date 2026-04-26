"""Per-session intake state for CSV + photo based PPT draft generation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import threading
import time
from typing import Iterable


_MAX_PHOTO_BATCHES = 20
_STATE_LOCK = threading.RLock()
_SESSION_STATE: dict[str, "SessionDraftIntake"] = {}


@dataclass(slots=True)
class DraftCsvUpload:
    path: str
    filename: str
    message_id: str | None = None
    uploaded_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class DraftPhotoBatch:
    tag: str
    image_paths: list[str]
    message_id: str | None = None
    uploaded_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class PendingDraftPhotoBatch:
    image_paths: list[str]
    message_id: str | None = None
    uploaded_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class SessionDraftIntake:
    latest_csv: DraftCsvUpload | None = None
    photo_batches: list[DraftPhotoBatch] = field(default_factory=list)
    pending_photo_batches: list[PendingDraftPhotoBatch] = field(default_factory=list)


def _normalize_session_key(session_key: str | None) -> str | None:
    if session_key is None:
        return None
    key = str(session_key).strip()
    return key or None


def _normalize_paths(image_paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for path in image_paths:
        value = str(path).strip()
        if value:
            normalized.append(value)
    return normalized


def get_session_draft_intake(session_key: str | None) -> SessionDraftIntake | None:
    key = _normalize_session_key(session_key)
    if not key:
        return None
    with _STATE_LOCK:
        intake = _SESSION_STATE.get(key)
        return deepcopy(intake) if intake is not None else None


def set_latest_csv(
    session_key: str | None,
    *,
    path: str,
    filename: str,
    message_id: str | None = None,
    uploaded_at: float | None = None,
) -> DraftCsvUpload | None:
    key = _normalize_session_key(session_key)
    if not key:
        return None
    entry = DraftCsvUpload(
        path=str(path).strip(),
        filename=str(filename).strip(),
        message_id=str(message_id) if message_id is not None else None,
        uploaded_at=float(uploaded_at) if uploaded_at is not None else time.time(),
    )
    with _STATE_LOCK:
        intake = _SESSION_STATE.setdefault(key, SessionDraftIntake())
        intake.latest_csv = entry
    return deepcopy(entry)


def add_photo_batch(
    session_key: str | None,
    *,
    tag: str,
    image_paths: Iterable[str],
    message_id: str | None = None,
    uploaded_at: float | None = None,
) -> DraftPhotoBatch | None:
    key = _normalize_session_key(session_key)
    if not key:
        return None
    entry = DraftPhotoBatch(
        tag=str(tag).strip(),
        image_paths=_normalize_paths(image_paths),
        message_id=str(message_id) if message_id is not None else None,
        uploaded_at=float(uploaded_at) if uploaded_at is not None else time.time(),
    )
    with _STATE_LOCK:
        intake = _SESSION_STATE.setdefault(key, SessionDraftIntake())
        intake.photo_batches.append(entry)
        if len(intake.photo_batches) > _MAX_PHOTO_BATCHES:
            intake.photo_batches = intake.photo_batches[-_MAX_PHOTO_BATCHES:]
    return deepcopy(entry)



def add_pending_photo_batch(
    session_key: str | None,
    *,
    image_paths: Iterable[str],
    message_id: str | None = None,
    uploaded_at: float | None = None,
) -> PendingDraftPhotoBatch | None:
    key = _normalize_session_key(session_key)
    if not key:
        return None
    entry = PendingDraftPhotoBatch(
        image_paths=_normalize_paths(image_paths),
        message_id=str(message_id) if message_id is not None else None,
        uploaded_at=float(uploaded_at) if uploaded_at is not None else time.time(),
    )
    with _STATE_LOCK:
        intake = _SESSION_STATE.setdefault(key, SessionDraftIntake())
        intake.pending_photo_batches.append(entry)
        if len(intake.pending_photo_batches) > _MAX_PHOTO_BATCHES:
            intake.pending_photo_batches = intake.pending_photo_batches[-_MAX_PHOTO_BATCHES:]
    return deepcopy(entry)



def assign_pending_photo_batches_to_tag(
    session_key: str | None,
    *,
    tag: str,
    message_id: str | None = None,
    tagged_at: float | None = None,
) -> list[DraftPhotoBatch]:
    key = _normalize_session_key(session_key)
    normalized_tag = str(tag or "").strip()
    if not key or not normalized_tag:
        return []

    with _STATE_LOCK:
        intake = _SESSION_STATE.setdefault(key, SessionDraftIntake())
        pending = list(intake.pending_photo_batches)
        intake.pending_photo_batches = []
        assigned: list[DraftPhotoBatch] = []
        for batch in pending:
            tagged_batch = DraftPhotoBatch(
                tag=normalized_tag,
                image_paths=list(batch.image_paths),
                message_id=str(message_id) if message_id is not None else batch.message_id,
                uploaded_at=float(tagged_at) if tagged_at is not None else batch.uploaded_at,
            )
            intake.photo_batches.append(tagged_batch)
            assigned.append(tagged_batch)
        if len(intake.photo_batches) > _MAX_PHOTO_BATCHES:
            intake.photo_batches = intake.photo_batches[-_MAX_PHOTO_BATCHES:]
            assigned = intake.photo_batches[-len(assigned):] if assigned else []
    return deepcopy(assigned)



def clear_session_draft_intake(session_key: str | None) -> bool:
    key = _normalize_session_key(session_key)
    if not key:
        return False
    with _STATE_LOCK:
        return _SESSION_STATE.pop(key, None) is not None
