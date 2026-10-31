# GPU Price Explainer — 60 s

> "Why Is a GPU So Expensive?" — 8 scenes, 120 BPM, exactly 60.000 s.
> Built to the Master Production Document. Every 🔒 gate that could run in this
> sandbox ran, with real numbers; every gate that could not is named in
> [`ENV_AUDIT.md`](./ENV_AUDIT.md) and [`logs/SUBSTITUTION_LEDGER.md`](./logs/SUBSTITUTION_LEDGER.md).

---

## Deliverables

| File | Spec | Size |
|---|---|---|
| [`out/explainer_1080p.mp4`](./out/explainer_1080p.mp4) | 1920×1080 · 60 fps · 60.000 s · H.264 High + AAC 192k | 86 MB |
| [`out/explainer_vertical.mp4`](./out/explainer_vertical.mp4) | 1080×1920 · 60 fps · 60.000 s · H.264 + AAC (pass 5) | 67 MB |
| [`out/stills_4k/`](./out/stills_4k) | 3840×2160 hero stills, one per scene + `hero_sheet.png` | 8 × 5 MB |
| [`out/explainer_draft_960.mp4`](./out/explainer_draft_960.mp4) | 960×540 · 60 fps (pass 1, not in git — regenerable) | 61 MB |
| [`out/soundtrack.wav`](./out/soundtrack.wav) | 44.1 kHz stereo, 60.000 s, synthesised at 120 BPM | 10 MB |
| [`out/contact_sheet.png`](./out/contact_sheet.png) | one frame per second, 8×8 (landscape) | 7 MB |
| [`out/contact_sheet_vertical.png`](./out/contact_sheet_vertical.png) | one frame per second (portrait) | 19 MB |
| [`logs/gate_report.json`](./logs/gate_report.json) | every gate, every pass, real numbers | — |
| [`logs/iteration_log.json`](./logs/iteration_log.json) | iterations per scene | — |
| [`logs/motion_curves.svg`](./logs/motion_curves.svg) | the curves that drive every camera move | — |

**4K master:** the pass-4 command is wired and gated — `npm run film:final`
(3840×2160, CRF 15). It is 3 600 frames at ~8.4 s/frame on this 2-core box
(≈ 8 h 24 m of CPU), so the 4K evidence delivered here is the eight hero
stills, rendered at full 3840×2160 through the same pipeline (including DOF,
bloom, aberration, grain and scrim).

---

## Gate results — pass 6 (1920×1080, final delivery)

Measured on `explainer_1080p.mp4`, not asserted:

| Gate | Rule | Measured | Result |
|---|---|---|---|
| Slideshow (H.9) | static fraction ≤ 0.18 · longest static run ≤ 24 f · median Δ ≥ 0.0015 | **0.000 · 0 f · 0.003345** over 1 799 sampled frames | **PASS** |
| Freeze (H.20) | `freezedetect=n=0.001:d=0.4` → ≤ 2 hits | **0 freezes** | **PASS** |
| Transition audit (H.16) | ≥ 5 distinct types · no type > 45 % | **7 types · max share 14.3 %** | **PASS** |
| Aesthetic (F) | gap > 0.08 · fail share ≤ 20 % | **premium 0.861 · slop 0.000 · gap 0.861 · fail share 0 %** | **PASS** (proxy) |
| Audio (H.18) | mean −30…−12 dB · peak < −0.5 dB | **mean −14.3 dB · peak −1.0 dB** | **PASS** |
| Sharpness | edge acutance at 480 px ≥ 0.055 | **1.277** (was 1.155 → **+10.5 %** on identical content) | **PASS** |

### What was actually wrong with the first cut

The first 1080p delivery passed every gate and still read as soft. Traced to
four renderer bugs, not to the delivery settings:

1. **No anti-aliasing** in the triangle rasteriser — every silhouette was a
   staircase.
2. **Depth of field started at a radius-2 blur**, so the entire frame was
   softened, focus plane included.
3. **DOF also defocused empty background**, smearing a copy of the subject
   around every silhouette: a halo on every edge.
4. **Type was composited before bloom**, so every glyph carried a glow.

Fixed by: 2×2 sub-sample coverage AA with alpha accumulation on silhouettes; a
z-buffer that interpolates 1/distance; DOF whose level 0 is the untouched frame,
with a thin-lens (squared) falloff, graded blending and no defocus of empty
background; and type on its own **2× supersampled layer composited after post**,
never bloomed. Edge acutance on identical content: **1.155 → 1.277 (+10.5 %)**.

Because "sharp" is now a gate, a regression of any of those four shows up as a
number rather than as a note in review.

The aesthetic gate is a **documented proxy**: OpenCLIP `ViT-B-32 / laion2b_s34b_b79k`
lives on `huggingface.co`, which this sandbox cannot reach. Every result is
stamped `"proxy": 1`. The literal gate is included and unmodified in intent:

```bash
pip install open_clip_torch torch pillow
python gpu-film/gates/clip_real.py --frames gpu-film/out/frames_hd
```

Pass 1 (960×540): static fraction 0.000 · median Δ 0.004910 · freezes 0 · 7 types.
Pass 5 (1080×1920, 68.0 min): static fraction 0.000 · median Δ 0.002760 · freezes 0 ·
7 transition types · aesthetic gap 0.788 (fail share 3.4 %) · audio mean −14.3 dB,
peak −1.0 dB — all **PASS**.

Portrait is not a crop: the graphics layer fits every line to the frame width
(`fit()`), and the world camera pulls back by `(1.78/aspect)^0.62` so the whole
subject stays in frame without distorting the lens.

