# The motion-design playbook this project encodes

A short, opinionated map from *visual language* to *code*. Every rule below is
implemented somewhere in `motion/src/` — the file is named in the margin.

---

## 1. Timing is the whole job

| Principle | Code |
|---|---|
| Never animate linearly on screen; animate with exponential-out for "snap" | `easeOutExpo` / `easeOutQuint` — `core/easing.ts` |
| Anything that arrives with weight overshoots by ~8–12 % | `easeOutBack(1.7)` |
| Only one thing per film may overshoot big: the hero beat | `easeOutElastic` on the drop, `scene.ts:sceneD` |
| Cameras settle, they do not stop dead | analytic damped spring `spring(1, 0.55, 12)` |
| Stagger everything at 30–60 ms per glyph | `charIn(t, start + i * 0.035, …)` |
| Anticipate before a slam: 6 % drift against the move for 80 ms | `offset: -0.06` on the pre-roll |

## 2. Typography as geometry

- Use **one** face, **one** weight, **big**, with negative space around it. The
  face here is a filled monoline display typeface defined in code
  (`graphics/type.ts`): heavy capsule stems, butt caps on axis-aligned cuts,
  round joins everywhere else.
- Tracking is animated, not static: `lerp(+0.16 → −0.035, easeOutQuint)` reads as
  the word *tightening* into place.
- Per-character state is a pure function of time:
  `{ opacity, scale, offset, rotZ, reveal, wipe }` — that is the whole vocabulary
  needed for kinetic type. `reveal` (bottom-up) and `wipe` (left-to-right) are
  screen-space masks, so they cost nothing extra.
- Set type on a **baseline**, not a centre. Boxes that grow upward from a
  baseline are why real layout looks stable while it animates.
- Scale is projected per glyph (`cam.scaleAt(depth)`), so type moving toward the
  lens gains weight the way it does through a real optic.
- The single strongest motion for display type is the *contrast pair*: a hard
  cut/wipe in one direction, then a settle in the other with
  `easeOutQuint`/`easeOutElastic`.

## 3. Camera choreography

- One camera for the whole film; scenes are *places*, not slides. (`CAMERA_KEYS`)
- Interpolation is a Hermite spline with tangents estimated from neighbouring
  keys → C1 continuity, no velocity pops at key boundaries.
- Easing is applied to the *segment parameter* `u`, not to the position, so
  ease-in/ease-out never introduces a straight-line artifact.
- Micro-shake amplitude is driven by the audio punch envelope: `0.035 × punch`.
  Two octaves of value noise (26 Hz + 61 Hz) so it never reads as a sine.

## 4. Light, not paint

- Render into a **linear HDR** buffer and let values exceed 1.0 — but only the
  accent should. If the body colour also blows out, everything reads as "glowing
  text" and the hierarchy collapses. (Bone type at 0.86, accent at 1.25.)
- Bloom = bright-pass → blur → add back, with a **high threshold** (0.95) so it
  touches only the accent. `core/fx.ts:bloom`
- Tone map with an exponential shoulder, not a clamp: `1 − e^(−1.35x)`.
- Restraint is the whole trick: 0.32 bloom, 0.35 px aberration, 0.004 grain.

## 4b. Composition

- One accent per frame, and one *job* per frame. If three elements compete, the
  frame reads as a template.
- Use print furniture — hairlines, index numerals, leader rules, tickers,
  credits — to make a moving frame feel *designed* rather than *rendered*.
- Let large shapes be cropped by the frame edge. Centred, fully-visible, evenly
  spaced elements are the signature of generated work.
- Negative space is a material. Aim for roughly a third of the frame empty.

## 5. Audio-reactive, honestly

- The picture is not synced to a hard-coded BPM: `analyze.ts` decodes the WAV,
  splits bands, detects onsets, estimates tempo by autocorrelation, then snaps
  the low-band onsets onto the grid to recover phase.
- Two envelopes are used everywhere:
  - `punch(t)` — sum of exponential decays from every kick (camera shake, scale
    pops, glow spikes, HUD ticks);
  - `rmsAt(t)` / `lowAt(t)` — slow energy (background lift, particle brightness).
- Cuts land inside glitch windows which themselves straddle detected beats, so
  the edit and the music agree.

## 6. Transitions

- A glitch is cheaper and more convincing than a dissolve between two *neon*
  shots: the shots already share a black background.
- Glitch recipe: row-band displacement + per-band RGB split + dropped scanlines
  + hard-edged blocks sampled from elsewhere in the frame (`fx.ts:glitch`).
- Keep the window under 200 ms and **dial the amplitude to 0.5–0.7**: used at
  full strength it destroys the comp instead of masking the cut.
