from types import SimpleNamespace
from unittest.mock import AsyncMock

from gateway.config import Platform, PlatformConfig, load_gateway_config



def _make_adapter(require_mention=None, free_response_chats=None, topic_routes=None, ignored_threads=None):
    from gateway.platforms.telegram import TelegramAdapter

    extra = {}
    if require_mention is not None:
        extra["require_mention"] = require_mention
    if free_response_chats is not None:
        extra["free_response_chats"] = free_response_chats
    if topic_routes is not None:
        extra["topic_routes"] = topic_routes
    if ignored_threads is not None:
        extra["ignored_threads"] = ignored_threads

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="***", extra=extra)
    adapter._bot = SimpleNamespace(id=999, username="hermes_bot")
    adapter._message_handler = AsyncMock()
    adapter._pending_text_batches = {}
    adapter._pending_text_batch_tasks = {}
    adapter._text_batch_delay_seconds = 0.01
    adapter._mention_patterns = []
    return adapter



def _group_message(text="hello", *, chat_id=-1003586456169, thread_id=478):
    return SimpleNamespace(
        text=text,
        caption=None,
        entities=[],
        caption_entities=[],
        message_thread_id=thread_id,
        chat=SimpleNamespace(id=chat_id, type="group"),
        reply_to_message=None,
    )



def test_exact_topic_route_free_response_bypasses_mention_requirement():
    adapter = _make_adapter(
        require_mention=True,
        topic_routes={
            "-1003586456169:478": {
                "free_response": True,
                "ignored": False,
                "notebook": "NLM Lab / 제국 운영",
            }
        },
    )

    assert adapter._should_process_message(_group_message("hello everyone")) is True



def test_exact_topic_route_ignore_beats_chat_allowlist_and_open_group_rules():
    adapter = _make_adapter(
        require_mention=False,
        free_response_chats=["-1003586456169"],
        topic_routes={
            "-1003586456169:478": {
                "free_response": False,
                "ignored": True,
            }
        },
        ignored_threads=[99],
    )

    assert adapter._should_process_message(_group_message("hello everyone")) is False



def test_exact_topic_route_is_chat_specific_even_with_same_thread_id():
    adapter = _make_adapter(
        require_mention=True,
        topic_routes={
            "-1003586456169:478": {
                "free_response": True,
                "ignored": False,
            }
        },
    )

    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-1003586456169, thread_id=478)) is True
    assert adapter._should_process_message(_group_message("hello everyone", chat_id=-1009999999999, thread_id=478)) is False



def test_exact_topic_route_overrides_legacy_ignored_threads():
    adapter = _make_adapter(
        require_mention=True,
        topic_routes={
            "-1003586456169:478": {
                "free_response": False,
                "ignored": False,
            }
        },
        ignored_threads=[478],
    )
    adapter._message_mentions_bot = lambda message: True
    adapter._is_reply_to_bot = lambda message: False
    adapter._message_matches_mention_patterns = lambda message: False

    assert adapter._should_process_message(_group_message("@hermes_bot hello")) is True



def test_exact_topic_route_overrides_legacy_free_response_threads():
    adapter = _make_adapter(
        require_mention=True,
        topic_routes={
            "-1003586456169:478": {
                "free_response": False,
                "ignored": False,
            }
        },
        free_response_chats=[],
    )
    adapter.config.extra["free_response_threads"] = [478]
    adapter._message_mentions_bot = lambda message: False
    adapter._is_reply_to_bot = lambda message: False
    adapter._message_matches_mention_patterns = lambda message: False

    assert adapter._should_process_message(_group_message("hello everyone")) is False



def test_build_message_event_attaches_exact_route_notebook_metadata():
    from gateway.platforms import telegram as telegram_mod

    adapter = _make_adapter(
        require_mention=True,
        topic_routes={
            "-1003586456169:478": {
                "label": "NLM Lab",
                "mode": "notebooklm",
                "notebook": "NLM Lab / 제국 운영",
                "notebook_id": "nb-478",
                "free_response": True,
                "ignored": False,
            }
        },
    )
    adapter._dm_topics = {}
    adapter._dm_topics_config = []

    message = SimpleNamespace(
        text="hello everyone",
        caption=None,
        entities=[],
        caption_entities=[],
        message_thread_id=478,
        chat=SimpleNamespace(id=-1003586456169, type=telegram_mod.ChatType.SUPERGROUP, is_forum=True, title="AGI Jarvis"),
        from_user=SimpleNamespace(id=111, full_name="Kim"),
        reply_to_message=None,
        message_id=10,
        date=None,
    )

    event = adapter._build_message_event(message, msg_type=SimpleNamespace(value="text"))

    assert event.route_target == "telegram:-1003586456169:478"
    assert event.route_label == "NLM Lab"
    assert event.route_mode == "notebooklm"
    assert event.route_notebook == "NLM Lab / 제국 운영"
    assert event.route_notebook_id == "nb-478"
    assert event.source.route_target == "telegram:-1003586456169:478"
    assert event.source.route_label == "NLM Lab"
    assert event.source.route_mode == "notebooklm"
    assert event.source.route_notebook == "NLM Lab / 제국 운영"
    assert event.source.route_notebook_id == "nb-478"



def test_exact_topic_route_matches_general_forum_topic():
    from gateway.platforms import telegram as telegram_mod

    adapter = _make_adapter(
        require_mention=False,
        topic_routes={
            "-1003586456169:1": {
                "label": "General",
                "mode": "notebooklm",
                "notebook": "NLM Lab / General",
                "free_response": True,
                "ignored": False,
            }
        },
    )
    adapter._dm_topics = {}
    adapter._dm_topics_config = []

    message = SimpleNamespace(
        text="hello everyone",
        caption=None,
        entities=[],
        caption_entities=[],
        message_thread_id=None,
        chat=SimpleNamespace(id=-1003586456169, type=telegram_mod.ChatType.SUPERGROUP, is_forum=True, title="AGI Jarvis"),
        from_user=SimpleNamespace(id=111, full_name="Kim"),
        reply_to_message=None,
        message_id=10,
        date=None,
    )

    assert adapter._should_process_message(message) is True
    event = adapter._build_message_event(message, msg_type=SimpleNamespace(value="text"))
    assert event.source.thread_id == "1"
    assert event.source.route_target == "telegram:-1003586456169:1"



def test_config_topic_route_keys_are_canonicalized_for_lookup():
    adapter = _make_adapter(
        require_mention=False,
        topic_routes={
            "-1003586456169:0478": {
                "free_response": True,
                "ignored": False,
            }
        },
    )

    assert adapter._should_process_message(_group_message("hello everyone", thread_id=478)) is True



def test_config_bridges_gateway_topic_routes_into_telegram_extra(monkeypatch, tmp_path):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "gateway:\n"
        "  topic_routes:\n"
        "    telegram:\n"
        "      \"-1003586456169:478\":\n"
        "        label: \"NLM Lab\"\n"
        "        mode: \"notebooklm\"\n"
        "        notebook: \"NLM Lab / 제국 운영\"\n"
        "        free_response: true\n"
        "        ignored: false\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")

    config = load_gateway_config()
    telegram_extra = config.platforms[Platform.TELEGRAM].extra

    assert telegram_extra["topic_routes"]["-1003586456169:478"] == {
        "label": "NLM Lab",
        "mode": "notebooklm",
        "notebook": "NLM Lab / 제국 운영",
        "free_response": True,
        "ignored": False,
    }
