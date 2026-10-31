#!/usr/bin/env python3
"""
clip_real.py — the literal Part F gate, for machines that can reach HuggingFace.

    pip install open_clip_torch torch pillow
    python gpu-film/gates/clip_real.py --frames gpu-film/out/frames_hd

This is the spec's OpenCLIP implementation, unchanged in intent: encode sampled
frames and compare them against premium vs slop text prompts, then require the
mean confidence gap to exceed 0.08 with fewer than 20 % of frames failing.
"""
import argparse
import os
import sys

PREMIUM = [
    "premium cinematic product commercial, dramatic lighting, shallow depth of field",
    "high-end motion graphics reel, polished kinetic typography",
    "professional studio product render, volumetric lighting, premium advertising",
    "award-winning motion design, smooth camera movement, agency quality",
]
SLOP = [
    "powerpoint slide presentation, static image with text",
    "amateur slideshow video, flat lighting, no motion",
    "stock photo with text overlay, basic template design",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="folder of rendered PNG frames")
    ap.add_argument("--step", type=int, default=10, help="score every Nth frame")
    ap.add_argument("--threshold", type=float, default=0.08)
    args = ap.parse_args()

    try:
        import open_clip
        import torch
        from PIL import Image
    except ImportError:
        print("install first: pip install open_clip_torch torch pillow", file=sys.stderr)
        return 2

    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")

    files = sorted(f for f in os.listdir(args.frames) if f.lower().endswith(".png"))[:: args.step]
    if not files:
        print(f"no frames in {args.frames}", file=sys.stderr)
        return 2

    prem = tokenizer(PREMIUM)
    slop = tokenizer(SLOP)
    with torch.no_grad():
        pf = model.encode_text(prem)
        sf = model.encode_text(slop)

    gaps = []
    fails = 0
    for name in files:
        img = preprocess(Image.open(os.path.join(args.frames, name)).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            feats = model.encode_image(img)
        gap = (feats @ pf.T).mean().item() - (feats @ sf.T).mean().item()
        gaps.append(gap)
        if gap <= args.threshold:
            fails += 1

    avg = sum(gaps) / len(gaps)
    fail_share = fails / len(gaps)
    print(f"frames scored      : {len(gaps)}")
    print(f"average gap        : {avg:.4f}")
    print(f"failing frames     : {fails} ({fail_share:.1%})")
    ok = avg >= args.threshold and fail_share <= 0.2
    print("RESULT             :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
