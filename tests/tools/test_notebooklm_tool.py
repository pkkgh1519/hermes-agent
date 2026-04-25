import json

from gateway.session_context import clear_session_vars, set_session_vars


def _set_bound_notebook_context():
    return set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        chat_name="AGI Jarvis",
        thread_id="478",
        user_id="111",
        user_name="Kim",
        session_key="sess-1",
        route_target="telegram:-1003586456169:478",
        route_label="NLM Lab",
        route_mode="notebooklm",
        route_notebook="NLM Lab / 제국 운영",
        route_notebook_id="nb-478",
    )



def test_status_includes_bound_route_notebook(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "collect_status",
        lambda profile="default": {"status": "ready", "logged_in": True, "profile": profile},
    )

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="status"))
    finally:
        clear_session_vars(tokens)

    assert payload["status"] == "ready"
    assert payload["logged_in"] is True
    assert payload["bound_notebook"] == {
        "notebook": "NLM Lab / 제국 운영",
        "notebook_id": "nb-478",
        "route_target": "telegram:-1003586456169:478",
        "route_mode": "notebooklm",
    }



def test_resolve_defaults_to_route_bound_notebook():
    import tools.notebooklm_tool as notebooklm_tool_mod

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="resolve"))
    finally:
        clear_session_vars(tokens)

    assert payload == {
        "notebook": "NLM Lab / 제국 운영",
        "notebook_id": "nb-478",
        "source": "session-route",
    }



def test_ask_uses_bound_notebook_id_by_default(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    recorded = {}

    def fake_ask_notebook(question, *, notebook_id=None, profile="default"):
        recorded["question"] = question
        recorded["notebook_id"] = notebook_id
        recorded["profile"] = profile
        return {
            "answer": "요약 답변",
            "conversation_id": "conv-1",
            "references": [{"source_id": "src-1"}],
        }

    monkeypatch.setattr(notebooklm_tool_mod, "ask_notebook", fake_ask_notebook)

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(
            notebooklm_tool_mod.notebooklm_tool(action="ask", question="이번 주 변경점 뭐야?")
        )
    finally:
        clear_session_vars(tokens)

    assert recorded == {
        "question": "이번 주 변경점 뭐야?",
        "notebook_id": "nb-478",
        "profile": "default",
    }
    assert payload["notebook"] == "NLM Lab / 제국 운영"
    assert payload["notebook_id"] == "nb-478"
    assert payload["answer"] == "요약 답변"
    assert payload["conversation_id"] == "conv-1"
    assert payload["references"] == [{"source_id": "src-1"}]



def test_list_returns_notebooks_from_helper(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "list_notebooks",
        lambda profile="default": [
            {"id": "nb-478", "title": "NLM Lab / 제국 운영"},
            {"id": "nb-999", "title": "Other"},
        ],
    )

    payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="list"))

    assert payload["count"] == 2
    assert payload["notebooks"] == [
        {"id": "nb-478", "title": "NLM Lab / 제국 운영"},
        {"id": "nb-999", "title": "Other"},
    ]



def test_ask_requires_question():
    import tools.notebooklm_tool as notebooklm_tool_mod

    payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="ask"))

    assert payload["error"] == "question is required for action='ask'"



def test_ask_without_bound_notebook_or_id_returns_structured_error():
    import tools.notebooklm_tool as notebooklm_tool_mod

    payload = json.loads(
        notebooklm_tool_mod.notebooklm_tool(action="ask", question="요약해줘")
    )

    assert (
        payload["error"]
        == "No notebook_id is available. Provide notebook_id explicitly or bind/resolve the notebook first."
    )



def test_metadata_defaults_to_route_bound_notebook(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "get_notebook_metadata",
        lambda notebook_id=None, profile="default": {
            "id": notebook_id,
            "title": "NLM Lab / 제국 운영",
        },
    )

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="metadata"))
    finally:
        clear_session_vars(tokens)

    assert payload["id"] == "nb-478"
    assert payload["title"] == "NLM Lab / 제국 운영"
    assert payload["notebook_id"] == "nb-478"



