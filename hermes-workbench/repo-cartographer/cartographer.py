"""repo-cartographer — durable, model-free repository profiling for Hermes.

Everything here is stdlib-only so the plugin works in a bare sandbox: no
network, no third-party imports, no LLM. It answers the question an agent
usually spends four `terminal` calls on: *what is this repo, really?*

Handlers follow the Hermes plugin contract:
    def handler(args: dict, **kwargs) -> str   # always a JSON string
"""

from __future__ import annotations

import json
import os
import os.path as osp
import time
from collections import Counter, defaultdict

# Directories that are noise in every repo profile.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox", ".next",
    ".nuxt", ".parcel-cache", ".turbo", ".cache", "dist", "build", "target",
    "coverage", ".idea", ".vscode", "site-packages", ".eggs",
}

LANG_BY_EXT = {
    ".py": "Python", ".pyi": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby",
    ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".hpp": "C++", ".cs": "C#",
    ".swift": "Swift", ".php": "PHP", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell", ".sql": "SQL", ".css": "CSS", ".scss": "SCSS",
    ".html": "HTML", ".md": "Markdown", ".mdx": "MDX", ".yaml": "YAML",
    ".yml": "YAML", ".toml": "TOML", ".json": "JSON", ".nix": "Nix",
    ".vue": "Vue", ".svelte": "Svelte", ".lua": "Lua", ".ex": "Elixir",
    ".exs": "Elixir", ".zig": "Zig", ".dart": "Dart", ".scala": "Scala",
}

TEXT_EXT = set(LANG_BY_EXT)

MANIFESTS = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Gemfile", "composer.json", "Dockerfile", "docker-compose.yml",
    "flake.nix", "Makefile", "justfile", "uv.lock", "poetry.lock",
    "pnpm-lock.yaml", "package-lock.json", "Cargo.lock", "go.sum",
}

# Filenames/patterns that look like entry points across ecosystems.
ENTRY_HINTS = (
    "__main__.py", "main.py", "cli.py", "app.py", "server.py", "manage.py",
    "index.ts", "index.js", "main.rs", "main.go", "main.ts",
)

# Files bigger than this are counted but not line-scanned (keeps it fast).
MAX_SCAN_BYTES = 2_000_000
# Hard stop so a monster checkout can't stall a turn.
MAX_FILES = 200_000


def _is_text_ext(path: str) -> bool:
    return osp.splitext(path)[1].lower() in TEXT_EXT


def _count_lines(path: str) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(chunk.count(b"\n") for chunk in iter(lambda: fh.read(1 << 20), b""))
    except OSError:
        return 0


def _git_info(root: str) -> dict:
    """Read git state straight from .git — no subprocess, no git binary needed."""
    git = osp.join(root, ".git")
    if not osp.isdir(git):
        return {"is_repo": False}
    info: dict = {"is_repo": True}
    try:
        with open(osp.join(git, "HEAD"), encoding="utf-8", errors="replace") as fh:
            head = fh.read().strip()
        if head.startswith("ref: "):
            ref = head[5:].strip()
            info["branch"] = ref.split("/", 2)[-1]
            ref_path = osp.join(git, ref)
            if osp.exists(ref_path):
                with open(ref_path, encoding="utf-8", errors="replace") as fh:
                    info["head"] = fh.read().strip()
        else:
            info["head"] = head
            info["detached"] = True
        if "head" in info:
            info["head_short"] = info["head"][:12]
        packed = osp.join(git, "packed-refs")
        if osp.exists(packed) and "head" not in info:
            info["note"] = "HEAD ref not materialized (packed-refs only)"
    except OSError as exc:
        info["error"] = f"could not read git state: {exc}"
    return info


