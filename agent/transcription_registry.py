"""
Transcription Provider Registry
===============================

Central map of plugin-registered transcription providers. Populated by plugins
at import time via ``PluginContext.register_transcription_provider()`` and
consumed by ``tools.transcription_tools`` when ``stt.provider`` names a
non-built-in backend.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from agent.transcription_provider import TranscriptionProvider

logger = logging.getLogger(__name__)


_providers: Dict[str, TranscriptionProvider] = {}
_lock = threading.Lock()


def register_provider(provider: TranscriptionProvider) -> None:
    """Register a transcription provider."""
    if not isinstance(provider, TranscriptionProvider):
        raise TypeError(
            f"register_provider() expects a TranscriptionProvider instance, "
            f"got {type(provider).__name__}"
        )
    name = provider.name
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Transcription provider .name must be a non-empty string")
    with _lock:
        existing = _providers.get(name)
        _providers[name] = provider
    if existing is not None:
        logger.debug(
            "Transcription provider '%s' re-registered (was %r)",
            name,
            type(existing).__name__,
        )
    else:
        logger.debug("Registered transcription provider '%s' (%s)", name, type(provider).__name__)


def list_providers() -> List[TranscriptionProvider]:
    """Return all registered transcription providers, sorted by name."""
    with _lock:
        items = list(_providers.values())
    return sorted(items, key=lambda p: p.name)


def get_provider(name: str) -> Optional[TranscriptionProvider]:
    """Return the provider registered under *name*, or None."""
    if not isinstance(name, str):
        return None
    with _lock:
        return _providers.get(name.strip())


def _reset_for_tests() -> None:
    """Clear the registry. **Test-only.**"""
    with _lock:
        _providers.clear()
