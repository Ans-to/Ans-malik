# Editorial explainer engine

A 15-second, 1920×1080, 60 fps AI explainer built with React/Remotion, GSAP, SVG, CSS and a Three.js icon. The current composition is intentionally specific to the AI topic; other topics are rejected rather than silently paired with unrelated claims. The confidence/evidence figures are illustrative, not measured statistics.

Chromium captures all 900 visual frames. Puppeteer seeks Remotion and GSAP to `frame / 60`, then sends PNG captures through an FFmpeg raw RGB pipe to libx264 (CRF 16, yuv420p). Python prepares only the ReportLab document texture, narration, word timings, audio mix and encoding orchestration. Five separately spoken segments keep each narration phrase within its three-second scene. Faster-Whisper supplies timings when its transcript matches; otherwise exact Edge TTS word-boundary events are used and identified in metadata. Offline eSpeak is for local previews. The yellow marker is timed to “predicts”; final words appear only during their spoken intervals.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python editorial_render.py --offline --output renders/final_video.mp4
python -m scripts.editorial_qa renders/final_video.mp4 renders/qa_contact_sheet.png
python -m pytest tests/test_editorial.py -q
```

`--require-online` requires Edge neural speech and Faster-Whisper; the GitHub render workflow uses this mode. The QA script expects `ffprobe` on PATH and deliberately requires neural speech, so offline previews do not pass final-release QA. Use `--samples renders/sample` to inspect five stills without encoding. The workflow generates and commits the MP4, timing metadata and contact sheet; check its run status before treating tracked output files as current. File-size fitting may re-encode if needed for GitHub's limit.

The sound mix uses soft synthetic UI clicks, filtered paper-like textures, marker and whooshes with a low background bed. Mastering targets −14 LUFS; the reconstructed peak estimate is not a certified true-peak measurement and AAC encoding can change it. Speech recognition timing and the contact sheet are useful checks, not proof of perfect audiovisual synchronization or overall visual quality.

Older documentary entry points and assets remain in the repository for historical compatibility, but are not used by this workflow or the editorial rendering path.
