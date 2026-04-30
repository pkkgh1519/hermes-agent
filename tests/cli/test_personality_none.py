"""Tests for /personality overlay activation and clearing."""
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ── CLI tests ──────────────────────────────────────────────────────────────

class TestCLIPersonalityOverlay:

    def _make_cli(self, personalities=None):
        from cli import HermesCLI
        cli = HermesCLI.__new__(HermesCLI)
        cli.personalities = personalities or {
            "helpful": "You are helpful.",
            "concise": "You are concise.",
        }
        cli.base_system_prompt = "Base operating rules."
        cli.system_prompt = "Base operating rules.\n\nYou are kawaii~"
        cli.agent = MagicMock()
        cli.console = MagicMock()
        return cli

    def test_none_clears_active_personality_but_preserves_base_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality none")
        assert cli.system_prompt == "Base operating rules."

    def test_default_clears_active_personality_but_preserves_base_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality default")
        assert cli.system_prompt == "Base operating rules."

    def test_neutral_clears_active_personality_but_preserves_base_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality neutral")
        assert cli.system_prompt == "Base operating rules."

    def test_none_forces_agent_reinit(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality none")
        assert cli.agent is None

    def test_none_saves_active_personality_to_config_not_system_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True) as mock_save:
            cli._handle_personality_command("/personality none")
        calls = [call.args for call in mock_save.call_args_list]
        assert ("agent.active_personality", "") in calls
        assert ("agent.system_prompt", "") not in calls

    def test_known_personality_composes_base_and_overlay(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True) as mock_save:
            cli._handle_personality_command("/personality helpful")
        assert cli.system_prompt == "Base operating rules.\n\nYou are helpful."
        calls = [call.args for call in mock_save.call_args_list]
        assert ("agent.active_personality", "helpful") in calls
        assert not any(call == ("agent.system_prompt", "You are helpful.") for call in calls)

    def test_unknown_personality_shows_none_in_available(self, capsys):
        cli = self._make_cli()
        cli._handle_personality_command("/personality nonexistent")
        output = capsys.readouterr().out
        assert "none" in output.lower()

    def test_list_shows_none_option(self):
        cli = self._make_cli()
        with patch("builtins.print") as mock_print:
            cli._handle_personality_command("/personality")
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "none" in output.lower()


# ── Gateway tests ──────────────────────────────────────────────────────────

