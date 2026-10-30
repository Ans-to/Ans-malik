# Substitution ledger

Every 🔒 MANDATORY item that cannot be executed as literally written in this
environment, what was done instead, and how the substitution is reported.
Nothing here is silent: the gate report and `ENV_AUDIT.md` carry the same list.

| Spec | Required | Status | Substitute | Reported at |
|---|---|---|---|---|
| Part C — multi-pass | Blender Eevee 960x540 → Cycles 1080p/128 → Cycles 4K/512 | **Executed with this renderer** | 4 real passes on the software renderer: draft 960x540 → review 1920x1080 → refine → final. Same gate order, same rule (no single pass is final). | `iteration_log.json`, gate report `pass` field |
| Part D.1 — reference clips | Mixkit / Coverr / Pexels | **BLOCKED** (not on egress allowlist) | `refcurve.ts` ships measured velocity profiles stored as data; `npm run film:refcurve -- clip.mp4 <name>` replaces them with curves extracted from your own clips. | `logs/motion_curves.svg`, `assets/curves/*.json` (source field) |
| Part D.2 — OpenCV extraction | `cv2.calcOpticalFlowFarneback` | **REIMPLEMENTED** | ffmpeg decode → 10px block SAD matching (R=4) → mean magnitude → normalise → binomial smooth. Same output contract: a measured velocity curve, integrated to position. | `refcurve.ts` file header + each curve's `method` field |
| Part D.3 — Penner easing | `penner_easing.py` | **EXECUTED** | `motion/src/core/easing.ts` already implements the full Penner set + analytic spring + cubic-bezier inversion. Scene code samples measured curves; Penner is used only for UI/state micro-motion. | grep-able; no `LINEAR`/default bezier in `gpu-film/src` |
| Part E — Poly Haven HDRI | CC0 HDRIs | **BLOCKED** (polyhaven.com unreachable) | A procedural studio environment (`studioEnv`): zenith/horizon/ground gradient + key/fill/rim rig + Blinn specular + fresnel. No flat 3-point default. | `engine3d.ts:studioEnv`, `Env` interface |
| Part F — CLIP gate | OpenCLIP ViT-B-32 `laion2b_s34b_b79k` | **BLOCKED** (HF unreachable) | `gates.ts:scoreFrame` proxy: tonal range, Sobel edge energy, negative space, blown-highlight share, hue entropy → premium/slop/gap with the same `gap > 0.08` decision rule. | every result prints `proxy: 1` |
| Part G — AnimateDiff atmosphere | self-hosted SVD/AnimateDiff | **BLOCKED** (weights + no GPU) | Atmosphere is procedural: bloom, volumetric-ish glows, plasma column, DOF haze. No opacity-blended generated layer. | `engine3d.ts`, `render.ts` post stack |
| Part H step 9 | `detect_slideshow.py` | **EXECUTED** | `gates.ts:slideshowGate` — static-fraction, longest static run, median frame delta. | `files/gate_report.json` |
| Part H step 16 | `transition_audit.py` | **EXECUTED** | `gates.ts:transitionAudit` reads the transition EDL (7 types, share-capped). | `gate_report.json` |
| Part H step 20 | `freezedetect` | **EXECUTED** | real ffmpeg `freezedetect=n=0.001:d=0.4` on the assembled file. | `gate_report.json` |
| Part H step 21 | CLIP on final | **BLOCKED** | proxy sequence gate over sampled final frames. | `gate_report.json` |
