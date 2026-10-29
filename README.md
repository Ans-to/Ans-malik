# MOTION / BY CODE

An 8-second, 120 BPM motion-graphics film made entirely in TypeScript — no After
Effects, no Blender, no GPU, no browser, no stock footage, fonts or samples.

```
motion/out/motion-by-code-1080p.mp4   1920×1080 · 30 fps · 8.0 s · H.264 + AAC
motion/out/contact-sheet.png          24-frame overview of the cut
motion/out/soundtrack.wav             the generated score (44.1 kHz stereo)
```

---

## Run it

```bash
npm run audio         # synthesise the score, then analyse it back
npm run still         # a handful of stills (fast sanity check)
npm run render:1080   # 1920×1080 @ 30 fps -> motion/out/motion-by-code-1080p.mp4
npm run render        # 1280×720 preview, ~4x faster
```

Requires Node ≥ 22.6 (native TypeScript stripping — no build step) and an
`ffmpeg` binary at `./tools/ffmpeg` or on `$PATH` (`FFMPEG=/path/to/ffmpeg`).

Flags: `--w --h --fps --crf --bloom --aberration --grain --out --keep`.
`--stills=1.2,2.9,6.2` renders arbitrary timestamps instead of the movie.

---

## Art direction

Editorial dark, not neon template:

* warm near-black ground, one soft off-centre pool of light;
* **bone-white display type at architectural scale** — one face, one weight,
  used big, with generous negative space;
* **one accent** — hot vermilion — reserved for a single word per scene and for
  hairline rules;
* hairline rules, index numerals, leader lines, ticker bands: print/grid
  furniture rather than glow;
* a sparse wireframe solid, used only as a depth element and cropped by frame;
* post: bloom on hot values only, a whisker of chromatic aberration, film grain,
  gentle vignette. No scanlines, no rainbow split, no lens dirt.

The type is a **filled monoline display face defined in code**
(`graphics/type.ts`): heavy capsule stems, butt terminals on axis-aligned cuts,
per-glyph coverage masks so overlapping strokes union instead of double-adding,
and per-character state (`scale`, `offset`, `wipe`, `reveal`, `rotZ`) so kinetic
animation never touches the outline data.

---

## The cut

| Time | Scene | What happens |
|---|---|---|
| 0.00–2.00 | **A — statement** | A hairline rule draws across the frame; `MOTION` rises out of it as a bottom-up reveal, tracking tightening from +0.16 to −0.035 em; caption, credit block and a scrubber that fills on the beat |
| 2.00–3.50 | **B — editorial** | Glitch cut. Index `01`, `KINETIC / TYPOGRAPHY` wiped on character by character, leader rule drawing itself, sparse icosphere→octahedron morph on the right, cropped by frame |
| 3.50–5.50 | **C — stack** | `PIXELS / OVER / TIME` slams in line by line from alternating directions, accent on the middle line, leader rules, top ticker band, ghost numeral `03` |
| 5.50–7.00 | **D — drop** | Glitch cut on the beat, `MOTION` lands from 1.34× with elastic settle and a short vertical smear, accent rule snaps out from centre, `BY CODE` sets underneath |
| 7.00–8.00 | **E — end card** | Wordmark wipes on, accent rule, credit line |

Three glitch transitions, each timed to straddle a detected beat so the edit and
the music agree.

---

## Audio → picture

`audio/synth.ts` composes the score sample-by-sample (kick, snare, hats, sub,
pad, riser, impact, small reverb). `audio/analyze.ts` then **re-decodes the WAV
and measures it** — three-band split, log-flux onset detection, autocorrelation
tempo estimate with a musical bias, then beat-phase recovery by snapping the
low-band onsets to the grid. On the generated score it reports:

```
120.2 BPM · 17 beats · 165 onsets · 8.00 s
```

Every scale pulse, glow lift, camera micro-shake and HUD tick reads the `punch`
envelope built from those beats. Swap in your own WAV and the picture re-times
itself.

---

## What is implemented, by skill

| Skill | Where | Notes |
|---|---|---|
| Programmatic video framework | `render.ts` | `t → frame → PNG → ffmpeg`; deterministic, resumable, parallelisable |
| Keyframes & easing | `scene.ts`, `core/easing.ts` | Hermite camera keys, expo/quint/back/elastic curves, analytic damped spring, CSS `cubic-bezier()` with Newton inversion |
| 3D engine & camera paths | `core/math.ts`, `graphics/stage.ts` | perspective/lookAt, C1-continuous spline camera, analytic projection, per-depth stroke radius and fog |
| Procedural 3D | `graphics/wire.ts` | subdivided icosphere with deduped edges, direction-remapped morph targets |
| Shader-style post | `core/fx.ts` | bright-pass→multi-scale bloom, radial chromatic aberration, block datamosh glitch, lens distortion, anamorphic streak, scanlines, vignette, half-res grain |
| HDR pipeline | `core/raster.ts` | additive linear-light Float32 buffer, filmic exponential shoulder, gamma 2.2, 8×8 ordered dither |
| Kinetic typography | `graphics/type.ts` | filled display face baked in code, coverage-mask rasteriser, per-character wipe/reveal/scale/offset |
| Audio reactivity | `audio/*` | as above |
| Prompt → parameters | `scene.ts` | the shot list and its vocabulary (wipe, reveal, leader rule, smear, elastic land) are named, tunable functions |

---

## Why a from-scratch renderer

Remotion / Motion Canvas + R3F + GSAP need Chromium and WebGL, which this
environment does not have. So the film is rendered the portable way: an HDR
software rasteriser plus a CPU post stack, wrapped in the same architecture you
would use with R3F (scene → camera → draw calls → post → encode). Every module is
a drop-in seam — see `docs/MOTION-PLAYBOOK.md` for the porting table.

---

## Layout

```
motion/src/
  core/math.ts        vec3 / mat4 / projection / splines / value noise
  core/easing.ts      easing vocabulary + spring + cubic-bezier
  core/raster.ts      HDR frame buffer, AA lines, glows, tone mapping + dither
  core/fx.ts          bloom, aberration, glitch, streaks, grain, vignette
  core/png.ts         dependency-free PNG encoder
  graphics/type.ts    filled display face + coverage-mask text rasteriser
  graphics/stage.ts   camera, wireframe mesh drawing, euler transform
  graphics/wire.ts    icosphere, shape morphing
  audio/synth.ts      the score
  audio/analyze.ts    band split, onsets, tempo, beat grid, punch envelope
  scene.ts            the film: camera keys, five scenes, post stack
  render.ts           CLI: frames -> ffmpeg
  build-audio.ts      CLI: synthesise + report the analysis
```
