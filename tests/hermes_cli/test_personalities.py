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
