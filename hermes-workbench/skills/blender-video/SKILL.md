---
name: blender-video
description: "Make Blender video scripts from a one-line brief."
version: 1.0.0
author: ans-malik/arena
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [blender, bpy, video, animation, 3d, rendering, scripting]
    related_skills: [software-development, creative]
prerequisites:
  commands: [blender]
---

# Blender Video

Generate a **headless-safe Blender Python script** from a short brief, verify it by
rendering, and iterate on the look with the user. The user should be able to say
"a spinning donut, 6 seconds, for a landing page" and get a working `.py` plus an
`.mp4` — not an interrogation.

## When to Use

- User wants a Blender script, animation, motion graphic, 3D loop, product turntable,
  title sting, or procedural visual, and wants the *code*, not a `.blend`.
- User has a rough visual idea and wants it rendered.
- User wants an existing bpy script fixed, sped up, or re-styled.

## When NOT to Use

- Image/still generation only → answer directly, no video pipeline.
- Video editing of existing footage (cuts, subtitles) → ffmpeg, not Blender.
- Modelling for 3D printing → geometry accuracy matters, not camera/render.

---

## Step 1 — Intake: at most 3 questions, one batch

Read the brief first. Anything the brief already answers, do not ask again.

Ask **one message, three questions maximum**, each with a default marked, then
proceed whether or not the user answers:

1. **Subject & motion** — what is on screen and what moves? (default: one hero
   object, slow 120° turntable)
2. **Look** — `studio` (clean seamless backdrop), `neon` (dark, emissive rim),
   `editorial` (soft daylight, muted), `tech` (grid, wireframe accents)?
   (default: `studio`)
3. **Shape & length** — aspect + duration, e.g. `16:9 / 6s`, `1:1 / 3s`,
   `9:16 / 10s`? (default: `16:9 / 6s`)

Rules:

- If the user says "just do it", "you decide", or gives no answer → take every
  default and do not ask again.
- Never ask about fps, samples, resolution, codec, or file paths. Those are yours;
  they live in the defaults table.
- If the user answers only one of three, apply defaults to the rest. No follow-up.
- One round of questions per request. The *second* round happens at Step 5, with
  stills in hand — that is where the real look gets decided.

## Step 2 — Write the spec before any code

Emit this block into your reply (it is the contract for the script and for QA):

```json
{
  "subject": "hero object + motion",
  "look": "studio",
  "aspect": "16:9",
  "resolution": [1920, 1080],
  "fps": 24,
  "seconds": 6,
  "frames": 144,
  "engine": "CYCLES",
  "device": "CPU",
  "samples": 64,
  "output": "render/hero_turntable.mp4"
}
```

`frames = fps * seconds`, always. If `frames > 600` or `resolution` is above 1080p,
warn about render time and offer a preview-tier first (see Timing).

## Step 3 — Generate the script (non-negotiable contract)

Every generated script must:

1. `import bpy, math, os, sys, json, argparse` — stdlib + bpy only, no addons.
2. Start with `bpy.ops.wm.read_factory_settings(use_empty=True)` — never inherit
   whatever scene the user has open.
3. Parse options **after** `--`: `python script.py -- --seconds 6 --look studio`.
   Defaults live in `argparse`, so the script runs with no arguments at all.
4. Never call UI-dependent ops (`view3d`, `screen`, `wm.save_mainfile`,
   `wm.quit_blender`, `object.mode_set` on a hidden object). Headless = no window.
5. Set, explicitly: `scene.render.fps`, `resolution_x/y/percentage`,
   `frame_start/frame_end`, `render.engine`, `cycles.device`, `cycles.samples`,
   `render.image_settings.file_format`, `render.filepath`.
6. Use `math.radians()` for every rotation. Degrees passed raw are the #1 silent
   visual bug.
7. Be deterministic: seed anything random (`random.seed(...)`), no `time.time()`
   in animation logic.
8. Write a manifest next to the output — `{"frames":…, "fps":…, "seconds":…,
   "resolution":[…], "engine":…, "output":…}` — so QA can verify without guessing.
