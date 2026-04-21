from argparse import Namespace

import pytest

from hermes_cli.config import read_raw_config


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    # Keep these tests hermetic even when the developer machine has a real,
    # logged-in NotebookLM profile. Tests that care about lookup behavior
    # override this default per-case.
    from hermes_cli.notebooklm import NotebookLookupUnavailable

    def _lookup_unavailable(notebook, profile="default"):
        raise NotebookLookupUnavailable("isolated test")

    monkeypatch.setattr(
        "hermes_cli.gateway_topic.resolve_notebook_reference",
        _lookup_unavailable,
    )



def _args(action, **overrides):
    defaults = {
        "topic_action": action,
        "target": None,
        "platform": None,
        "label": "",
        "notebook": "",
        "profile": "default",
        "free_response": False,
        "json": False,
    }
    defaults.update(overrides)
    return Namespace(**defaults)



def test_bind_writes_exact_topic_route_for_topic_478(capsys):
    from hermes_cli.gateway_topic import topic_command

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            label="NLM Lab",
            notebook="NLM Lab / 제국 운영",
            free_response=True,
        )
    )

    cfg = read_raw_config()
    route = cfg["gateway"]["topic_routes"]["telegram"]["-1003586456169:478"]

    assert route == {
        "label": "NLM Lab",
        "mode": "notebooklm",
        "notebook": "NLM Lab / 제국 운영",
        "free_response": True,
        "ignored": False,
    }
    assert "telegram:-1003586456169:478" in capsys.readouterr().out



def test_bind_resolves_notebook_id_when_lookup_succeeds(monkeypatch):
    from hermes_cli.gateway_topic import topic_command

    monkeypatch.setattr(
        "hermes_cli.gateway_topic.resolve_notebook_reference",
        lambda notebook, profile="default": {"id": "nb-478", "title": notebook},
    )

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            label="NLM Lab",
            notebook="NLM Lab / 제국 운영",
        )
    )

    cfg = read_raw_config()
    route = cfg["gateway"]["topic_routes"]["telegram"]["-1003586456169:478"]

    assert route["notebook_id"] == "nb-478"



def test_bind_uses_requested_notebooklm_profile(monkeypatch):
    from hermes_cli.gateway_topic import topic_command

    recorded = {}

    def _resolve(notebook, profile="default"):
        recorded["notebook"] = notebook
        recorded["profile"] = profile
        return {"id": "nb-478", "title": notebook}

    monkeypatch.setattr("hermes_cli.gateway_topic.resolve_notebook_reference", _resolve)

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            notebook="NLM Lab / 제국 운영",
            profile="nlm-lab",
        )
    )

    assert recorded == {
        "notebook": "NLM Lab / 제국 운영",
        "profile": "nlm-lab",
    }



def test_bind_rejects_unknown_notebook_name(monkeypatch):
    from hermes_cli.gateway_topic import topic_command

    def _raise(notebook, profile="default"):
        raise ValueError("Notebook not found: missing")

    monkeypatch.setattr("hermes_cli.gateway_topic.resolve_notebook_reference", _raise)

    with pytest.raises(SystemExit):
        topic_command(
            _args(
                "bind",
                target="telegram:-1003586456169:478",
                notebook="missing",
            )
        )



def test_list_json_returns_bound_routes(capsys):
    from hermes_cli.gateway_topic import topic_command

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            label="NLM Lab",
            notebook="NLM Lab / 제국 운영",
            free_response=True,
        )
    )
    capsys.readouterr()

    topic_command(_args("list", platform="telegram", json=True))
    out = capsys.readouterr().out

    assert '"target": "telegram:-1003586456169:478"' in out
    assert '"free_response": true' in out



def test_ignore_then_unignore_toggles_route_flag():
    from hermes_cli.gateway_topic import topic_command

    topic_command(_args("bind", target="telegram:-1003586456169:478"))
    topic_command(_args("ignore", target="telegram:-1003586456169:478"))

    cfg = read_raw_config()
    assert cfg["gateway"]["topic_routes"]["telegram"]["-1003586456169:478"]["ignored"] is True

    topic_command(_args("unignore", target="telegram:-1003586456169:478"))

    cfg = read_raw_config()
    assert cfg["gateway"]["topic_routes"]["telegram"]["-1003586456169:478"]["ignored"] is False



def test_test_command_reports_effective_route(capsys):
    from hermes_cli.gateway_topic import topic_command

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            label="NLM Lab",
            notebook="NLM Lab / 제국 운영",
            free_response=True,
        )
    )
    capsys.readouterr()

    topic_command(_args("test", target="telegram:-1003586456169:478"))
    out = capsys.readouterr().out

    assert "telegram:-1003586456169:478" in out
    assert "free_response=True" in out
    assert "notebook=NLM Lab / 제국 운영" in out



def test_unbind_removes_route():
    from hermes_cli.gateway_topic import topic_command

    topic_command(_args("bind", target="telegram:-1003586456169:478"))
    topic_command(_args("unbind", target="telegram:-1003586456169:478"))

    cfg = read_raw_config()
    telegram_routes = cfg.get("gateway", {}).get("topic_routes", {}).get("telegram", {})
    assert "-1003586456169:478" not in telegram_routes



def test_unignore_does_not_create_phantom_route():
    from hermes_cli.gateway_topic import topic_command

    topic_command(_args("unignore", target="telegram:-1003586456169:478"))

    cfg = read_raw_config()
    telegram_routes = cfg.get("gateway", {}).get("topic_routes", {}).get("telegram", {})
    assert "-1003586456169:478" not in telegram_routes



def test_invalid_exact_target_is_rejected():
    from hermes_cli.gateway_topic import parse_exact_target

    with pytest.raises(ValueError):
        parse_exact_target("telegram:-1003586456169")



def test_parse_exact_target_canonicalizes_platform_and_thread_id():
    from hermes_cli.gateway_topic import parse_exact_target

    assert parse_exact_target("Telegram:-1003586456169:0478") == (
        "telegram",
        "-1003586456169",
        "478",
    )



def test_parse_exact_target_rejects_non_telegram_platform():
    from hermes_cli.gateway_topic import parse_exact_target

    with pytest.raises(ValueError):
        parse_exact_target("discord:123:478")



def test_bind_keeps_notebook_title_when_lookup_command_fails(monkeypatch):
    from hermes_cli.gateway_topic import topic_command
    from hermes_cli.notebooklm import NotebookCommandError

    def _raise(notebook, profile="default"):
        raise NotebookCommandError("NotebookLM command failed")

    monkeypatch.setattr("hermes_cli.gateway_topic.resolve_notebook_reference", _raise)

    topic_command(
        _args(
            "bind",
            target="telegram:-1003586456169:478",
            label="NLM Lab",
            notebook="NLM Lab / 제국 운영",
        )
    )

    cfg = read_raw_config()
    route = cfg["gateway"]["topic_routes"]["telegram"]["-1003586456169:478"]
    assert route["notebook"] == "NLM Lab / 제국 운영"
    assert "notebook_id" not in route
