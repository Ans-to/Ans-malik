#!/usr/bin/env python3
"""Per-shot detail diagnostics, printed from inside a render shard or the probe.

The type gate measures frame-wide edge energy, so a failing line can mean very different things:
the words are not there, the words are there but blown out to a smooth blob, or the shot around
them is simply quieter than the rest of the film. This reports all three:

  * frame-wide detail and detail in the band where this film puts type, per shot
  * what each type window actually saw, using the gate's own frame rounding
  * inside each text object's projected bounding box (when a boxes.json is supplied)

    diag.py --frames blender-film/out/frames_preview \
            --manifest blender-film/out/manifest_preview.json [--boxes out/probe/boxes.json]

Everything is emitted as one annotation: GitHub keeps only a handful per step, and the messages
must be escaped or it drops them silently.
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
# the lines of type, not the odometer digits (C_dNN_-635 and friends), which would fill the
# annotation cap before the shots that matter are reached
TYPE_NAMES = ("A_type", "B_cap", "C_line", "D_type", "E_letter", "E_tag")


def lap_abs(gray: np.ndarray) -> np.ndarray:
    g = gray.astype(np.float32)
    return np.abs(g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1])


def laplacian(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1])
    return float(np.abs(lap).mean())


def escape(msg: str) -> str:
    return msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--label", default="detail")
    ap.add_argument("--boxes", default="", help="boxes.json written by scene.py --probe-render")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.frames, "f_*.png")))
    if not files:
        print(f"::warning title={args.label}::no frames in {args.frames}")
        return 0

    with open(args.manifest) as fh:
        man = json.load(fh)

    out: list[str] = []
    full, band, luma = {}, {}, {}
    for path in files:
        idx = int(os.path.basename(path).split("_")[1].split(".")[0])
        a = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
        full[idx] = laplacian(a)
        h = a.shape[0]
        band[idx] = laplacian(a[int(h * 0.30):int(h * 0.70)])
        luma[idx] = float(a.mean())

    for sh in man.get("shots", []):
        ks = [k for k in full if sh["start"] <= k <= sh["end"]]
        if not ks:
            continue
        f = np.array([full[k] for k in ks])
        b = np.array([band[k] for k in ks])
        out.append(f"shot {sh['key']}: frames {min(ks)}-{max(ks)}, detail med {np.median(f):.4f} "
                   f"max {f.max():.4f}, band med {np.median(b):.4f} max {b.max():.4f}, "
                   f"luma {np.median([luma[k] for k in ks]):.3f}")

    for r in man.get("type", []):
        f10 = max(0, int(round((r["frame"] - 1) / FPS * 10)))
        ks = [k for k in full if f10 * 3 <= k < f10 * 3 + 36]
        if not ks:
            continue
        out.append(f"type '{r['body'][:20]}' f{r['frame']}: full max "
                   f"{max(full[k] for k in ks):.4f}, band max {max(band[k] for k in ks):.4f}")

    if args.boxes and os.path.exists(args.boxes):
        with open(args.boxes) as fh:
            boxes = json.load(fh)
        # shot D first: it is the one in question, and the annotation is capped
        wanted = sorted(boxes, key=lambda f: (0 if any(n.startswith("D_") for n in boxes[f]) else 1,
                                              int(f)))
        for frame in wanted:
            path = os.path.join(args.frames, f"f_{int(frame):04d}.png")
            if not os.path.exists(path):
                continue
            a = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
            for name, box in sorted(boxes[frame].items(), key=lambda kv: (0 if kv[0].startswith("D_") else 1, kv[0])):
                if not name.startswith(TYPE_NAMES):
                    continue
                x0, y0, x1, y1 = box
                x0, y0 = max(0, int(x0)), max(0, int(y0))
                x1, y1 = min(a.shape[1], int(x1)), min(a.shape[0], int(y1))
                if x1 <= x0 or y1 <= y0:
                    out.append(f"{name} f{frame}: box off-frame")
                    continue
                patch = a[y0:y1, x0:x1]
                lap = lap_abs(patch)
                out.append(f"{name} f{frame}: {x1 - x0}x{y1 - y0}px mean {patch.mean():.3f} "
                           f"max {patch.max():.3f} blown {(patch > 0.90).mean() * 100:.0f}% "
                           f"detail {lap.mean():.4f} p99 {np.percentile(lap, 99):.3f} "
                           f"p999 {np.percentile(lap, 99.9):.3f}")

    # shot/type summary first, then the boxes; the whole thing still has to fit the cap
    print(f"::notice title={args.label}::" + escape(" | ".join(out))[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
