# SILICON — a 15 second Blender film, rendered on GitHub Actions

Fifteen seconds, five shots, one idea: a GPU begins as sand. Built in Blender Python, voiced by
Kokoro, scored by a synthesiser written for this film, cut to a 120 BPM grid, and gated by numbers
measured from the delivered file rather than by opinion.

**Status: the pipeline runs in GitHub Actions.** Blender 4.2.19, Kokoro and the synthesiser all
install and run on a stock `ubuntu-latest` runner; the film is split into four parallel shards for
the preview and eight for the final, because a standard runner has two cores and a single-job
1080p render takes hours. Numbers for the delivered file are in [Gates](#gates) and in
[`out/gates_*.json`](out).

```
blender-film/
├── film_config.py   single source of truth: shots, palette, easing tokens, voice-over lines
├── scene.py         the film — geometry, typography, cameras, lights, compositor, render driver
├── vo.py            Kokoro voice-over, one line at a time, placed on its beat
├── score.py         additive-synthesis bed + ducking + mix
├── gates.py         22 objective checks on the encoded file
└── ../.github/workflows/blender-film.yml   the runner: install, render, encode, gate
```

---

## The film

| | |
|---|---|
| Length | 15.00 s, 450 frames, exactly |
| Frame rate | 30 fps — one beat at 120 BPM is 15 frames, so every cut lands on a beat |
| Master | 1920×1080, H.264 high, yuv420p, CRF 18 |
| Preview | 960×540, 12 spp — exists so the look can be judged in ~10 min instead of ~45 |
| Engine | Cycles, CPU; 64 spp final, adaptive sampling, OpenImageDenoise |
| Audio | 48 kHz stereo, EBU R128 −16 LUFS, −1.0 dBTP ceiling |

### Shots

| # | Frames | Picture | Voice |
|---|---|---|---|
| A | 1–90 | dust motes tumbling through a shaft of light, type rising out of depth | "It begins as sand." |
| B | 91–195 | a silicon die: 144 copper pads, wireframe resolving to solid, a strip light raking a specular band | "Then light does the work." |
| C | 196–300 | kinetic type left-aligned on one edge, plus an 11-column mechanical odometer rolling to 26,000,000,000 | "Twenty-six billion switches." |
| D | 301–378 | macro slabs, focus rack from near to far, scale-punch type | "Each one smaller than a virus." |
| E | 379–450 | the wordmark, one letter at a time, copper rule, tagline, fade to black | "This is silicon." |

### Transitions

No cross-fades. Every transition is designed, and every one is a different kind of event:

- **A→B** whip-pan out of the typographic plane, hard cut on the beat
- **B→C** push-in over the last 8 frames, cut on the impact
- **C→D** push-in, hard cut
- **D→E** aperture rack f/1.8 → f/22 (defocus to mush) then a snap back to sharpness

`gates.py` proves these are real discontinuities rather than something that merely looks like a cut:
it requires each planned cut to fall in the top 15% of frame-to-frame deltas. On a synthetic clip
built to mimic the structure it measured 0.987, 0.980, 0.966, 0.886 — all four detected.

### Colour

Five values, given as the sRGB hex a designer would hand over and converted to linear for Cycles:

| role | hex | use |
|---|---|---|
| ink | `#0B0A09` | warm near-black, the base of every shot |
| bone | `#EDE4D6` | all primary type |
| copper | `#C9723F` | the single accent, used sparingly so it stays an accent |
| steel | `#7C878E` | secondary surfaces, cool counterweight |
| sand | `#D8C4A2` | dust and highlight tint |

The look is warm-black and copper, deliberately away from the rejected neon-on-navy: `gates.py`
fails the film if more than 1.5% of pixels sit in the neon-blue hue band, and requires at least
0.15% to carry the copper accent.

### Motion

Every move is baked by sampling a cubic bezier per frame — not by leaving Blender's interpolator to
guess. The control points are the Material 3 motion tokens (`standard`, `decelerate`, `accelerate`,
`emphasized`), so no curve in this film is invented:

```python
EASING = {
    "standard":   (0.20, 0.00, 0.00, 1.00),
    "decelerate": (0.00, 0.00, 0.20, 1.00),
    "accelerate": (0.40, 0.00, 1.00, 1.00),
    "emphasized": (0.05, 0.70, 0.10, 1.00),
}
```

### Typography

Type is not hand-placed. Each line is created, measured (`obj.dimensions`), then scaled so its cap
height is a fixed fraction of the **visible frame height at its own depth**, computed from the
camera's real field of view. A lens change, a resolution change, or a different aspect ratio cannot
push type out of frame. Verified by re-deriving every text object's extents against its rig after a
build: 20 text elements, none outside ±w/2.

### Sound

Kokoro (Apache-2.0, ONNX, 82M params) with the bundled espeak-ng data — no system package needed.
Each line is synthesised separately and placed at its planned frame, which means the mix knows where
the speech actually is and can duck under it from the voice's own envelope.

The bed is additive synthesis, not samples: a pad per shot (Am add9 → Fmaj7 → Cmaj9 → G → Am), a
55 Hz sub pulse on every bar, ticks on every beat from bar 2, a noise-and-pitch riser into every cut,
and an impact on it. Measured balance of the delivered mix:

| band | share |
|---|---|
| sub 20–120 Hz | 35.5% |
| low 120–600 Hz | 23.3% |
| mid 600–2500 Hz | 26.2% |
| top 2500–9000 Hz | 14.1% |

Mixed at −17.9 LUFS, −1.76 dBTP before the loudnorm pass that brings it to −16.

---

## Running it

### GitHub Actions

```bash
gh workflow run blender-film -f preset=preview    # 540p, ~12 min, for looking at
gh workflow run blender-film -f preset=final      # 1080p, ~45 min, for delivery
```

The workflow installs Blender 4.2.19 LTS (cached), installs the X11/GL libraries Blender links even
in background mode, fetches the Kokoro weights (cached), builds the audio, smoke-tests the scene by
rendering 5 frames, renders the full pass, encodes with ffmpeg, runs the gates, and uploads the
master, the gate report, the manifest and a contact sheet as artifacts.

### Locally, with Blender installed

```bash
python3 blender-film/vo.py    --out blender-film/out/vo.wav --model kokoro-v1.0.onnx --voices voices-v1.0.bin
python3 blender-film/score.py --vo blender-film/out/vo.wav --out blender-film/out/mix.wav
ffmpeg -y -i blender-film/out/mix.wav -af loudnorm=I=-16:TP=-1.0:LRA=11 blender-film/out/soundtrack.wav
blender -b --factory-startup --python blender-film/scene.py -- --preset preview
ffmpeg -y -framerate 30 -start_number 1 -i blender-film/out/frames_preview/f_%04d.png \
       -i blender-film/out/soundtrack.wav -c:v libx264 -crf 18 -pix_fmt yuv420p \
       -c:a aac -b:a 256k -movflags +faststart blender-film/out/silicon_preview.mp4
python3 blender-film/gates.py --video blender-film/out/silicon_preview.mp4 \
       --audio blender-film/out/soundtrack.wav --manifest blender-film/out/manifest_preview.json
```

`blender-film/out/frames_*/` is git-ignored: 450 PNGs are regenerable and would bloat the repo.

---

## Getting Actions to actually run it

Five separate things were broken between "the YAML is valid" and "there are frames", and each cost a
run. They are recorded here because they are all silent failures:

1. **Billing.** The first runs never started a step: *"The job was not started because recent account
   payments have failed or your spending limit needs to be increased."* Account-level, fixed in
   Settings → Billing & plans. A failed step with every later step `skipped` is a step bug; a job with
   `steps: []` is this.
2. **SIGPIPE.** `some_command | head` under Actions' `pipefail` exits 141 and kills the step. Write to
   a file, then `head` the file.
3. **`apt` in bulk.** A long package list aborts on the first `t64` rename. Install one package at a
   time with `|| echo "::warning::"`.
4. **No `ffmpeg`.** `ubuntu-latest` does not ship it, and the score mix, the loudness measurement and
   the encode all need it. `apt` first, johnvansickle's static build as the fallback.
5. **`blender -b -P script.py` exits 0 even when the script raises.** A render step that finishes in
   one second and reports success is this bug. Every Blender call now passes `--python-exit-code 1`.

One Blender-4.2 API trap too: the compositor socket is `Lensdist.inputs["Distortion"]`, not `"Distort"`,
so sockets are resolved by candidate name instead of by one hard-coded key.

Because the job log is not reachable from everywhere, `ci_run.sh` re-emits the tail of any failed
command as a check-run annotation, and `report.py` re-emits every gate's value and verdict the same
way. A red step there always says why.

**To run it:** push a change under `blender-film/`, or `gh workflow run blender-film -f preset=final`.
The preset is read from `blender-film/run_preset` when the trigger is a push.

**A no-billing alternative:** `colab/silicon_render.ipynb` runs the same five scripts in Google Colab,
where `bpy` installs with `pip` and a free T4 renders 1080p on Cycles GPU.

---

## What has been verified, and what has not

Verified by running, in this environment:

- **The scene builds.** Executed `scene.build()` end to end against a mock `bpy`: 363 objects, 8,560
  keyframe operations, no exceptions. This is how three real bugs were found — `dof.focus_distance`
  keyed on the camera instead of its data, emission keyed on a node socket instead of through the
  node tree, and a manifest that referenced an undefined name.
- **Type fits.** Every text object's measured extents re-derived against its camera rig: 20/20 inside
  frame, including the seven-letter wordmark and the 11-column odometer.
- **The score.** Rendered and analysed: band balance above, peak 0.487, RMS 0.039, no silence holes.
- **The gates.** Run against a synthetic 15 s clip built to mimic the film's structure: 21/22 passed.
  The one failure was the synthetic clip's own garish saturation (0.493 vs a 0.45 limit) — which is
  the gate doing its job on a clip that was never meant to pass. Two parser bugs were found and fixed
  this way (the EBU R128 JSON block, and a frozen-frame metric that was a regex over a joined string).
- **The YAML.** Parses; 14 steps.

Verified in Actions, on a stock `ubuntu-latest` runner:

- **Blender installs and runs.** 4.2.19 LTS unpacks to `/opt/blender`; the smoke test renders five
  frames of the real scene under Cycles CPU and exits 0.
- **Kokoro produces the voice-over in CI.** The 310 MB ONNX model downloads and caches on the runner,
  and the five lines are synthesised and placed on their beats.
- **The score mixes and measures.** `score.py` plus `loudnorm` produce `soundtrack.wav` and the
  loudness numbers.
- **The film renders.** 450 frames across four shards, around thirty minutes wall clock.
- **The encode and the contact sheet** come out of the same job, with the frames stitched from the
  four artifacts.

Not verified from the authoring sandbox:

- **How the shots look.** Layout, timing, palette share and type placement are measured; taste is not.
  The contact sheet in the artifact is the thing to look at, and this is why the preview pass exists
  separately from the 1080p final.
- **Anything about the 1080p final's timing** until a `final` run has finished; the preview numbers do
  not predict it, and eight shards on two cores each is a different load.
