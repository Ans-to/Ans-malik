# Audio-led continuous morph explainer

A Chromium/React/GSAP/Three.js motion-graphics explainer about the 1971 end of official dollar-to-gold conversion and the dollar's role in foreign exchange. The 88% figure is **not global trade**: the BIS reports that the US dollar was on one side of approximately 88% of foreign-exchange trades in its April 2022 survey. The United States suspended conversion for foreign monetary authorities; gold itself did not disappear. Sources: [Federal Reserve History](https://www.federalreservehistory.org/essays/gold-convertibility-ends) and [BIS 2022 survey](https://www.bis.org/press/p221027.htm).

Edge `en-US-AndrewNeural` speaks at +0%, without time-stretching to fit a target. Only interior low-RMS pauses longer than 500 ms are capped at about 280 ms, cutting at the quiet centre; natural short pauses remain untouched. The narration receives 150 ms lead-in and 400 ms tail padding. Faster-Whisper runs after this preparation, and the resulting audio length determines the frame count. Beat grouping follows word timing while camera motion continues independently. Numbers and charts in the visuals are illustrative unless explicitly attributed to the BIS.

A gentle high-pass, low-shelf/peak warmth, and 2.5:1 compressor process the voice. Foley RMS is limited to at least 18 dB below the vocal RMS. Pedalboard/PyLoudNorm target −14 LUFS and a 4× oversampled peak estimate; this is not certified dBTP, and AAC may change peaks. RMS silence detection is conservative, not a guarantee of perfect phoneme boundaries; listen to the neural result when evaluating cadence.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python morph_render.py --offline --samples renders/morph-preview
python morph_render.py --offline --output renders/preview.mp4
python -m pytest tests/test_morph.py -q
```

Offline previews use robotic eSpeak and its approximate word events; they do not demonstrate the online voice's cadence. GitHub Actions requires neural Edge TTS and Faster-Whisper, renders 1080p60 in Chromium, checks the video, and produces a beat contact sheet. It listens for `main` and session-branch pushes but commits generated outputs to the session branch, not directly to `main`. Older outputs should not be treated as the new render until the workflow succeeds. Python is used for audio, alignment, the ReportLab document texture, and encoding orchestration, not for drawing video frames.
