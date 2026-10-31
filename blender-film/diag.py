#!/usr/bin/env python3
"""Per-shot detail diagnostics, printed from inside a render shard.

The type gate measures frame-wide edge energy, so a failing line can mean two very different
things: the lettering is not there (a build bug) or the shot around it is simply quieter than the
rest of the film. This distinguishes them by reporting, per shot, the frame-wide detail and the
detail inside the band of the frame where the type sits.

    diag.py --frames blender-film/out/frames_preview --manifest blender-film/out/manifest_preview.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

FPS = 30.0


def laplacian(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1])
    return float(np.abs(lap).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--label", default="detail")
    ap.add_argument("--boxes", default="", help="boxes.json written by scene.py --probe-render")
    args = ap.parse_args()

    out_lines: list[str] = []

    def say(msg: str) -> None:
        # GitHub keeps only a handful of annotations per step, so they are collected and emitted
        # once at the end instead of one at a time.
        out_lines.append(msg)

    files = sorted(glob.glob(os.path.join(args.frames, "f_*.png")))
    if not files:
        print(f"::warning title={args.label}::no frames in {args.frames}")
        # Inside the words themselves: is the lettering blown out to a smooth blob, or simply absent?
    if args.boxes and os.path.exists(args.boxes):
        with open(args.boxes) as fh:
            boxes = json.load(fh)
        for frame, objs in sorted(boxes.items(), key=lambda kv: int(kv[0])):
            path = os.path.join(args.frames, f"f_{int(frame):04d}.png")
            if not os.path.exists(path):
                continue
            a = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
            for name, (x0, y0, x1, y1) in objs.items():
                if not name.startswith(("D_", "C_", "A_")):
                    continue
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(a.shape[1], x1), min(a.shape[0], y1)
                if x1 <= x0 or y1 <= y0:
                    say(f"{name} at {frame}: off-frame")
                    continue
                patch = a[y0:y1, x0:x1]
                say(f"{name} at {frame}: box {x1 - x0}x{y1 - y0}, mean {patch.mean():.3f}, "
                    f"max {patch.max():.3f}, blown {(patch > 0.90).mean() * 100:.1f}%, "
                    f"detail {laplacian(patch):.4f}")
    return 0
    with open(args.manifest) as fh:
        man = json.load(fh)

    full, band, luma = {}, {}, {}
    for path in files:
        idx = int(os.path.basename(path).split("_")[1].split(".")[0])
        a = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
        full[idx] = laplacian(a)
        # the vertical band where this film puts type: the middle 40 % of the height
        h = a.shape[0]
        band[idx] = laplacian(a[int(h * 0.30):int(h * 0.70)])
        luma[idx] = float(a.mean())

    shots = man.get("shots", [])
    for sh in shots:
        ks = [k for k in full if sh["start"] <= k <= sh["end"]]
        if not ks:
            continue
        f = np.array([full[k] for k in ks])
        b = np.array([band[k] for k in ks])
        say(f"shot {sh['key']}: frames {min(ks)}-{max(ks)}, "
              f"detail med {np.median(f):.4f} p90 {np.percentile(f, 90):.4f} max {f.max():.4f} | "
              f"band med {np.median(b):.4f} max {b.max():.4f} | luma {np.median([luma[k] for k in ks]):.3f}")

    # what the type windows actually see, with the same rounding the gate uses
    rows = [[r for r in man.get("type", []) if r["shot"] == sh["key"]] for sh in shots]
    for sh, rs in zip(shots, rows):
        for r in rs:
            f10 = max(0, int(round((r["frame"] - 1) / FPS * 10)))
            ks = [k for k in full if f10 * 3 <= k < f10 * 3 + 36]  # the gate's 12 x 0.1 s window
            if not ks:
                continue
            say(f"type '{r['body'][:22]}' frame {r['frame']}: full max "
                f"{max(full[k] for k in ks):.4f}, band max {max(band[k] for k in ks):.4f}")
    # Inside the words themselves: is the lettering blown out to a smooth blob, or simply absent?
    if args.boxes and os.path.exists(args.boxes):
        with open(args.boxes) as fh:
            boxes = json.load(fh)
        for frame, objs in sorted(boxes.items(), key=lambda kv: int(kv[0])):
            path = os.path.join(args.frames, f"f_{int(frame):04d}.png")
            if not os.path.exists(path):
                continue
            a = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
            for name, (x0, y0, x1, y1) in objs.items():
                if not name.startswith(("D_", "C_", "A_")):
                    continue
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(a.shape[1], x1), min(a.shape[0], y1)
                if x1 <= x0 or y1 <= y0:
                    say(f"{name} at {frame}: off-frame")
                    continue
                patch = a[y0:y1, x0:x1]
                say(f"{name} at {frame}: box {x1 - x0}x{y1 - y0}, mean {patch.mean():.3f}, "
                    f"max {patch.max():.3f}, blown {(patch > 0.90).mean() * 100:.1f}%, "
                    f"detail {laplacian(patch):.4f}")
    print(f"::notice title={args.label}::" + " | ".join(out_lines)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