---

## The pipeline, as executed

```
1  curves     assets/curves/*.json   ← extracted or stored measured profiles
2  motion     scenes.ts samples the INTEGRAL of measured velocity
3  light      procedural studio env: key/fill/rim + fresnel + Blinn spec
4  type       flat graphics layer, single grid, per-char wipes, aspect fitted
5  passes     PASS1 960×540 → PASS3 1920×1080 → PASS4 3840×2160
6  gates      slideshow · aesthetic · freezedetect · transition audit · audio
7  assembly   PNG sequence → x264 + AAC, faststart
```

### Part D — no invented easing

`refcurve.ts` implements the spec's `extract_camera_speed_curve()` without
OpenCV: ffmpeg decodes the reference to raw RGB, a 10 px block SAD matcher (R=4)
measures per-frame motion, the series is normalised and binomial-smoothed, and
the **integral** of that velocity becomes a position curve. Scene code calls
`e('dolly_in', u)`, `e('orbit', u)`, `e('whip_pan', u)`, `e('drift', u)` — never
a hand-written ease. Penner functions exist in `motion/src/core/easing.ts` and
are used only for UI-state micro-motion.

```bash
npm run film:refcurve -- refs/hero_push.mp4 dolly_in   # replace a curve with your own clip
```

### Part C — multi-pass, enforced

`logs/iteration_log.json` carries, per scene, the design iterations
(`logs/ITERATION_NOTES.md`: what was wrong, what changed) plus every render pass
appended by `render.ts`. Every scene is at 4–5 iterations; the same film was
rendered at 960×540, 1920×1080, 1080×1920 and 3840×2160 stills. No single pass
was treated as final.

### Part E — lighting

`studioEnv()` is a procedural studio: sky/horizon/ground gradient, key, fill and
rim, Blinn specular with a roughness-driven exponent, fresnel rim, and an
environment term weighted by metalness. Scenes choose a rig (`envKey` for hero
product shots, `envWide` for wides). There is no default flat 3-point setup.

### Part G — organic layers

Not used. AnimateDiff weights are behind the same blocked host, and the spec's
own rule forbids generated content replacing procedural geometry. Atmosphere is
procedural: plasma column, bloom, DOF haze, grain.

---

## Shot list (60.000 s, 120 BPM, 0.5 s per beat)

| # | In–out | Scene | Camera curve | Content |
|---|---|---|---|---|
| 1 | 0–6 | Title | `dolly_in` | `WHY IS A GPU / SO EXPENSIVE?` over a GPU package; rule on beat 4 |
| 2 | 6–14 | 01 Silicon area | `orbit` + `dolly_in` | die grid, HBM, gold contacts; live counter → 608 mm² |
| 3 | 14–22 | 02 Yield | `dolly_in` | wafer top-down, clustered defects in amber; yield 100 % → 82 % |
| 4 | 22–30 | 03 Memory | `dolly_in` | 8-layer HBM stacks separating |
| 5 | 30–38 | 04 Lithography | `orbit` | EUV scanner: chamber, mirror stack, plasma column pulsing on the beat |
| 6 | 38–46 | 05 Supply | `drift` | 8 demand towers vs a lagging supply line |
| 7 | 46–54 | 06 Bill of materials | `drift` | cost stack DIE · HBM · PKG · BOARD · MARGIN, labels projected from the geometry |
| 8 | 54–60 | The answer | `dolly_in` | hero package; `IT IS EXPENSIVE / BECAUSE IT IS HARD` |

**Transitions (7 distinct, audited):** hard cut · whip pan · glitch · light
sweep · defocus dissolve · scale punch · wipe.

---

## Measured render cost (2 vCPU, 3 GB, no GPU — 2 worker processes)

| Pass | Resolution | total | per frame |
|---|---|---|---|
| draft | 960×540 | **33.1 min** | 0.52 s |
| hd | 1920×1080 | **65.4 min** | 1.09 s |
| vertical | 1080×1920 | ~1 h | ~1.1 s |
| 4k | 3840×2160 | ~8.4 h (extrapolated from 11.0 s/still) | 11.0 s |

Blender/Cycles on 2 CPU cores at 4K/512 spp is 60–120 s/frame → 60–120 h per
pass, and Parts E/F/G need network access this box does not have. Hence a
from-scratch HDR software renderer: 100 % open source, deterministic, and it
makes the four-pass discipline *affordable* — which is the actual requirement
in Part C.

---

## Commands

```bash
npm run film:audio      # synthesise the 60 s score
npm run film:stills     # 8 hero frames
npm run film:draft      # pass 1  960×540
npm run film:review     # pass 3  1920×1080 + gates
npm run film:final      # pass 4  3840×2160 + gates
npm run film:vertical   # 1080×1920
npm run film:refcurve -- <clip.mp4> <curve_name>
bash tools/film-sheet.sh # contact sheet, one frame per second
```

Requires Node ≥ 22.6 and ffmpeg at `./tools/ffmpeg` (or `FFMPEG=...`).

---

## Source map

```
gpu-film/src/
  engine3d.ts     z-buffered triangle raster, studio env shading, CoC DOF, geometry
  scenes.ts       the film: 8 scenes, measured-curve cameras, one type grid
  refcurve.ts     Part D — curve extraction, integration, plotting
  transitions.ts  seven transition types + the EDL the audit reads
  gates.ts        slideshow / aesthetic / freezedetect / transition / audio gates
  render.ts       CLI: frames → x264, parallel workers, resumable, gates
  audio.ts        60 s score at 120 BPM
```
