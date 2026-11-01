"""repo-cartographer — Hermes plugin registration.

Registers:
  * two tools (`repo_profile`, `hotspot_scan`) in the `workbench` toolset
  * a `post_tool_call` hook that keeps a small activity log
  * a `/cartographer` in-session slash command
  * a bundled skill (`repo-cartographer:repo-audit`) via ctx.register_skill
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from . import cartographer

logger = logging.getLogger(__name__)

TOOLSET = "workbench"

REPO_PROFILE_SCHEMA = {
    "name": "repo_profile",
    "description": (
        "Profile a repository without running shell commands: file/byte totals, "
        "per-language file counts, bytes and lines of code, the largest files, "
        "top-level entry points, dependency manifests, and git branch/HEAD read "
        "straight from .git. Stdlib only, no network. Use this first when asked "
        "'what is this codebase?'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository root. Defaults to '.'."},
            "top": {
                "type": "integer",
                "description": "How many rows to return per section (1-50). Default 10.",
            },
        },
        "required": [],
    },
}

HOTSPOT_SCHEMA = {
    "name": "hotspot_scan",
    "description": (
        "Find refactor targets: source files above a line-count threshold, sorted "
        "largest first. Filter by extension (default .py). Stdlib only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory to scan. Defaults to '.'."},
            "loc_limit": {
                "type": "integer",
                "description": "Report files at or above this many lines. Default 800.",
            },
            "extensions": {
                "type": "string",
                "description": "Comma-separated extensions, e.g. '.py,.ts'. Default '.py'.",
            },
        },
        "required": [],
    },
}


def _activity_log_path() -> Path:
    """Per-profile state dir, created on demand. Never raises to the caller."""
    base = os.environ.get("HERMES_HOME") or ""
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".hermes")
    log_dir = Path(base) / "plugin-state" / "repo-cartographer"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path(os.devnull)
    return log_dir / "activity.jsonl"


def _on_post_tool_call(tool_name, args, result, task_id=None, **kwargs):
    """Record every workbench-tool call. Runs for all tools; we only keep ours."""
    if tool_name not in ("repo_profile", "hotspot_scan"):
        return
    try:
        path = _activity_log_path()
        entry = {
            "tool": tool_name,
            "session": task_id,
            "target": (args or {}).get("path"),
            "result_bytes": len(result or ""),
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:  # a logging hook must never break a turn
        logger.debug("repo-cartographer: activity log failed", exc_info=True)


def _handle_slash(ctx, raw_args: str) -> str:
    """/cartographer [path] — profile a repo inline."""
    target = (raw_args or "").strip() or "."
    payload = ctx.dispatch_tool("repo_profile", {"path": target, "top": 8})
    if isinstance(payload, str):
        return cartographer.format_profile(payload)
    return cartographer.format_profile(json.dumps(payload))


def _register_skills(ctx) -> None:
    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            try:
                ctx.register_skill(child.name, skill_md)
            except Exception:
                logger.debug("repo-cartographer: could not register skill %s",
                             child.name, exc_info=True)


def register(ctx):
    """Entry point Hermes calls once at startup."""
    ctx.register_tool(name="repo_profile", toolset=TOOLSET,
                      schema=REPO_PROFILE_SCHEMA, handler=cartographer.repo_profile)
    ctx.register_tool(name="hotspot_scan", toolset=TOOLSET,
                      schema=HOTSPOT_SCHEMA, handler=cartographer.hotspot_scan)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_command(
        "cartographer",
        lambda raw: _handle_slash(ctx, raw),
        description="Profile a repository (repo_profile) and print a summary table",
    )
    _register_skills(ctx)
    logger.info("repo-cartographer registered: repo_profile, hotspot_scan, /cartographer")
