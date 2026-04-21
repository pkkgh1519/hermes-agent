#!/usr/bin/env python3
"""NotebookLM tool with gateway route-aware defaults."""

from __future__ import annotations

from typing import Any

from hermes_cli.notebooklm import (
    NotebookCommandError,
    NotebookLookupUnavailable,
    add_source,
    ask_notebook,
    collect_status,
    get_notebook_metadata,
    list_notebooks,
    list_sources,
    resolve_notebook_reference,
    _module_available,
)
from tools.registry import registry, tool_error, tool_result



def _tool_result_with_notebook_context(
    resolved: dict[str, str | None],
    payload: dict[str, Any],
) -> str:
    clean_payload = dict(payload)
    clean_payload.pop("notebook", None)
    clean_payload.pop("notebook_id", None)
    return tool_result(
        notebook=resolved["notebook"],
        notebook_id=resolved["notebook_id"],
        **clean_payload,
    )



def _get_bound_notebook() -> dict[str, str]:
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return {
            "notebook": "",
            "notebook_id": "",
            "route_target": "",
            "route_mode": "",
        }

    return {
        "notebook": get_session_env("HERMES_SESSION_ROUTE_NOTEBOOK", ""),
        "notebook_id": get_session_env("HERMES_SESSION_ROUTE_NOTEBOOK_ID", ""),
        "route_target": get_session_env("HERMES_SESSION_ROUTE_TARGET", ""),
        "route_mode": get_session_env("HERMES_SESSION_ROUTE_MODE", ""),
    }



def _resolve_target(
    *,
    notebook: str | None = None,
    notebook_id: str | None = None,
    profile: str = "default",
) -> dict[str, str | None]:
    bound = _get_bound_notebook()
    route_mode = (bound.get("route_mode") or "").strip().lower()
    bound_notebook = bound["notebook"] if route_mode in ("", "notebooklm") else ""
    bound_notebook_id = bound["notebook_id"] if route_mode in ("", "notebooklm") else ""

    if notebook_id:
        title = None
        if notebook:
            try:
                resolved = resolve_notebook_reference(notebook, profile=profile)
            except NotebookLookupUnavailable as exc:
                raise ValueError(
                    "Cannot validate notebook title against notebook_id because NotebookLM lookup is unavailable"
                ) from exc
            resolved_id = resolved.get("id")
            if resolved_id and str(resolved_id) != str(notebook_id):
                raise ValueError("notebook and notebook_id refer to different notebooks")
            title = resolved.get("title") or notebook
        elif bound_notebook_id == notebook_id:
            title = bound_notebook or None
        return {
            "notebook": title or None,
            "notebook_id": notebook_id,
            "source": "explicit-id",
        }

    if notebook:
        resolved = resolve_notebook_reference(notebook, profile=profile)
        return {
            "notebook": resolved.get("title") or notebook,
            "notebook_id": resolved.get("id") or None,
            "source": "lookup",
        }

    if bound_notebook_id:
        return {
            "notebook": bound_notebook or None,
            "notebook_id": bound_notebook_id or None,
            "source": "session-route",
        }

    if bound_notebook:
        resolved = resolve_notebook_reference(bound_notebook, profile=profile)
        return {
            "notebook": resolved.get("title") or bound_notebook or None,
            "notebook_id": resolved.get("id") or None,
            "source": "session-route",
        }

    return {
        "notebook": None,
        "notebook_id": None,
        "source": "none",
    }



