"""Tests for shared personality preset helpers."""


def test_builtin_personalities_include_documented_presets():
    from hermes_cli.personalities import BUILTIN_PERSONALITIES

    assert list(BUILTIN_PERSONALITIES) == [
        "helpful",
        "concise",
        "technical",
        "creative",
        "teacher",
        "kawaii",
        "catgirl",
        "pirate",
        "shakespeare",
        "surfer",
        "noir",
        "uwu",
        "philosopher",
        "hype",
    ]


def test_available_personalities_merges_custom_with_builtins_and_custom_wins():
    from hermes_cli.personalities import available_personalities

    personalities = available_personalities(
        {
            "helpful": "Custom helpful prompt.",
            "codereviewer": "Review code carefully.",
        }
    )

    assert "concise" in personalities
    assert personalities["helpful"] == "Custom helpful prompt."
    assert personalities["codereviewer"] == "Review code carefully."


def test_render_personality_prompt_supports_dict_format():
    from hermes_cli.personalities import render_personality_prompt

    prompt = render_personality_prompt(
        {
            "system_prompt": "You are an expert programmer.",
            "tone": "technical and precise",
            "style": "concise",
        }
    )

    assert "You are an expert programmer." in prompt
    assert "Tone: technical and precise" in prompt
    assert "Style: concise" in prompt


def test_normalize_personality_name_clears_none_aliases():
    from hermes_cli.personalities import normalize_personality_name

    assert normalize_personality_name("") == ""
    assert normalize_personality_name("none") == ""
    assert normalize_personality_name("default") == ""
    assert normalize_personality_name("neutral") == ""
    assert normalize_personality_name("  BBChan  ") == "bbchan"


def test_compose_system_prompt_preserves_base_when_overlay_empty():
    from hermes_cli.personalities import compose_system_prompt

    assert compose_system_prompt("base rules", "") == "base rules"


def test_resolve_active_personality_prompt_uses_agent_active_not_display():
    from hermes_cli.personalities import resolve_active_personality_prompt
    cfg = {
        "display": {"personality": "kawaii"},
        "agent": {
            "active_personality": "",
            "personalities": {"bbchan": "BB overlay"},
        },
    }

    name, prompt = resolve_active_personality_prompt(cfg)

    assert name == ""
    assert prompt == ""


def test_compose_config_system_prompt_combines_base_and_normalized_active_overlay():
    from hermes_cli.personalities import compose_config_system_prompt

    cfg = {
        "display": {"personality": "kawaii"},
        "agent": {
            "system_prompt": "base rules",
            "active_personality": "  BBCHAN  ",
            "personalities": {"bbchan": "BB overlay"},
        },
    }

    assert compose_config_system_prompt(cfg) == "base rules\n\nBB overlay"


def test_cli_config_merges_custom_personalities_with_builtins(tmp_path, monkeypatch):
    import cli

    (tmp_path / "config.yaml").write_text(
        """
agent:
  personalities:
    helpful: Custom helpful prompt.
    codereviewer: Review code carefully.
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_hermes_home", tmp_path)

    cfg = cli.load_cli_config()
    personalities = cfg["agent"]["personalities"]

    assert "concise" in personalities
    assert personalities["helpful"] == "Custom helpful prompt."
    assert personalities["codereviewer"] == "Review code carefully."


def test_tui_validate_personality_accepts_builtin_without_custom_config():
    from tui_gateway.server import _validate_personality

    name, prompt = _validate_personality("concise", {"agent": {"personalities": {}}})

    assert name == "concise"
    assert "concise assistant" in prompt
