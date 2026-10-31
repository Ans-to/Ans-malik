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
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.frames, "f_*.png")))
    if not files:
        print(f"::warning title={args.label}::no frames in {args.frames}")
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
        print(f"::notice title={args.label} shot {sh['key']}::{sh['key']}: frames {min(ks)}-{max(ks)}, "
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
            print(f"::notice title={args.label} type {r['body'][:18]}::"
                  f"'{r['body'][:22]}' frame {r['frame']}: full max {max(full[k] for k in ks):.4f}, "
                  f"band max {max(band[k] for k in ks):.4f}, window frames {min(ks)}-{max(ks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