def test_metadata_resolves_title_only_bound_route(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "resolve_notebook_reference",
        lambda notebook, profile="default": {"id": "nb-478", "title": notebook},
    )
    monkeypatch.setattr(
        notebooklm_tool_mod,
        "get_notebook_metadata",
        lambda notebook_id=None, profile="default": {
            "id": notebook_id,
            "title": "NLM Lab / 제국 운영",
        },
    )

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        chat_name="AGI Jarvis",
        thread_id="478",
        user_id="111",
        user_name="Kim",
        session_key="sess-1",
        route_target="telegram:-1003586456169:478",
        route_label="NLM Lab",
        route_mode="notebooklm",
        route_notebook="NLM Lab / 제국 운영",
        route_notebook_id="",
    )
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="metadata"))
    finally:
        clear_session_vars(tokens)

    assert payload["id"] == "nb-478"
    assert payload["notebook"] == "NLM Lab / 제국 운영"
    assert payload["notebook_id"] == "nb-478"



def test_ask_resolves_title_only_bound_route(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    recorded = {}

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "resolve_notebook_reference",
        lambda notebook, profile="default": {"id": "nb-478", "title": notebook},
    )

    def fake_ask_notebook(question, *, notebook_id=None, profile="default"):
        recorded["question"] = question
        recorded["notebook_id"] = notebook_id
        recorded["profile"] = profile
        return {"answer": "ok"}

    monkeypatch.setattr(notebooklm_tool_mod, "ask_notebook", fake_ask_notebook)

    tokens = set_session_vars(
        platform="telegram",
        chat_id="-1003586456169",
        chat_name="AGI Jarvis",
        thread_id="478",
        user_id="111",
        user_name="Kim",
        session_key="sess-1",
        route_target="telegram:-1003586456169:478",
        route_label="NLM Lab",
        route_mode="notebooklm",
        route_notebook="NLM Lab / 제국 운영",
        route_notebook_id="",
    )
    try:
        payload = json.loads(
            notebooklm_tool_mod.notebooklm_tool(action="ask", question="요약해줘")
        )
    finally:
        clear_session_vars(tokens)

    assert recorded == {
        "question": "요약해줘",
        "notebook_id": "nb-478",
        "profile": "default",
    }
    assert payload["notebook_id"] == "nb-478"
    assert payload["answer"] == "ok"



def test_resolve_rejects_conflicting_notebook_and_notebook_id(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "resolve_notebook_reference",
        lambda notebook, profile="default": {"id": "nb-other", "title": notebook},
    )

    payload = json.loads(
        notebooklm_tool_mod.notebooklm_tool(
            action="resolve",
            notebook="Other Notebook",
            notebook_id="nb-478",
        )
    )

    assert payload["error"] == "notebook and notebook_id refer to different notebooks"



def test_resolve_rejects_conflicting_notebook_when_lookup_is_unavailable(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "resolve_notebook_reference",
        lambda notebook, profile="default": (_ for _ in ()).throw(
            notebooklm_tool_mod.NotebookLookupUnavailable("NotebookLM is not installed")
        ),
    )

    payload = json.loads(
        notebooklm_tool_mod.notebooklm_tool(
            action="resolve",
            notebook="Other Notebook",
            notebook_id="nb-478",
        )
    )

    assert payload["error"] == (
        "Cannot validate notebook title against notebook_id because NotebookLM lookup is unavailable"
    )



def test_source_list_uses_route_bound_notebook(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "list_sources",
        lambda notebook_id=None, profile="default": [{"id": "src-1", "title": "RFC"}],
    )

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="source_list"))
    finally:
        clear_session_vars(tokens)

    assert payload["sources"] == [{"id": "src-1", "title": "RFC"}]
    assert payload["count"] == 1
    assert payload["notebook_id"] == "nb-478"



