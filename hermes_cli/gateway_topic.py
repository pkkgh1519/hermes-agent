"""Helpers for exact chat/topic routing commands."""

from __future__ import annotations

import json
import os
from typing import Any

from hermes_cli.config import read_raw_config, save_config
from hermes_cli.notebooklm import (
    NotebookCommandError,
    NotebookLookupUnavailable,
    resolve_notebook_reference,
)



def parse_exact_target(target: str) -> tuple[str, str, str]:
    parts = target.split(":")
    if len(parts) != 3:
        raise ValueError("Exact target must look like platform:<chat_id>:<thread_id>")

    platform, chat_id, thread_id = (part.strip() for part in parts)
    if not platform or not chat_id or not thread_id:
        raise ValueError("Platform, chat_id, and thread_id are all required")

    platform = platform.lower()
    if platform != "telegram":
        raise ValueError("Only telegram exact topic routes are currently supported")

    try:
        thread_id = str(int(thread_id))
    except ValueError as exc:
        raise ValueError("thread_id must be numeric") from exc

    return platform, chat_id, thread_id



def _route_key(chat_id: str, thread_id: str) -> str:
    return f"{chat_id}:{thread_id}"



def _load_topic_routes_config() -> dict[str, Any]:
    return read_raw_config() or {}



def _topic_routes_root(config: dict[str, Any], *, create: bool = False) -> dict[str, Any] | None:
    gateway_cfg = config.get("gateway")
    if gateway_cfg is None:
        if not create:
            return None
        gateway_cfg = {}
        config["gateway"] = gateway_cfg
    if not isinstance(gateway_cfg, dict):
        if not create:
            return None
        gateway_cfg = {}
        config["gateway"] = gateway_cfg

    topic_routes = gateway_cfg.get("topic_routes")
    if topic_routes is None:
        if not create:
            return None
        topic_routes = {}
        gateway_cfg["topic_routes"] = topic_routes
    if not isinstance(topic_routes, dict):
        if not create:
            return None
        topic_routes = {}
        gateway_cfg["topic_routes"] = topic_routes

    return topic_routes



def _platform_routes(config: dict[str, Any], platform: str, *, create: bool = False) -> dict[str, Any] | None:
    topic_routes = _topic_routes_root(config, create=create)
    if topic_routes is None:
        return None

    routes = topic_routes.get(platform)
    if routes is None:
        if not create:
            return None
        routes = {}
        topic_routes[platform] = routes
    if not isinstance(routes, dict):
        if not create:
            return None
        routes = {}
        topic_routes[platform] = routes
    return routes



def _flatten_routes(config: dict[str, Any], platform_filter: str | None = None) -> list[dict[str, Any]]:
    topic_routes = _topic_routes_root(config, create=False) or {}
    rows: list[dict[str, Any]] = []

    for platform, routes in topic_routes.items():
        if platform_filter and platform != platform_filter:
            continue
        if not isinstance(routes, dict):
            continue
        for key, route in routes.items():
            if not isinstance(route, dict):
                continue
            row = {"target": f"{platform}:{key}"}
            row.update(route)
            rows.append(row)

    rows.sort(key=lambda row: row["target"])
    return rows



def _save(config: dict[str, Any]) -> None:
    save_config(config)



def _bind(args) -> None:
    platform, chat_id, thread_id = parse_exact_target(args.target)
    config = _load_topic_routes_config()
    routes = _platform_routes(config, platform, create=True)
    assert routes is not None

    notebook_title = getattr(args, "notebook", "") or ""
    notebook_id = ""
    profile = getattr(args, "profile", None) or os.getenv("NOTEBOOKLM_PROFILE", "default")
    mode = "manual"
    if notebook_title:
        mode = "notebooklm"
        try:
            notebook_info = resolve_notebook_reference(notebook_title, profile=profile)
            notebook_id = str(notebook_info.get("id") or "")
            notebook_title = str(notebook_info.get("title") or notebook_title)
        except NotebookLookupUnavailable:
            # Best-effort validation: keep the provided title when NotebookLM
            # tooling is unavailable on this machine/profile.
            pass
        except NotebookCommandError:
            # Command/runtime failures should not block topic binding; keep the
            # provided title and continue without notebook_id.
            pass
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    entry = {
        "label": getattr(args, "label", "") or "",
        "mode": mode,
        "notebook": notebook_title,
        "free_response": bool(getattr(args, "free_response", False)),
        "ignored": False,
    }
    if notebook_id:
        entry["notebook_id"] = notebook_id
    routes[_route_key(chat_id, thread_id)] = entry
    _save(config)
    print(f"Bound topic route: {args.target}")



def _unbind(args) -> None:
    platform, chat_id, thread_id = parse_exact_target(args.target)
    config = _load_topic_routes_config()
    routes = _platform_routes(config, platform, create=False) or {}
    routes.pop(_route_key(chat_id, thread_id), None)
    _save(config)
    print(f"Unbound topic route: {args.target}")



def _set_ignored(args, ignored: bool, *, create: bool) -> None:
    platform, chat_id, thread_id = parse_exact_target(args.target)
    config = _load_topic_routes_config()
    routes = _platform_routes(config, platform, create=create) or {}
    key = _route_key(chat_id, thread_id)
    if key not in routes and not create:
        print(f"Topic route not found: {args.target}")
        return
    entry = dict(routes.get(key) or {})
    entry.setdefault("label", "")
    entry.setdefault("mode", "manual")
    entry.setdefault("notebook", "")
    entry.setdefault("free_response", False)
    entry["ignored"] = ignored
    routes[key] = entry
    _save(config)
    state = "ignored" if ignored else "unignored"
    print(f"Marked topic route as {state}: {args.target}")



def _list(args) -> None:
    platform_filter = getattr(args, "platform", None)
    if platform_filter:
        platform_filter = str(platform_filter).strip().lower()
    rows = _flatten_routes(_load_topic_routes_config(), platform_filter)
    if getattr(args, "json", False):
        print(json.dumps(rows, ensure_ascii=False))
        return

    if not rows:
        print("No topic routes configured.")
        return

    for row in rows:
        print(
            f"{row['target']} label={row.get('label', '')!r} "
            f"mode={row.get('mode', '')} free_response={row.get('free_response', False)} "
            f"ignored={row.get('ignored', False)} notebook={row.get('notebook', '')!r}"
        )



def _test(args) -> None:
    platform, chat_id, thread_id = parse_exact_target(args.target)
    config = _load_topic_routes_config()
    routes = _platform_routes(config, platform, create=False) or {}
    entry = dict(routes.get(_route_key(chat_id, thread_id)) or {})

    if not entry:
        print(f"target={args.target} matched_exact_route=False")
        return

    print(
        f"target={args.target} matched_exact_route=True "
        f"free_response={entry.get('free_response', False)} "
        f"ignored={entry.get('ignored', False)} "
        f"mode={entry.get('mode', '')} notebook={entry.get('notebook', '')}"
    )



def topic_command(args) -> None:
    action = getattr(args, "topic_action", None)

    if action == "bind":
        _bind(args)
        return
    if action == "list":
        _list(args)
        return
    if action == "ignore":
        _set_ignored(args, True, create=True)
        return
    if action == "unignore":
        _set_ignored(args, False, create=False)
        return
    if action == "unbind":
        _unbind(args)
        return
    if action == "test":
        _test(args)
        return

    raise SystemExit(f"Unknown gateway topic action: {action}")
