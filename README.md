# MOTION / BY CODE

An 8-second, 120 BPM, code-only motion-graphics film — kinetic typography, a
morphing 3D wireframe, a spline camera move, glitch cuts, bloom/chromatic
aberration, and a synthesised score that the picture is actually locked to.

No After Effects. No Blender. No GPU. No browser. No external footage, fonts or
audio samples. The whole thing is TypeScript + math, rendered to PNG frames and
muxed to H.264 with ffmpeg.

```
motion/out/motion-by-code.mp4     1280×720 · 30 fps · 8.0 s · H.264 + AAC
motion/out/soundtrack.wav         the generated score (44.1 kHz stereo)
```

---

## Run it

```bash
npm run audio     # synthesise the soundtrack, then analyse it back
npm run still     # render a handful of stills (fast sanity check)
npm run render    # 1280×720 @ 30 fps -> motion/out/motion-by-code.mp4
npm run render:1080   # 1920×1080 @ 30 fps
npm run render:60     # 1920×1080 @ 60 fps
```

Requirements: Node ≥ 22.6 (uses native TypeScript stripping — no build step),
and an `ffmpeg` binary at `./tools/ffmpeg` or on `$PATH` (`FFMPEG=/path/to/ffmpeg`).

Useful flags: `--w --h --fps --crf --bloom --aberration --grain --out --keep`.
`--stills=1.2,2.9,6.2` renders arbitrary timestamps instead of the movie.
`--keep` preserves the PNG sequence.

---

## What is actually implemented

| Skill you asked about | Where it lives | What it does |
|---|---|---|
| **Programmatic video framework** | `motion/src/render.ts` | Deterministic frame graph: `t → render → post → PNG → ffmpeg`. Same time, same pixels, every run. |
| **Timeline / keyframes** | `motion/src/scene.ts` (`CAMERA_KEYS`, scene phases) | Time-indexed keyframes with per-segment easing; scenes are functions of `t` only, so any frame renders independently (parallelisable, resumable). |
| **3D engine + camera paths** | `core/math.ts`, `graphics/stage.ts` | Perspective + lookAt matrices, Catmull-Rom/Hermite spline camera with C1 continuity, analytic projection, per-depth stroke width and fog. |
| **3D geometry & morphing** | `graphics/wire.ts` | Procedural icosphere (subdivided, deduped edges) morphed between sphere → torus → cube → octahedron on the beat. |
| **"Shaders" (glow, RGB split, glitch, bloom)** | `core/fx.ts` | Bright-pass → multi-scale blur → bloom, radial chromatic aberration, block datamosh, lens distortion, anamorphic streak, scanlines, vignette, grain. |
| **HDR / tone mapping** | `core/raster.ts` | Additive linear-light Float32 buffer, filmic exponential shoulder, gamma 2.2, ordered dither. |
| **Easing & physics** | `core/easing.ts` | Expo / quint / back / elastic, analytic damped spring, CSS `cubic-bezier()` with Newton inversion, staggered delays. |
| **Kinetic typography** | `graphics/font.ts` + `stage.ts` | A single-stroke vector font defined in code; text is driven per-character (scale, rotate, tracking, Z-offset, glow) — plus 3D extrusion and perspective. |
| **Audio-reactive sync** | `audio/synth.ts`, `audio/analyze.ts` | The score is synthesised sample-by-sample, written to WAV, then re-decoded and analysed: band split, onset detection, autocorrelation tempo estimate, beat-phase snap. Cuts, slams, pulses and camera shake are all driven by that analysis. |
| **Prompt → parameters** | `scene.ts` | "cinematic", "kinetic type", "morphing", "fluid camera", "glitch transition" are the named knobs (`easeOutExpo`, morph `t`, camera spline, `GLITCH_WINDOWS`). |

### Audio → picture contract

`analyze.ts` does no cheating: it decodes the WAV, splits it into three bands
(one-pole filters), takes log-energy positive flux, peak-picks onsets, estimates
tempo by autocorrelation over 70–180 BPM with a musical bias, then snaps the low
band onsets to that grid to recover the phase. On the generated score it reports:

```
120.2 BPM · 17 beats · 165 onsets · 8.00 s
```

Those beats feed `punch(t)`, which every impact scale, glow spike, HUD tick and
camera micro-shake reads. Swap in your own WAV and the picture re-times itself.

---

## The cut

| Time | Scene | Beats |
|---|---|---|
| 0.0–2.0 | **A** — `MOTION` slams letter-by-letter out of Z depth over a perspective floor grid, tracking settles, hologram ghost behind | camera dolly-in, per-letter `easeOutExpo` + impact streaks |
| 2.0–3.5 | **B** — camera orbits right; the wireframe morphs sphere → torus → cube inside three counter-rotating orbit rings; `BY CODE` | parallax orbit, spline ease |
| 3.5–5.56 | **C** — stacked kinetic lines `PIXELS / OVER / TIME`, HUD ticks on the beat, a self-typing prompt, wireframe knot, ghost numeral for depth | staggered per-character slides, frame line draw-on |
| 5.56–7.12 | **D** — the drop: `MOTION` hits the lens with elastic overshoot while the mesh shatters; light-bar sweep | `easeOutElastic`, shatter noise, punch² |
| 7.12–8.0 | **E** — end card: counter-rotating rings, mark resolves, camera settles | ring draw-on, exponential out |

Three glitch transitions (`GLITCH_WINDOWS`) are aligned to the cuts *and* to the
beat grid, so every hard cut is also a musical event.

---

## Why a from-scratch renderer

The usual stack (Remotion / Motion Canvas + React Three Fiber + GSAP) needs a
Chromium + WebGL runtime and a Node package tree. This sandbox has neither
headless Chrome nor a GPU, and third-party binary downloads are blocked — so the
film is rendered the old, portable way: an HDR software rasteriser and a CPU post
stack, wrapped in the same architecture you would use with R3F (scene graph →
camera → draw calls → post → encode). Every module is a drop-in seam: to port to
Remotion, each `sceneX(frame, t)` becomes a component and the FX stack becomes a
shader pass, with no change to the timing model.

---

## Layout

```
motion/src/
  core/math.ts        vec3 / mat4 / projection / splines / noise
  core/easing.ts      easing vocabulary + spring + cubic-bezier
  core/raster.ts      HDR frame buffer, AA lines, glows, tone mapping
  core/fx.ts          bloom, aberration, glitch, streaks, grain, vignette
  core/png.ts         dependency-free PNG encoder
  graphics/font.ts    single-stroke vector font + layout/tracking
  graphics/stage.ts   camera, 3D text, meshes, grid, particles
  graphics/wire.ts    icosphere, shape morphing, particle fields
  audio/synth.ts      the score (drums, sub, pad, riser, impact, reverb)
  audio/analyze.ts    band split, onsets, tempo, beat grid, punch envelope
  scene.ts            the film: camera keys, five scenes, post stack
  render.ts           CLI: frames → ffmpeg
  build-audio.ts      CLI: synthesise + report analysis
```