def repo_profile(args: dict, **kwargs) -> str:
    """Profile a repository: languages, sizes, hotspots, entry points, manifests."""
    started = time.time()
    raw_path = args.get("path") or "."
    top = args.get("top")
    try:
        top = max(1, min(int(top), 50))
    except (TypeError, ValueError):
        top = 10

    root = osp.abspath(osp.expanduser(str(raw_path)))
    if not osp.isdir(root):
        return json.dumps({"error": f"not a directory: {root}", "path": root})

    ext_files: Counter = Counter()
    ext_bytes: Counter = Counter()
    ext_loc: Counter = Counter()
    largest: list = []
    entry_points: list = []
    manifests: list = []
    truncated = False
    files = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in filenames:
            if files >= MAX_FILES:
                truncated = True
                break
            full = osp.join(dirpath, name)
            try:
                size = osp.getsize(full)
            except OSError:
                continue
            rel = osp.relpath(full, root)
            files += 1
            total_bytes += size
            ext = osp.splitext(name)[1].lower() or "(none)"
            ext_files[ext] += 1
            ext_bytes[ext] += size
            if _is_text_ext(full) and size <= MAX_SCAN_BYTES:
                ext_loc[ext] += _count_lines(full)
            largest.append((size, rel))
            if name in ENTRY_HINTS and "/" not in rel.replace(os.sep, "/"):
                entry_points.append(rel)
            if name in MANIFESTS:
                manifests.append(rel)
        if truncated:
            break

    largest.sort(reverse=True)

    by_language: dict = defaultdict(lambda: {"files": 0, "bytes": 0, "loc": 0})
    for ext, n in ext_files.items():
        lang = LANG_BY_EXT.get(ext)
        if lang is None:
            # Not a source extension: lump binaries and stray data together so
            # they cannot masquerade as a language in the table.
            lang = "(binary/other)"
        by_language[lang]["files"] += n
        by_language[lang]["bytes"] += ext_bytes[ext]
        by_language[lang]["loc"] += ext_loc[ext]

    languages = sorted(
        ({"language": k, **v} for k, v in by_language.items()),
        key=lambda d: (-d["bytes"], d["language"]),
    )[:top]

    result = {
        "path": root,
        "files_total": files,
        "bytes_total": total_bytes,
        "megabytes_total": round(total_bytes / 1_048_576, 2),
        "languages": languages,
        "largest_files": [
            {"path": rel, "bytes": size, "megabytes": round(size / 1_048_576, 2)}
            for size, rel in largest[:top]
        ],
        "entry_points_top_level": sorted(entry_points)[:top],
        "manifests": sorted(manifests)[:top],
        "git": _git_info(root),
        "scan_truncated": truncated,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
    return json.dumps(result, indent=2)


def hotspot_scan(args: dict, **kwargs) -> str:
    """Flag oversized files and suspiciously large modules — the usual refactor targets."""
    started = time.time()
    raw_path = args.get("path") or "."
    try:
        loc_limit = int(args.get("loc_limit") or 800)
    except (TypeError, ValueError):
        loc_limit = 800
    try:
        loc_limit = max(50, min(loc_limit, 20000))
    except TypeError:
        loc_limit = 800
    extensions = args.get("extensions")
    if isinstance(extensions, str):
        extensions = [e.strip() if e.strip().startswith(".") else "." + e.strip()
                      for e in extensions.split(",") if e.strip()]
    if not extensions:
        extensions = [".py"]

    root = osp.abspath(osp.expanduser(str(raw_path)))
    if not osp.isdir(root):
        return json.dumps({"error": f"not a directory: {root}"})

    hits = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in filenames:
            ext = osp.splitext(name)[1].lower()
            if ext not in extensions:
                continue
            full = osp.join(dirpath, name)
            try:
                if osp.getsize(full) > MAX_SCAN_BYTES * 5:
                    continue
            except OSError:
                continue
            scanned += 1
            loc = _count_lines(full)
            if loc >= loc_limit:
                hits.append({"path": osp.relpath(full, root), "loc": loc, "extension": ext})

    hits.sort(key=lambda h: -h["loc"])
    return json.dumps({
        "path": root,
        "extensions": extensions,
        "loc_limit": loc_limit,
        "files_scanned": scanned,
        "over_limit": len(hits),
        "largest": hits[:25],
        "elapsed_ms": int((time.time() - started) * 1000),
    }, indent=2)


def format_profile(data: str) -> str:
    """Render a repo_profile JSON payload as a compact human table."""
    try:
        d = json.loads(data)
    except (TypeError, ValueError):
        return data
    if "error" in d:
        return f"repo-cartographer: {d['error']}"
    lines = [
        f"{d['path']}  —  {d['files_total']:,} files, {d['megabytes_total']:,} MB",
    ]
    git = d.get("git") or {}
    if git.get("is_repo"):
        lines.append(f"git: {git.get('branch', '?')} @ {(git.get('head') or '')[:12]}")
    lines.append("")
    lines.append(f"{'language':<14}{'files':>8}{'MB':>10}{'LOC':>12}")
    for row in d.get("languages", [])[:8]:
        lines.append(
            f"{row['language']:<14}{row['files']:>8}"
            f"{row['bytes'] / 1_048_576:>10.1f}{row['loc']:>12,}"
        )
    if d.get("entry_points_top_level"):
        lines.append("")
        lines.append("entry points: " + ", ".join(d["entry_points_top_level"][:6]))
    if d.get("manifests"):
        lines.append("manifests:    " + ", ".join(d["manifests"][:6]))
    return "\n".join(lines)