def test_source_add_uses_bound_notebook(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "add_source",
        lambda notebook_id=None, source_type=None, content=None, profile="default", mime_type=None: {
            "source": {"id": "src-1", "title": content, "type": source_type, "mime_type": mime_type}
        },
    )

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(
            notebooklm_tool_mod.notebooklm_tool(
                action="source_add",
                source_type="url",
                content="https://example.com",
            )
        )
    finally:
        clear_session_vars(tokens)

    assert payload["notebook_id"] == "nb-478"
    assert payload["source"] == {
        "id": "src-1",
        "title": "https://example.com",
        "type": "url",
        "mime_type": None,
    }



def test_source_add_supports_file_for_bound_notebook(monkeypatch, tmp_path):
    import tools.notebooklm_tool as notebooklm_tool_mod

    recorded = {}
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"%PDF-test")

    def fake_add_source(notebook_id=None, source_type=None, content=None, profile="default", mime_type=None):
        recorded["notebook_id"] = notebook_id
        recorded["source_type"] = source_type
        recorded["content"] = content
        recorded["profile"] = profile
        recorded["mime_type"] = mime_type
        return {"source": {"id": "src-1", "title": content, "type": source_type}}

    monkeypatch.setattr(notebooklm_tool_mod, "add_source", fake_add_source)

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(
            notebooklm_tool_mod.notebooklm_tool(
                action="source_add",
                source_type="file",
                content=str(file_path),
                mime_type="application/pdf",
            )
        )
    finally:
        clear_session_vars(tokens)

    assert recorded == {
        "notebook_id": "nb-478",
        "source_type": "file",
        "content": str(file_path),
        "profile": "default",
        "mime_type": "application/pdf",
    }
    assert payload["notebook_id"] == "nb-478"
    assert payload["source"] == {
        "id": "src-1",
        "title": str(file_path),
        "type": "file",
    }



def test_source_add_rejects_non_cache_file_for_telegram_session(tmp_path, monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    outside_path = tmp_path / "outside.pdf"
    outside_path.write_bytes(b"%PDF-test")

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(
            notebooklm_tool_mod.notebooklm_tool(
                action="source_add",
                source_type="file",
                content=str(outside_path),
            )
        )
    finally:
        clear_session_vars(tokens)

    assert "allowed roots" in payload["error"]



def test_notebooklm_schema_exposes_file_source_and_mime_type():
    import tools.notebooklm_tool as notebooklm_tool_mod

    properties = notebooklm_tool_mod.NOTEBOOKLM_SCHEMA["parameters"]["properties"]

    assert properties["source_type"]["enum"] == ["url", "text", "file"]
    assert properties["mime_type"]["type"] == "string"



def test_source_add_requires_source_type_and_content():
    import tools.notebooklm_tool as notebooklm_tool_mod

    payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="source_add"))

    assert payload["error"] == "source_type and content are required for action='source_add'"



def test_source_add_rejects_whitespace_only_content():
    import tools.notebooklm_tool as notebooklm_tool_mod

    payload = json.loads(
        notebooklm_tool_mod.notebooklm_tool(
            action="source_add",
            source_type="text",
            content="   ",
        )
    )

    assert payload["error"] == "source_type and content are required for action='source_add'"



def test_metadata_ignores_conflicting_payload_notebook_keys(monkeypatch):
    import tools.notebooklm_tool as notebooklm_tool_mod

    monkeypatch.setattr(
        notebooklm_tool_mod,
        "get_notebook_metadata",
        lambda notebook_id=None, profile="default": {
            "id": notebook_id,
            "title": "NLM Lab / 제국 운영",
            "notebook": "wrong-title",
            "notebook_id": "wrong-id",
        },
    )

    tokens = _set_bound_notebook_context()
    try:
        payload = json.loads(notebooklm_tool_mod.notebooklm_tool(action="metadata"))
    finally:
        clear_session_vars(tokens)

    assert payload["notebook"] == "NLM Lab / 제국 운영"
    assert payload["notebook_id"] == "nb-478"
    assert payload["title"] == "NLM Lab / 제국 운영"
