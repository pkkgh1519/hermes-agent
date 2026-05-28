"""
Transcription Provider ABC
==========================

Defines the pluggable-backend interface for speech-to-text providers.
Providers register instances via ``PluginContext.register_transcription_provider()``;
``tools.transcription_tools`` dispatches explicit non-built-in provider names to
this registry.

Unlike image/video generation, there is no global "active provider" resolver
here: STT routing still starts from ``stt.provider`` config and the built-in
provider chain. The registry is only for plugin providers selected explicitly
by name.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Optional


class TranscriptionProvider(abc.ABC):
    """Abstract base class for a pluggable STT backend."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier used in ``stt.provider`` config."""

    @property
    def display_name(self) -> str:
        """Human-readable label shown in setup UIs. Defaults to ``name.title()``."""
        return self.name.title()

    def is_available(self) -> bool:
        """Return True when this provider can service calls.

        Providers typically check for required API keys and optional SDKs.
        Default: True.
        """
        return True

    @abc.abstractmethod
    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Transcribe *file_path* and return the standard STT response dict.

        Expected success shape::

            {
              "success": True,
              "transcript": "...",
              "provider": "<name>",
              ...optional extra fields...
            }

        Expected failure shape::

            {
              "success": False,
              "transcript": "",
              "error": "...",
              "provider": "<name>",
              ...optional extra fields...
            }
        """
