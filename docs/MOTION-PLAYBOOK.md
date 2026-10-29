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

- Tracking is animated, not static: `lerp(0.34 → 0.16, easeOutExpo)` reads as the
  word *tightening* into place. (`stage.ts:drawText` accepts `tracking` per call.)
- Per-character state is a pure function of time:
  `{ opacity, scale, offset[x,y,z], rotZ, glow, track }` — that is the entire
  vocabulary needed for kinetic type.
- Depth is a typographic tool: the ghost copy at z = −9.5 behind the word creates
  parallax without adding a single extra element.
- Stroke width is projected per-glyph (`cam.scaleAt(depth)`), so a word moving
  toward the lens thickens the way real neon does.

## 3. Camera choreography

- One camera for the whole film; scenes are *places*, not slides. (`CAMERA_KEYS`)
- Interpolation is a Hermite spline with tangents estimated from neighbouring
  keys → C1 continuity, no velocity pops at key boundaries.
- Easing is applied to the *segment parameter* `u`, not to the position, so
  ease-in/ease-out never introduces a straight-line artifact.
- Micro-shake amplitude is driven by the audio punch envelope: `0.035 × punch`.
  Two octaves of value noise (26 Hz + 61 Hz) so it never reads as a sine.

## 4. Light, not paint

- Render into a **linear HDR** buffer and let values exceed 1.0.
- Bloom = bright-pass → blur → add back. Multi-scale (tight + wide halo) is what
  separates "glow" from "blurry text". (`core/fx.ts:bloom`)
- Tone map with an exponential shoulder, not a clamp:
  `1 − e^(−1.35x)` → highlights roll off, colours keep their hue.
- Tiny amounts: gain 0.8 bloom, 0.9 streak, 0.005 grain. Restraint reads as
  expensive; excess reads as a filter pack.

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
- Keep the window under 200 ms; place it so the *cut* happens at peak.

## 7. Making procedural 3D look designed

- One topology, many silhouettes: morph a unit icosphere onto a torus / cube /
  octahedron by remapping its direction vectors (`wire.ts:shapePoint`). Same edge
  count means no popping.
- Never show a wireframe alone: pair it with orbit rings for silhouette, and put
  type in front of it with a depth gap for readability.
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
