import json
import uuid

from gateway.session_context import clear_session_vars, get_session_env, set_session_vars
import tools.terminal_tool as terminal_tool


def test_session_context_exposes_bound_notebook_route_vars():
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
        route_notebook_id="nb-478",
    )
    try:
        assert get_session_env("HERMES_SESSION_ROUTE_TARGET") == "telegram:-1003586456169:478"
        assert get_session_env("HERMES_SESSION_ROUTE_NOTEBOOK") == "NLM Lab / 제국 운영"
        assert get_session_env("HERMES_SESSION_ROUTE_NOTEBOOK_ID") == "nb-478"
    finally:
        clear_session_vars(tokens)



def test_terminal_tool_exports_bound_notebook_env_vars_to_shell(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "local")

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
        route_notebook_id="nb-478",
    )
    try:
        task_id = f"nb-env-{uuid.uuid4().hex[:8]}"
        result_json = terminal_tool.terminal_tool(
            command="python - <<'PY'\nimport os, json\nprint(json.dumps({\"route\": os.getenv(\"HERMES_SESSION_ROUTE_TARGET\"), \"notebook\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK\"), \"notebook_id\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK_ID\")}))\nPY",
            task_id=task_id,
            timeout=120,
        )
        result = json.loads(result_json)
        payload = json.loads(result["output"].strip())

        assert result["exit_code"] == 0
        assert payload == {
            "route": "telegram:-1003586456169:478",
            "notebook": "NLM Lab / 제국 운영",
            "notebook_id": "nb-478",
        }
    finally:
        clear_session_vars(tokens)
        terminal_tool.cleanup_vm(task_id)



def test_terminal_tool_clears_route_env_vars_on_reused_task(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "local")

    task_id = f"nb-env-clear-{uuid.uuid4().hex[:8]}"
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
        route_notebook_id="nb-478",
    )
    try:
        first = json.loads(
            terminal_tool.terminal_tool(
                command="python - <<'PY'\nimport os, json\nprint(json.dumps({\"route\": os.getenv(\"HERMES_SESSION_ROUTE_TARGET\"), \"notebook\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK\"), \"notebook_id\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK_ID\")}))\nPY",
                task_id=task_id,
                timeout=120,
            )
        )
        assert json.loads(first["output"].strip()) == {
            "route": "telegram:-1003586456169:478",
            "notebook": "NLM Lab / 제국 운영",
            "notebook_id": "nb-478",
        }
    finally:
        clear_session_vars(tokens)

    second = json.loads(
        terminal_tool.terminal_tool(
            command="python - <<'PY'\nimport os, json\nprint(json.dumps({\"route\": os.getenv(\"HERMES_SESSION_ROUTE_TARGET\"), \"notebook\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK\"), \"notebook_id\": os.getenv(\"HERMES_NOTEBOOKLM_NOTEBOOK_ID\")}))\nPY",
            task_id=task_id,
            timeout=120,
        )
    )
    try:
        assert json.loads(second["output"].strip()) == {
            "route": None,
            "notebook": None,
            "notebook_id": None,
        }
    finally:
        terminal_tool.cleanup_vm(task_id)