class TestGatewayPersonalityOverlay:

    def _make_event(self, args=""):
        event = MagicMock()
        event.get_command.return_value = "personality"
        event.get_command_args.return_value = args
        return event

    def _make_runner(self, personalities=None):
        from gateway.run import GatewayRunner
        runner = GatewayRunner.__new__(GatewayRunner)
        runner._ephemeral_system_prompt = "Base operating rules.\n\nYou are kawaii~"
        runner.config = {
            "agent": {
                "system_prompt": "Base operating rules.",
                "active_personality": "kawaii",
                "personalities": personalities or {"helpful": "You are helpful."},
            }
        }
        return runner

    @pytest.mark.asyncio
    async def test_none_preserves_configured_base_prompt(self, tmp_path):
        runner = self._make_runner()
        config_data = {
            "agent": {
                "personalities": {"helpful": "You are helpful."},
                "system_prompt": "Base operating rules.",
                "active_personality": "kawaii",
            }
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("none")
            result = await runner._handle_personality_command(event)

        saved = yaml.safe_load(config_file.read_text())
        assert runner._ephemeral_system_prompt == "Base operating rules."
        assert saved["agent"]["system_prompt"] == "Base operating rules."
        assert saved["agent"]["active_personality"] == ""
        assert "cleared" in result.lower()

    @pytest.mark.asyncio
    async def test_default_preserves_configured_base_prompt(self, tmp_path):
        runner = self._make_runner()
        config_data = {
            "agent": {
                "personalities": {"helpful": "You are helpful."},
                "system_prompt": "Base operating rules.",
                "active_personality": "helpful",
            }
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("default")
            await runner._handle_personality_command(event)

        saved = yaml.safe_load(config_file.read_text())
        assert runner._ephemeral_system_prompt == "Base operating rules."
        assert saved["agent"]["system_prompt"] == "Base operating rules."
        assert saved["agent"]["active_personality"] == ""

    @pytest.mark.asyncio
    async def test_set_personality_replaces_non_mapping_display_config(self, tmp_path):
        runner = self._make_runner()
        config_data = {
            "display": "legacy-invalid-value",
            "agent": {
                "personalities": {"helpful": "You are helpful."},
                "system_prompt": "Base operating rules.",
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("helpful")
            await runner._handle_personality_command(event)

        saved = yaml.safe_load(config_file.read_text())
        assert saved["display"] == {"personality": "helpful"}
        assert saved["agent"]["active_personality"] == "helpful"

    @pytest.mark.asyncio
    async def test_list_includes_none(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"personalities": {"helpful": "You are helpful."}}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("")
            result = await runner._handle_personality_command(event)

        assert "none" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_shows_none_in_available(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"personalities": {"helpful": "You are helpful."}}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("nonexistent")
            result = await runner._handle_personality_command(event)

        assert "none" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_personality_list_uses_profile_display_path(self, tmp_path):
        runner = self._make_runner(personalities={})
        (tmp_path / "config.yaml").write_text(yaml.dump({"agent": {"personalities": {}}}))

        with patch("gateway.run._hermes_home", tmp_path), \
             patch("hermes_constants.display_hermes_home", return_value="~/.hermes/profiles/coder"):
            event = self._make_event("")
            result = await runner._handle_personality_command(event)

        assert "No personalities configured" not in result
        assert "`concise`" in result
        assert "`pirate`" in result

    @pytest.mark.asyncio
    async def test_builtin_personality_sets_active_personality_and_composes_prompt(self, tmp_path):
        runner = self._make_runner(personalities={})
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"agent": {"system_prompt": "Base operating rules.", "personalities": {}}}))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("concise")
            result = await runner._handle_personality_command(event)

        saved = yaml.safe_load(config_file.read_text())
        assert "Personality set" in result
        assert runner._ephemeral_system_prompt.startswith("Base operating rules.\n\n")
        assert "concise assistant" in runner._ephemeral_system_prompt
        assert saved["agent"]["system_prompt"] == "Base operating rules."
        assert saved["agent"]["active_personality"] == "concise"

    @pytest.mark.asyncio
    async def test_none_clears_active_personality_without_custom_personalities(self, tmp_path):
        runner = self._make_runner(personalities={})
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"agent": {"personalities": {}, "system_prompt": "Base operating rules.", "active_personality": "kawaii"}}))

        with patch("gateway.run._hermes_home", tmp_path):
            event = self._make_event("none")
            result = await runner._handle_personality_command(event)

        saved = yaml.safe_load(config_file.read_text())
        assert "cleared" in result.lower()
        assert runner._ephemeral_system_prompt == "Base operating rules."
        assert saved["agent"]["system_prompt"] == "Base operating rules."
        assert saved["agent"]["active_personality"] == ""


class TestPersonalityDictFormat:
    """Test dict-format custom personalities with description, tone, style."""

    def _make_cli(self, personalities):
        from cli import HermesCLI
        cli = HermesCLI.__new__(HermesCLI)
        cli.personalities = personalities
        cli.base_system_prompt = "Base operating rules."
        cli.system_prompt = "Base operating rules."
        cli.agent = None
        cli.console = MagicMock()
        return cli

    def test_dict_personality_uses_system_prompt(self):
        cli = self._make_cli({
            "coder": {
                "description": "Expert programmer",
                "system_prompt": "You are an expert programmer.",
                "tone": "technical",
                "style": "concise",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality coder")
        assert "You are an expert programmer." in cli.system_prompt

    def test_dict_personality_includes_tone(self):
        cli = self._make_cli({
            "coder": {
                "system_prompt": "You are an expert programmer.",
                "tone": "technical and precise",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality coder")
        assert "Tone: technical and precise" in cli.system_prompt

    def test_dict_personality_includes_style(self):
        cli = self._make_cli({
            "coder": {
                "system_prompt": "You are an expert programmer.",
                "style": "use code examples",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality coder")
        assert "Style: use code examples" in cli.system_prompt

    def test_string_personality_still_works(self):
        cli = self._make_cli({"helper": "You are helpful."})
        with patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality helper")
        assert cli.system_prompt == "Base operating rules.\n\nYou are helpful."

    def test_resolve_prompt_dict_no_tone_no_style(self):
        from cli import HermesCLI
        result = HermesCLI._resolve_personality_prompt({
            "description": "A helper",
            "system_prompt": "You are helpful.",
        })
        assert result == "You are helpful."

    def test_resolve_prompt_string(self):
        from cli import HermesCLI
        result = HermesCLI._resolve_personality_prompt("You are helpful.")
        assert result == "You are helpful."
