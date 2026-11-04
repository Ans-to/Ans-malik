# Cinema Forge

An experimental documentary renderer. It creates five procedural scenes, finishes every frame in Python, and encodes H.264/AAC MP4. It is not a researched documentary generator or a guarantee of studio-grade output.

## Setup and render

Python 3.11+, Node 22 and `tar` are required. On Linux, `npm ci` installs Puppeteer, Three.js, GSAP, and a Chromium build; its packaged shared libraries are extracted to a temporary directory. FFmpeg comes from `imageio-ffmpeg`, with no system install required.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm ci
python ceo_render_app.py --topic "Why Your AI Gives You Wrong Answers" --duration 60 --resolution 1920x1080 --output final_video.mp4
python qa_video.py final_video.mp4 --sheet qa_contact_sheet.png --resolution 1920x1080
python aesthetic_gatekeeper.py final_video.mp4
# Smaller draft; narration stays at normal speed (at least 30 seconds):
python ceo_render_app.py --topic "Why Your AI Gives You Wrong Answers" --preview --output preview.mp4
```

Defaults are 60 seconds, 1920x1080, 60 fps. The duration is a **minimum**: each of the five scenes lasts at least six seconds and expands when necessary to fit unmodified narration and approximately 145 words per minute. The five-scene minimum is therefore 30 seconds, not 15–20 seconds. `--preview` uses 640x360 and a 30-second minimum, but a long script will extend it further. Full HD software rendering is computationally intensive. The `.mp4.json` sidecar records requested and actual duration, script, speech mode, timestamps and PDF word boxes; `.mp4.brief.pdf` contains the generated classified brief.

The **Render documentary** workflow runs on manual dispatch and on engine changes pushed to `main` or the session branch. It renders with `--require-online`, so a failure to get neural speech or reliable timing fails the job rather than silently committing an offline result. After QA, it uploads artifacts and commits `renders/github_action_masterpiece.mp4` and the contact sheet (plus sidecars) to `arena/fa1317bb-ans-malik`. A main-branch trigger also checks out and renders this session branch; it does **not** write to main. Generated-only commits do not match the engine path filters, preventing a render loop. The MP4 uses Git LFS to support files over GitHub's 100 MiB Git blob limit; LFS storage/bandwidth and workflow write permissions must be available. Workflow-dispatch availability through GitHub's UI requires this workflow file to exist on the default branch. The older `renders/final_video.mp4` is a historical five-second preview, not output from the current pacing policy.

## Pipeline

1. A five-act template script is spoken per act. The renderer automatically attempts Edge TTS with Christopher Neural at rate -5% and pitch -2 Hz, then downloads/loads Faster-Whisper `base.en` and requests word timestamps. If Whisper's words differ from the script, Edge's own word-boundary timestamps are used when they match; Whisper still runs, but those scenes are marked separately in the sidecar. Without online services the renderer falls back to bundled eSpeak NG at 145 wpm and uses its word-start events; word ends are inferred from the next event. `--offline` skips the probe; `--require-online` instead fails if reliable neural speech/alignment is unavailable. `--whisper-model` selects another model name or local model directory. Speech is never sped up to fit a scene; the timeline expands instead. Offline timings are not independently verified forced alignment.
2. The `SevenLayerCompositor` constructs each frame on a 2x canvas: gradient/grid and timecode, parallax, subject-derived ambient shadow, scene subject, frosted HUD, editorial typography and timed subtitles, and atmospheric particles. It rejects layers with no alpha or spatial variance. The classified brief is a ReportLab PDF, rasterized by PyMuPDF; recorded word boxes drive the highlighter. OpenCV projects a rotating 3D plane and applies edge blur. The illustrative chart has an area fill, two curves, and a tabular numerical counter; the network projects 180 animated nodes. The hero is Three.js and GSAP rendered deterministically in headless Chromium with SwiftShader, three-point lighting, metallic material, exponential fog and a Bokeh pass.
3. The compositor downsamples with `INTER_AREA` and sends every frame to the optical finisher before FFmpeg. The finisher applies quarter-resolution Gaussian bloom (an approximation of sigma 18 at full resolution), a Numba vignette and seeded grain pass, and chromatic aberration.
4. The audio bus mixes the voice, dark procedural music and room tone, ducks beneath voice, and pre-normalizes to -13.5 LUFS before a limiter and a final -14 LUFS correction. A lookahead gain envelope and a final 4x `resample_poly` check cap that particular reconstructed float signal at -1 dBFS. This is **not a certified ITU-R BS.1770-4 true-peak meter**: different reconstruction filters and AAC encoding can yield higher peaks. A strict peak limit and exact loudness can also be incompatible. Verify delivery files with a calibrated broadcast meter and adjust the source mix.

## Limitations and QA

- Script generation is templated, not researched or genuinely tailored to arbitrary topics; the chart values are explicitly illustrative. Human fact-checking and editorial work are required.
- Offline timing marks are generated by the speech engine, not verified by Whisper. Online Whisper requires model download/network availability; Edge word boundaries are substituted when Whisper recognition differs from the script. The 145 wpm policy controls offline synthesis and timeline allocation; the neural voice uses the requested Edge rate and its exact instantaneous speaking rate may vary.
- The document's blur is a screen-space approximation rather than physically simulated depth of field. Heading entrances use a SciPy damped spring with ten temporal samples for approximate motion blur; other scene transitions do not yet have full camera-motion blur. The Three.js hero uses GSAP for camera/object motion; it is not a Remotion composition.
- `qa_video.py` checks streams, resolution, 60 fps, sampled contrast and sampled motion, and creates a contact sheet. `aesthetic_gatekeeper.py` additionally rejects video below 1080p and checks ten sampled frames for Sobel edge density, 3×3 spatial coverage, and shadow/midtone/highlight presence. Its blur suppresses grain before the edge test. Both are numerical heuristics, not guarantees of professional visual quality, narration intelligibility, alignment accuracy, or broadcast compliance. The strict aesthetic gate intentionally rejects previews.

`design_system/palettes.json` is the palette source. Licensed Google Fonts and their OFL licenses are in `shared_workspace/fonts/`; `python scripts/download_fonts.py` refreshes them from upstream. Shared CSS, motion and Three.js utilities live in `web/`; Python springs live in `forge_python/motion/`. `forge_python.assemble` can finish pre-rendered compatible chunks before concatenation. The standalone master is `python -m forge_python.audio_mastering.pedalboard_master music.wav voice.wav master.wav`.

Run `python -m pytest -q` and `npm test` for unit and encoding/decoding smoke tests, including offline speech, PDF creation, peak checks, compositor-layer validation, empty/grain-only gate tests and a real Puppeteer render.
