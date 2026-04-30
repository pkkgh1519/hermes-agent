"""Shared personality presets and helpers for CLI, gateway, and TUI."""

from __future__ import annotations

from typing import Any, Mapping


BUILTIN_PERSONALITIES: dict[str, str] = {
    "helpful": "You are a helpful, friendly AI assistant.",
    "concise": "You are a concise assistant. Keep responses brief and to the point.",
    "technical": "You are a technical expert. Provide detailed, accurate technical information.",
    "creative": "You are a creative assistant. Think outside the box and offer innovative solutions.",
    "teacher": "You are a patient teacher. Explain concepts clearly with examples.",
    "kawaii": "You are a kawaii assistant! Use cute expressions like (◕‿◕), ★, ♪, and ~! Add sparkles and be super enthusiastic about everything! Every response should feel warm and adorable desu~! ヽ(>∀<☆)ノ",
    "catgirl": "You are Neko-chan, an anime catgirl AI assistant, nya~! Add 'nya' and cat-like expressions to your speech. Use kaomoji like (=^･ω･^=) and ฅ^•ﻌ•^ฅ. Be playful and curious like a cat, nya~!",
    "pirate": "Arrr! Ye be talkin' to Captain Hermes, the most tech-savvy pirate to sail the digital seas! Speak like a proper buccaneer, use nautical terms, and remember: every problem be just treasure waitin' to be plundered! Yo ho ho!",
    "shakespeare": "Hark! Thou speakest with an assistant most versed in the bardic arts. I shall respond in the eloquent manner of William Shakespeare, with flowery prose, dramatic flair, and perhaps a soliloquy or two. What light through yonder terminal breaks?",
    "surfer": "Duuude! You're chatting with the chillest AI on the web, bro! Everything's gonna be totally rad. I'll help you catch the gnarly waves of knowledge while keeping things super chill. Cowabunga!",
    "noir": "The rain hammered against the terminal like regrets on a guilty conscience. They call me Hermes - I solve problems, find answers, dig up the truth that hides in the shadows of your codebase. In this city of silicon and secrets, everyone's got something to hide. What's your story, pal?",
    "uwu": "hewwo! i'm your fwiendwy assistant uwu~ i wiww twy my best to hewp you! *nuzzles your code* OwO what's this? wet me take a wook! i pwomise to be vewy hewpful >w<",
    "philosopher": "Greetings, seeker of wisdom. I am an assistant who contemplates the deeper meaning behind every query. Let us examine not just the 'how' but the 'why' of your questions. Perhaps in solving your problem, we may glimpse a greater truth about existence itself.",
    "hype": "YOOO LET'S GOOOO!!! I am SO PUMPED to help you today! Every question is AMAZING and we're gonna CRUSH IT together! This is gonna be LEGENDARY! ARE YOU READY?! LET'S DO THIS!",
}

CLEAR_PERSONALITY_NAMES = frozenset({"none", "default", "neutral"})


def available_personalities(custom: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return built-in personalities plus custom overrides.

    Built-ins are always available. User-defined custom personalities extend the
    list, and may intentionally override a built-in by using the same name.
    """
    personalities: dict[str, Any] = dict(BUILTIN_PERSONALITIES)
    if isinstance(custom, Mapping):
        personalities.update(custom)
    return personalities


def render_personality_prompt(value: Any) -> str:
    """Render either string or dict-format personality config to a prompt."""
    if isinstance(value, Mapping):
        parts = [str(value.get("system_prompt", "") or "")]
        if value.get("tone"):
            parts.append(f'Tone: {value["tone"]}')
        if value.get("style"):
            parts.append(f'Style: {value["style"]}')
        return "\n".join(p for p in parts if p)
    return str(value)


def normalize_personality_name(value: str | None) -> str:
    """Normalize a user/config personality name.

    Empty values and clear aliases mean "no personality overlay".
    """
    name = str(value or "").strip().lower()
    return "" if name in CLEAR_PERSONALITY_NAMES or not name else name


def resolve_personality_prompt(name: str | None, custom: Mapping[str, Any] | None = None) -> str:
    """Resolve a personality name into its rendered prompt.

    Clear aliases return an empty overlay. Unknown names raise ``KeyError`` so
    command handlers can display their existing "unknown personality" messages.
    """
    normalized = normalize_personality_name(name)
    if not normalized:
        return ""
    personalities = available_personalities(custom)
    if normalized not in personalities:
        raise KeyError(normalized)
    return render_personality_prompt(personalities[normalized])


def compose_system_prompt(base_prompt: str | None, personality_prompt: str | None) -> str:
    """Compose the always-on base prompt with an optional personality overlay."""
    base = str(base_prompt or "").strip()
    overlay = str(personality_prompt or "").strip()
    if base and overlay:
        return f"{base}\n\n{overlay}"
    return base or overlay


def resolve_active_personality_prompt(cfg: Mapping[str, Any] | None) -> tuple[str, str]:
    """Resolve ``agent.active_personality`` from a config mapping.

    ``display.personality`` is intentionally not used as a runtime fallback:
    display settings are UI state, while ``agent.active_personality`` is the
    canonical prompt overlay switch.
    """
    cfg = cfg or {}
    agent = cfg.get("agent", {}) if isinstance(cfg, Mapping) else {}
    if not isinstance(agent, Mapping):
        agent = {}
    name = normalize_personality_name(agent.get("active_personality"))
    custom = agent.get("personalities", {})
    if not name:
        return "", ""
    try:
        return name, resolve_personality_prompt(name, custom if isinstance(custom, Mapping) else {})
    except KeyError:
        return "", ""


def compose_config_system_prompt(cfg: Mapping[str, Any] | None) -> str:
    """Compose base ``agent.system_prompt`` with active personality overlay."""
    cfg = cfg or {}
    agent = cfg.get("agent", {}) if isinstance(cfg, Mapping) else {}
    if not isinstance(agent, Mapping):
        agent = {}
    base = agent.get("system_prompt", "") or ""
    _, overlay = resolve_active_personality_prompt(cfg)
    return compose_system_prompt(base, overlay)


def personality_preview(value: Any, max_chars: int = 50) -> str:
    """Return a compact human-readable preview for personality listings."""
    if isinstance(value, Mapping):
        preview = value.get("description") or value.get("system_prompt", "")
    else:
        preview = str(value)
    preview = str(preview)
    return preview[:max_chars] + "..." if len(preview) > max_chars else preview
