# Continuous morph documentary renderer

`morph_render.py` synthesizes the monetary-history script with Edge TTS Andrew at +12%, compresses interior low-RMS gaps over 70 ms to 35 ms with a 10 ms equal-power crossfade, then uses Faster-Whisper word timestamps to group three or four words per beat. The group compiler optimizes toward 1.15 seconds, but cannot guarantee 1–1.3 second durations without changing the speech. The aggressive energy-based trimmer can remove quiet consonants or meaningful pauses; listen to the output. Whisper timestamps are estimates, and display is quantized to 60 fps, not millisecond-accurate ground truth.

Chromium, React, GSAP, SVG and Three.js render the continuous archival-to-dark composition; the document texture is generated with ReportLab. A shared container transitions between prompt, document, illustrative chart, globe portal, bento and kinetic type. The line-to-chart and portal effects are composited motion-graphics approximations, not literal continuous material deformation or a physical camera. Foley is generated at the aligned beat starts; loudness is targeted to -14 LUFS and a 4x oversampled -1 dB ceiling before AAC encoding (the encoded output can differ).

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python morph_render.py --require-online --output renders/final_video.mp4
python -m scripts.morph_qa renders/final_video.mp4 renders/qa_contact_sheet.png
python -m pytest -q && npm test
```

The workflow runs on pushes to `main` and `arena/fa1317bb-ans-malik` or manual dispatch. It checks out and pushes generated outputs **only to the session branch**, not `main`. It requires internet access for Edge TTS and the Faster-Whisper model download. Output files and metadata are uploaded as an artifact and committed only after QA. `art_render.py` remains available for visual-only renders against a previously locked master.

The 88% figure is **not global trade**: in April 2022 the dollar was on one side of approximately 88% of foreign-exchange trades, according to the [BIS](https://www.bis.org/press/p221027.htm). The United States suspended official foreign conversion; gold did not disappear ([Federal Reserve History](https://www.federalreservehistory.org/essays/gold-convertibility-ends)).