def notebooklm_tool(
    action: str = "status",
    notebook: str | None = None,
    notebook_id: str | None = None,
    question: str | None = None,
    source_type: str | None = None,
    content: str | None = None,
    profile: str = "default",
) -> str:
    action = (action or "status").strip().lower()
    bound = _get_bound_notebook()

    try:
        if action == "status":
            status = collect_status(profile)
            status["bound_notebook"] = {
                "notebook": bound["notebook"] or None,
                "notebook_id": bound["notebook_id"] or None,
                "route_target": bound["route_target"] or None,
                "route_mode": bound["route_mode"] or None,
            }
            return tool_result(status)

        if action == "list":
            notebooks = list_notebooks(profile)
            return tool_result(
                notebooks=notebooks,
                count=len(notebooks),
                bound_notebook={
                    "notebook": bound["notebook"] or None,
                    "notebook_id": bound["notebook_id"] or None,
                    "route_target": bound["route_target"] or None,
                    "route_mode": bound["route_mode"] or None,
                },
            )

        if action == "resolve":
            resolved = _resolve_target(notebook=notebook, notebook_id=notebook_id, profile=profile)
            if not resolved["notebook"] and not resolved["notebook_id"]:
                return tool_error(
                    "No notebook is bound to this session. Provide notebook or notebook_id, or bind the topic route first."
                )
            return tool_result(resolved)

        if action == "metadata":
            resolved = _resolve_target(notebook=notebook, notebook_id=notebook_id, profile=profile)
            if not resolved["notebook_id"]:
                return tool_error(
                    "No notebook_id is available. Provide notebook_id explicitly or bind/resolve the notebook first."
                )
            payload = get_notebook_metadata(
                notebook_id=str(resolved["notebook_id"]),
                profile=profile,
            )
            if not isinstance(payload, dict):
                return tool_error("NotebookLM metadata returned an unsupported payload")
            return _tool_result_with_notebook_context(resolved, payload)

        if action == "source_list":
            resolved = _resolve_target(notebook=notebook, notebook_id=notebook_id, profile=profile)
            if not resolved["notebook_id"]:
                return tool_error(
                    "No notebook_id is available. Provide notebook_id explicitly or bind/resolve the notebook first."
                )
            sources = list_sources(
                notebook_id=str(resolved["notebook_id"]),
                profile=profile,
            )
            return tool_result(
                notebook=resolved["notebook"],
                notebook_id=resolved["notebook_id"],
                sources=sources,
                count=len(sources),
            )

        if action == "source_add":
            if not source_type or content is None or not content.strip():
                return tool_error("source_type and content are required for action='source_add'")
            resolved = _resolve_target(notebook=notebook, notebook_id=notebook_id, profile=profile)
            if not resolved["notebook_id"]:
                return tool_error(
                    "No notebook_id is available. Provide notebook_id explicitly or bind/resolve the notebook first."
                )
            payload = add_source(
                notebook_id=str(resolved["notebook_id"]),
                source_type=source_type,
                content=content,
                profile=profile,
            )
            return _tool_result_with_notebook_context(resolved, payload)

        if action == "ask":
            if not question or not question.strip():
                return tool_error("question is required for action='ask'")
            resolved = _resolve_target(notebook=notebook, notebook_id=notebook_id, profile=profile)
            if not resolved["notebook_id"]:
                return tool_error(
                    "No notebook_id is available. Provide notebook_id explicitly or bind/resolve the notebook first."
                )
            payload = ask_notebook(question.strip(), notebook_id=str(resolved["notebook_id"]), profile=profile)
            if not isinstance(payload, dict):
                return tool_error("NotebookLM ask returned an unsupported payload")
            return _tool_result_with_notebook_context(resolved, payload)

        return tool_error(f"Unknown action: {action}")
    except (NotebookLookupUnavailable, NotebookCommandError, ValueError) as exc:
        return tool_error(str(exc))



def check_notebooklm_requirements() -> bool:
    bound = _get_bound_notebook()
    if (bound.get("route_mode") or "").strip().lower() == "notebooklm":
        return True
    return _module_available("notebooklm")


NOTEBOOKLM_SCHEMA = {
    "name": "notebooklm",
    "description": (
        "Interact with NotebookLM notebooks. When the current gateway topic is bound to a "
        "NotebookLM route, notebook_id defaults to that bound notebook. Actions: status, list, "
        "resolve, metadata, source_list, source_add, ask."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "list", "resolve", "metadata", "source_list", "source_add", "ask"],
                "description": "Operation to perform",
            },
            "notebook": {
                "type": "string",
                "description": "Notebook title or ID. Optional; defaults to the bound route notebook.",
            },
            "notebook_id": {
                "type": "string",
                "description": "Explicit notebook ID. Overrides notebook title and bound-route defaults.",
            },
            "question": {
                "type": "string",
                "description": "Question to ask when action='ask'.",
            },
            "source_type": {
                "type": "string",
                "enum": ["url", "text"],
                "description": "Source type to add when action='source_add'.",
            },
            "content": {
                "type": "string",
                "description": "URL or raw text content to add when action='source_add'.",
            },
            "profile": {
                "type": "string",
                "description": "NotebookLM profile name for legacy profile-based installs.",
                "default": "default",
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="notebooklm",
    toolset="notebooklm",
    schema=NOTEBOOKLM_SCHEMA,
    handler=lambda args, **kw: notebooklm_tool(
        action=args.get("action", "status"),
        notebook=args.get("notebook"),
        notebook_id=args.get("notebook_id"),
        question=args.get("question"),
        source_type=args.get("source_type"),
        content=args.get("content"),
        profile=args.get("profile", "default"),
    ),
    check_fn=check_notebooklm_requirements,
    emoji="📚",
)
