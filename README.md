# Cinema Forge

An experimental documentary video renderer. Its six-beat impact showcase uses hard cuts and contrasting full-screen compositions, not the former radar/HUD world. The script and chart are illustrative and require editorial fact-checking.

## Setup and render

Python 3.11+, Node 22 and `tar` are required. Chromium, FFmpeg and Python dependencies are installed with:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm ci
python ceo_render_app.py --topic "Why Your AI Gives You Wrong Answers" --showcase --offline --resolution 1920x1080 --output renders/final_video.mp4
python qa_video.py renders/final_video.mp4 --sheet renders/qa_contact_sheet.png --resolution 1920x1080
python impact_gatekeeper.py renders/final_video.mp4
python -m pytest -q
npm test
```

The showcase is a naturally paced single-act narration lasting at least 15 seconds. Omit `--showcase` for the longer five-act script, whose duration is extended rather than speeding speech up; the six visual beats repeat every 15 seconds. `--preview` sets 640x360 and at least 30 seconds for the long version. Rendering at 2× resolution with software Chromium can take a long time. A JSON sidecar records timing, voice mode and document boxes; a ReportLab PDF is also saved alongside the MP4.

By default, the app attempts neural `en-US-ChristopherNeural` Edge TTS and Faster-Whisper word timestamps. When Whisper recognition differs from the script it uses Edge word boundaries if available. `--require-online` fails rather than silently substituting offline speech; `--offline` uses eSpeak NG with its own word-start events and inferred word ends. Neither mode guarantees perfect alignment. Audio mastering mixes narration, procedural music, impact transients and room tone, ducks the music, and targets -14 LUFS. Its 4× resampled peak check is not a certified true-peak meter, and AAC encoding may change peaks.

## Visuals and QA

Three.js renders 144 solid metallic fragments, extruded text and an animated tip-following 3D chart. A GLSL raymarcher responds to speech frequency bands. A real ReportLab PDF is rasterized, rotated and highlighted with word coordinates. Hard-cut compositions, shockwaves, deterministic camera shake, timed type and impact audio are followed by the optical finisher on every frame. The finisher includes bloom, vignette, chromatic aberration and grain; 2× captures are downsampled before finishing. These are procedural stylizations, not a simulation of actual data, and not every shot uses physically simulated depth of field or motion blur.

`qa_video.py` checks streams, resolution, fps, sampled contrast and motion and creates a contact sheet. `impact_gatekeeper.py` checks a full-HD 60 fps showcase for six decodable beat samples, palette inversion and sampled intra-beat motion. It deliberately allows hard cuts; neither gate guarantees aesthetic quality or alignment. The older `aesthetic_gatekeeper.py` is intended for continuous-shot footage and is not the impact gate.

The GitHub Actions workflow runs on engine changes pushed to main or this session branch, and supports manual topic, duration, resolution and showcase inputs. Pushes render the 15-second showcase; manual runs can choose a longer render. It checks out and writes to the session branch, requires neural speech and alignment, performs QA, uploads artifacts, and commits the video and sheet. Online services, workflow write permission and sufficient GitHub storage must be available. Files over GitHub's ordinary 100 MiB limit require Git LFS or external storage. Workflow-dispatch UI availability requires the workflow on the default branch.

Licensed fonts and licenses are in `shared_workspace/fonts/`. The chart values are illustrative; generated narration is templated and must be verified by a human.