- The best transition in an editorial piece is still a hard cut with a 120 ms
  accent flash. Glitch is a garnish.

## 7. Making procedural 3D look designed

- One topology, many silhouettes: morph a unit icosphere onto a torus / cube /
  octahedron by remapping its direction vectors (`wire.ts:shapePoint`). Same edge
  count means no popping.
- **Use 3D as a supporting element.** A wireframe carrying the whole film reads
  as a tech demo; the same object at 22 % opacity, cropped by the frame and
  sitting behind type, reads as art direction.
- One mesh, one colour, no glow rings, no orbiting planets.
- Shatter = per-vertex hash noise scaled by the audio punch; the topology stays
  intact, so it reads as an object breaking, not as a mesh error.

## 8. Determinism

`t → frame` is a pure function: no `Math.random()` (hash noise instead), no
wall-clock, no GPU. Frame 137 renders identically today and next year, which is
what makes the render resumable, parallelisable and diffable.

---

## Porting to the conventional stack

| Here | Remotion | Motion Canvas | Three.js / R3F |
|---|---|---|---|
| `scene.render(t)` | `<Sequence>` + `useCurrentFrame()` | `yield*` generator with `waitFor` | `useFrame` |
| `CAMERA_KEYS` spline | `interpolate()` chain | `all(...)` tweens | `CatmullRomCurve3` |
| `drawText()` | absolutely-positioned styled text | `Txt` node | `TextGeometry` / troika |
| `fx.ts` | CSS filters or a GLSL pass | canvas filters | `EffectComposer` (UnrealBloom, RGBShift) |
| `analyze.ts` | runs once, output baked to JSON | same | same |

The timing model (`t`-only, easing-as-data, per-character state objects) transfers
unchanged; only the drawing calls get swapped for the host renderer.

---

## 8. What the 60-second GPU film added

The 8 s piece proved the engine. The 60 s explainer forced four new disciplines.
Each one is a rule now, and each is enforced by code rather than taste.

### 8.1 Motion is measured, not felt

| Principle | Code |
|---|---|
| A camera move may only come from a curve extracted from reference footage | `gpu-film/src/refcurve.ts` |
| Extract: decode → block-match → mean velocity → normalise → smooth | `extractMotionCurve()` |
| Sample position, never velocity: integrate the measured speed | `toPosition()` |
| One curve per idea (`dolly_in`, `orbit`, `whip_pan`, `type_slam`, `drift`), reused across scenes | `assets/curves/*.json` |
| Easing functions are reserved for UI-state micro-motion, never for camera paths | `motion/src/core/easing.ts` |

A hand-tuned `easeInOutCubic` on a dolly reads as "animation". An integrated,
measured velocity profile reads as "operated camera". That difference is the
entire premium/slop gap on a product film.

### 8.2 Two cameras, never one

- **World camera** — the 3D camera (`cam`). Perspective, DOF, everything in space.
- **Graphics camera** — a flat orthographic-like layer (`tcam`, fov = 2·atan(0.5))
  whose half-height is exactly 1.0. Type, rules, labels and stats live here.

Layout is expressed in **frame fractions** (`at(x, y)`, `sz(frac)`), so the same
composition survives 16:9, 9:16 and 4K. Type through the world camera is the
classic beginner bug: it scales with the lens, it goes out of frame at other
aspect ratios, and it can never be re-flowed.

### 8.3 Depth of field is a CoC field, not a blur filter

`applyDOF(focus, aperture, maxRadius)` computes per-pixel circle-of-confusion
from the z-buffer, smooths the field 5×5 so contours do not show, then blends
between three blur pyramid levels. A fixed-radius blur is what makes amateur
renders look like a blurry render; a CoC field looks like a lens.

### 8.4 Every gate is a number

| Gate | Pass rule | Code |
|---|---|---|
| Slideshow | static fraction ≤ 0.18, longest static run ≤ 24 f, median Δ ≥ 0.0015 | `slideshowGate` |
| Freeze | `freezedetect=n=0.001:d=0.4` → ≤ 2 hits | `freezeGate` |
| Transition variety | ≥ 5 distinct types, no type > 45 % of cuts | `transitionAudit` |
| Aesthetic | premium−slop gap > 0.08, fail share ≤ 20 % | `scoreSequence` |
| Audio | mean −30…−12 dB, peak < −0.5 dB | `audioGate` |

### 8.5 Transitions are a vocabulary, not a default

Seven types, each with a job: `hard_cut` (statement), `whip_pan` (momentum
carry), `glitch` (data shock), `light_sweep` (reveal), `defocus_dissolve`
(memory/time), `scale_punch` (impact), `wipe` (section change). The EDL is data,
so the audit gate can read it. Six cuts that all dissolve is a slideshow with
extra steps.