9. Keep H.264 targets **even** in both dimensions (odd width/height → encoder error).
10. One `main()` guarded by `if __name__ == "__main__":`. Under `bpy` as a module,
    `__name__` is `__main__` only when run as a script; also call `main()` when
    executed via `blender -b -P`.

Start from `templates/turntable.py` — it satisfies all ten and is verified.

## Step 4 — QA ladder (do not skip a rung)

**Rung 1 — static** (~1s, no Blender needed):

```bash
python3 scripts/qa_check.py my_scene.py        # JSON report, non-zero exit on failure
```

Catches: missing factory reset, unset fps/resolution/output, degree/radian slips,
odd dimensions for H.264, frames ≠ fps×seconds, UI-only ops, no `--` parsing.

**Rung 2 — smoke render** (one frame, low res, few samples). This is the rung that
proves the script actually runs:

```bash
#   4 samples, 320x180, frame 1 only
blender -b -P my_scene.py -- --preview --samples 4 --width 320 --height 180 --frames 1
```

Then confirm the PNG exists and is not blank/black (file size > ~1 KB and not a
single flat colour — `scripts/qa_check.py --check-frame <png>` does both).

**Rung 3 — full render**, only after rung 2 is green. Report elapsed time and file
size. If it exceeds ~5 minutes, stop and offer a lower-fidelity pass instead.

If Blender is not installed but the `bpy` module is: run with
`python -m bpy`-style invocation, or `LD_LIBRARY_PATH` workaround on Linux (see
`references/bpy-recipes.md` → Headless notes).

## Step 5 — Show, then ask (the second QA round)

Render 3 stills — 10%, 50%, 90% of the timeline — and present them. Then ask
**one** question: *"Which of these should change — framing, lighting, or pacing?"*
Offer at most three concrete options and a "looks good" exit.

Only re-render what changed: a lighting tweak is a still frame, a camera change is
a still frame, a pacing change is a preview-tier animation. Never re-render the
final to answer a look question.

## Step 6 — Deliver

Report, in the user's units: one paragraph of what it shows, the script path, the
video path (with size and duration), the exact command to re-render at full quality,
and one line of what to tweak first. No restating the script in prose.

---

## Defaults

| Setting | Default | Notes |
|---|---|---|
| Engine | `CYCLES`, `device='CPU'` | EEVEE needs a GPU/GL context — fails in headless CI |
| Samples | 64 | 4 for preview, 16 for look-dev, 128+ for final |
| fps | 24 | 30 for UI/tech, 60 only for fast motion |
| Resolution | 1920×1080 @ 100% | preview tier: 640×360 @ 50% |
| Duration | 6s | 3s for loops, 10s+ for explainers |
| Codec | `FFMPEG` / `MPEG4` / `H264` | PNG sequence if the user needs alpha |
| Color | `AgX` view transform | `Filmic` on Blender < 4.0 |
| Motion | linear or eased 120° arc | constant speed reads as "cheap" |

## Timing math (state this to the user before a long render)

Rough Cycles CPU cost: `samples × megapixels × frames × ~0.6s`. A 1920×1080,
64-sample, 144-frame turntable is ~1.5–4 min per machine core-hour budget. Always
quote an estimate before starting a final render, and prefer preview tier until the
user has approved a still.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Black frame | no light, or camera inside geometry | add AREA light + check camera location |
| `Cannot read file` | `scene.render.filepath` points at a directory that does not exist | `os.makedirs(..., exist_ok=True)` |
| Encoder error / zero-byte mp4 | odd resolution, or codec unset | even dimensions, set `ffmpeg.format`/`codec` |
| Everything is flat grey | `samples=1` with no denoise, or world strength 0 | bump samples, set world background |
| Animation does not move | keyframes on frame 1 only, or `frame_end` = 1 | keyframe twice, set `frame_end` |
| Rotation looks wrong | degrees passed where radians expected | wrap in `math.radians()` |
| Works in GUI, fails headless | UI op or missing context | replace with data-API calls (`obj.location = …`) |

## Files

- `templates/turntable.py` — verified reference script, all ten contract rules.
- `references/bpy-recipes.md` — copy-paste snippets: scene reset, camera aim,
  turntable rig, lights, materials, text objects, geometry spin, output, headless notes.
- `scripts/qa_check.py` — static contract checker + frame sanity check.
