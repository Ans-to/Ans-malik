#!/usr/bin/env python3
"""qa_check.py — static contract checker for Blender video scripts.

Standard library only. Two modes:

    python3 qa_check.py script.py                # contract check, JSON out, rc!=0 on fail
    python3 qa_check.py --check-frame out.png    # rendered-frame sanity check

The contract checked here is the one in SKILL.md Step 3. It is deliberately
syntactic: it cannot tell you the shot looks good, only that the script will
run headless and produce a correctly-typed, correctly-sized video.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import struct
import sys

# Rule -> (severity, human message, needle-regex)
CHECKS = [
    ("import_bpy", "error", "script must import bpy", r"^\s*import\s+bpy|^\s*from\s+bpy"),
    ("factory_reset", "error",
     "must start from bpy.ops.wm.read_factory_settings(use_empty=True)",
     r"read_factory_settings\s*\([^)]*use_empty\s*=\s*True"),
    ("fps", "error", "scene.render.fps must be set explicitly", r"\bfps\s*="),
    ("resolution", "error", "resolution_x and resolution_y must be set",
     r"resolution_x\s*=.*[\s\S]*resolution_y\s*="),
    ("frame_range", "error", "frame_start and frame_end must be set",
     r"frame_start\s*=.*[\s\S]*frame_end\s*="),
    ("output_path", "error", "render.filepath must be set", r"filepath\s*="),
    ("format", "error", "image_settings.file_format or ffmpeg settings must be set",
     r"file_format\s*="),
    ("argv_split", "warn", "parse options after '--' (sys.argv) for re-runnable scripts",
     r"sys\.argv|argparse"),
    ("makedirs", "warn", "create the output directory before rendering",
     r"makedirs|mkdir"),
    ("manifest", "warn", "write a JSON manifest so QA can verify the output",
     r"manifest|\.json"),
    ("main_guard", "warn", "wrap execution in main() under an if __name__ guard",
     r"if\s+__name__\s*=="),
]

UI_ONLY = [
    (r"bpy\.ops\.view3d\.", "view3d ops need a window; headless render will fail"),
    (r"bpy\.ops\.screen\.", "screen ops need a UI; headless render will fail"),
    (r"bpy\.ops\.wm\.save_mainfile", "saving .blend is not needed and can prompt"),
    (r"bpy\.ops\.wm\.quit_blender", "never quit Blender from a render script"),
    (r"bpy\.ops\.render\.view_show|bpy\.ops\.render\.opengl", "OpenGL previews need a GPU context"),
]


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def literal_ints(src: str) -> dict:
    """Pull simple int literals assigned to well-known names, for the math check."""
    found = {}
    for name in ("fps", "frame_start", "frame_end", "resolution_x", "resolution_y",
                 "samples"):
        m = re.search(rf"\b{name}\s*=\s*(-?\d+)", src)
        if m:
            found[name] = int(m.group(1))
    m = re.search(r"\bframes?\s*=\s*(?:int\()?\s*(\d+)", src)
    if m:
        found["frames"] = int(m.group(1))
    m = re.search(r"\bseconds?\s*=\s*(\d+(?:\.\d+)?)", src)
    if m:
        found["seconds"] = float(m.group(1))
    return found


def check_script(path: str) -> dict:
    result = {"script": os.path.abspath(path), "problems": [], "warnings": [], "info": {}}
    if not os.path.isfile(path):
        result["problems"].append({"rule": "exists", "message": f"no such file: {path}"})
        result["ok"] = False
        return result

    src = read(path)

    # 1. Must be parseable Python.
    try:
        ast.parse(src)
    except SyntaxError as exc:
        result["problems"].append({"rule": "syntax", "message": f"{exc.msg} (line {exc.lineno})"})
        result["ok"] = False
        return result

    # 2. Contract needles.
    for rule, severity, message, pattern in CHECKS:
        if not re.search(pattern, src, re.M):
            bucket = result["problems"] if severity == "error" else result["warnings"]
            bucket.append({"rule": rule, "message": message})

    # 3. UI-only ops.
    for pattern, message in UI_ONLY:
        if re.search(pattern, src):
            result["problems"].append({"rule": "ui_only_op", "message": message})

    # 4. Determinism / radian slips.
    if re.search(r"random\.(random|randint|choice)\s*\(", src) and "random.seed" not in src:
        result["warnings"].append({"rule": "seed", "message": "randomness without random.seed() is not reproducible"})
    for m in re.finditer(r"rotation_euler\s*=\s*\(([^)]*)\)", src):
        args = m.group(1)
        numeric = [a.strip() for a in args.split(",") if a.strip()]
        suspicious = [a for a in numeric
                      if re.fullmatch(r"-?\d+(\.\d+)?", a) and abs(float(a)) > 6.5]
        if suspicious:
            result["problems"].append({
                "rule": "radians",
                "message": f"rotation_euler looks like degrees, not radians: ({args.strip()}). "
                           f"Wrap in math.radians()"})

    # 5. Math: frames == fps * seconds, even dimensions for H.264.
    nums = literal_ints(src)
    result["info"]["literals"] = nums
    fps, frames = nums.get("fps"), nums.get("frames")
    seconds = nums.get("seconds")
    fs, fe = nums.get("frame_start"), nums.get("frame_end")
    if fps and fs is not None and fe is not None:
        result["info"]["frames_from_range"] = fe - fs + 1
        result["info"]["seconds_from_range"] = round((fe - fs + 1) / fps, 2)
    if seconds and fps and frames and abs(frames - fps * seconds) > max(1, fps):
        result["warnings"].append({
            "rule": "duration_math",
            "message": f"frames={frames} but fps*seconds={fps * seconds}"})
    if "H264" in src or "MPEG4" in src:
        for axis in ("resolution_x", "resolution_y"):
            val = nums.get(axis)
            if val is not None and val % 2:
                result["problems"].append({
                    "rule": "even_dimensions",
                    "message": f"{axis}={val} is odd; H.264 requires even dimensions"})

    result["ok"] = not result["problems"]
    return result


def check_frame(path: str) -> dict:
    """Verify a rendered PNG: exists, plausible size, and not a single flat colour."""
    out = {"frame": os.path.abspath(path), "ok": False, "problems": []}
    if not os.path.isfile(path):
        out["problems"].append(f"no such file: {path}")
        return out
    size = os.path.getsize(path)
    out["bytes"] = size
    if size < 1024:
        out["problems"].append(f"suspiciously small ({size} bytes) — likely a blank render")
    try:
        with open(path, "rb") as fh:
            head = fh.read(33)
            if head[:8] != b"\x89PNG\r\n\x1a\n":
                out["problems"].append("not a PNG")
                return out
            width, height = struct.unpack(">II", head[16:24])
            out["width"], out["height"] = width, height
            if width < 2 or height < 2:
                out["problems"].append("degenerate dimensions")
    except OSError as exc:
        out["problems"].append(f"cannot read PNG header: {exc}")
        return out
    # A ~flat single-colour PNG compresses absurdly well; bytes/pixel is the cheap tell.
    px = out.get("width", 1) * out.get("height", 1)
    out["bytes_per_pixel"] = round(size / px, 3)
    if px > 1000 and size / px < 0.05:
        out["problems"].append("frame is nearly uniform (bytes/pixel < 0.05) — probably black or empty")
    out["ok"] = not out["problems"]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Static QA for Blender video scripts")
    ap.add_argument("script", nargs="?", help="path to the .py to check")
    ap.add_argument("--check-frame", metavar="PNG", help="validate a rendered frame")
    ap.add_argument("--json", action="store_true", help="machine-readable output only")
    args = ap.parse_args(argv)

    if args.check_frame:
        report = check_frame(args.check_frame)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    if not args.script:
        ap.print_help()
        return 2

    report = check_script(args.script)
    if not args.json:
        print(f"{'PASS' if report['ok'] else 'FAIL'} {report['script']}")
        for p in report["problems"]:
            print(f"  ✗ [{p['rule']}] {p['message']}")
        for w in report["warnings"]:
            print(f"  ⚠ [{w['rule']}] {w['message']}")
        if not report["problems"] and not report["warnings"]:
            print("  all contract rules satisfied")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
