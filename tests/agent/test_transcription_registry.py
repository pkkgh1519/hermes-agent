"""Tests for agent/transcription_registry.py — provider registration & lookup."""

from __future__ import annotations

import pytest

from agent import transcription_registry
from agent.transcription_provider import TranscriptionProvider


class _FakeProvider(TranscriptionProvider):
    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, file_path, *, model=None, language=None, **kwargs):
        return {"success": True, "transcript": f"{self._name}:{file_path}", "provider": self._name}


@pytest.fixture(autouse=True)
def _reset_registry():
    transcription_registry._reset_for_tests()
    yield
    transcription_registry._reset_for_tests()


class TestRegisterProvider:
    def test_register_and_lookup(self):
        provider = _FakeProvider("fake")
        transcription_registry.register_provider(provider)
        assert transcription_registry.get_provider("fake") is provider

    def test_rejects_non_provider(self):
        with pytest.raises(TypeError):
            transcription_registry.register_provider("not a provider")  # type: ignore[arg-type]

    def test_rejects_empty_name(self):
        class Empty(TranscriptionProvider):
            @property
            def name(self) -> str:
                return ""

            def transcribe(self, file_path, *, model=None, language=None, **kwargs):
                return {}

        with pytest.raises(ValueError):
            transcription_registry.register_provider(Empty())

    def test_reregister_overwrites(self):
        a = _FakeProvider("same")
        b = _FakeProvider("same")
        transcription_registry.register_provider(a)
        transcription_registry.register_provider(b)
        assert transcription_registry.get_provider("same") is b

    def test_list_is_sorted(self):
        transcription_registry.register_provider(_FakeProvider("zeta"))
        transcription_registry.register_provider(_FakeProvider("alpha"))
        names = [p.name for p in transcription_registry.list_providers()]
        assert names == ["alpha", "zeta"]
