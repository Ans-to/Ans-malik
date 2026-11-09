# Continuous morph-and-dive explainer

An AI explainer rendered entirely in headless Chromium at 1920×1080 and 60 fps. React/Remotion supplies the frame clock, Puppeteer seeks GSAP to `frame / 60`, and CSS/SVG/Three.js supply the visual layers. A shared container stretches from prompt to document and chart, opens a globe portal, unfolds a bento grid, and flips into kinetic type. Subsequent word groups reshape the same container while the camera keeps moving. Chart numbers and shapes are illustrative, not measurements.

The narration is a single Edge `en-US-AndrewNeural` take at +12%. A 10 ms RMS envelope compresses silent gaps longer than 70 ms toward 35 ms with cosine crossfades before Faster-Whisper alignment. Three-to-four aligned words form each beat; because actual speech timings are not artificially time-stretched, beat lengths vary with the delivery. Beat timestamps also schedule tactile synthetic Foley. Pedalboard and PyLoudNorm target −14 LUFS, with a 4× oversampled peak ceiling; this is an estimate, not certified true-peak metering, and AAC can change peaks.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python morph_render.py --offline --samples renders/morph-preview
python morph_render.py --offline --output renders/preview.mp4
python -m pytest tests/test_morph.py -q
```

`--offline` uses robotic eSpeak for local previews. GitHub Actions requires online neural TTS and Faster-Whisper; it fails rather than substitute guessed word timings when transcription differs. It renders, fits the video under GitHub's file limit if necessary, verifies it with ffprobe, and creates a ten-beat contact sheet. The workflow listens for `main` and session-branch pushes, and commits output to the session branch; it does not push directly to `main`.

`renders/final_video.mp4` and `renders/qa_contact_sheet.png` are valid only after a successful workflow run. Python is used for audio, alignment, ReportLab texture generation and encoding orchestration, not for drawing video frames. The older documentary/editorial implementations remain for compatibility and are not the active workflow.
