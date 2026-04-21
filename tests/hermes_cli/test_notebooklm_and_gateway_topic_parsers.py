import sys


def test_notebooklm_doctor_routes_to_notebooklm_command(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_notebooklm(args):
        captured["command"] = args.command
        captured["notebooklm_command"] = args.notebooklm_command
        captured["json"] = args.json

    monkeypatch.setattr(main_mod, "cmd_notebooklm", fake_cmd_notebooklm, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "notebooklm", "doctor", "--json"],
    )

    main_mod.main()

    assert captured == {
        "command": "notebooklm",
        "notebooklm_command": "doctor",
        "json": True,
    }



def test_notebooklm_install_accepts_browser_flag(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_notebooklm(args):
        captured["notebooklm_command"] = args.notebooklm_command
        captured["browser"] = args.browser

    monkeypatch.setattr(main_mod, "cmd_notebooklm", fake_cmd_notebooklm, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "notebooklm", "install", "--browser"],
    )

    main_mod.main()

    assert captured == {
        "notebooklm_command": "install",
        "browser": True,
    }



def test_gateway_topic_bind_parses_exact_target_and_notebook_fields(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_gateway(args):
        captured["command"] = args.command
        captured["gateway_command"] = args.gateway_command
        captured["topic_action"] = args.topic_action
        captured["target"] = args.target
        captured["label"] = args.label
        captured["notebook"] = args.notebook
        captured["profile"] = args.profile
        captured["free_response"] = args.free_response

    monkeypatch.setattr(main_mod, "cmd_gateway", fake_cmd_gateway)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hermes",
            "gateway",
            "topic",
            "bind",
            "telegram:-1003586456169:478",
            "--label",
            "NLM Lab",
            "--notebook",
            "NLM Lab / 제국 운영",
            "--profile",
            "nlm-lab",
            "--free-response",
        ],
    )

    main_mod.main()

    assert captured == {
        "command": "gateway",
        "gateway_command": "topic",
        "topic_action": "bind",
        "target": "telegram:-1003586456169:478",
        "label": "NLM Lab",
        "notebook": "NLM Lab / 제국 운영",
        "profile": "nlm-lab",
        "free_response": True,
    }



def test_gateway_topic_list_accepts_platform_filter_and_json(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_gateway(args):
        captured["gateway_command"] = args.gateway_command
        captured["topic_action"] = args.topic_action
        captured["platform"] = args.platform
        captured["json"] = args.json

    monkeypatch.setattr(main_mod, "cmd_gateway", fake_cmd_gateway)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "gateway", "topic", "list", "telegram", "--json"],
    )

    main_mod.main()

    assert captured == {
        "gateway_command": "topic",
        "topic_action": "list",
        "platform": "telegram",
        "json": True,
    }



def test_gateway_topic_test_uses_user_supplied_topic_478(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_gateway(args):
        captured["gateway_command"] = args.gateway_command
        captured["topic_action"] = args.topic_action
        captured["target"] = args.target

    monkeypatch.setattr(main_mod, "cmd_gateway", fake_cmd_gateway)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "gateway", "topic", "test", "telegram:-1003586456169:478"],
    )

    main_mod.main()

    assert captured == {
        "gateway_command": "topic",
        "topic_action": "test",
        "target": "telegram:-1003586456169:478",
    }
