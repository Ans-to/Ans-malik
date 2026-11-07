# The Nixon Shock — documentary renderer

This 15-second cold open uses eleven short Three.js shots: an extruded 1971 monument and archival-style press, a vaulted bullion corridor, electronic ledger structures, debt towers, a geographic globe with trade arcs, and an 88% FX statistic. Bundled Natural Earth 110m land outlines are provided by the `world-atlas` package. Each shot uses a fast arrival, slower glide, and fast exit, with three staggered on-screen elements. Onset times are selected near recognized key-word events where the 1.2–1.6-second shot constraints allow; other words trigger a title pulse rather than guaranteeing a new cut.

The narration makes two important distinctions: in 1971 the US suspended gold conversion for foreign monetary authorities; gold did not vanish from vaults. In April 2022 the US dollar was on one side of about 88% of **foreign-exchange** trades, not all global trade. The BIS 2025 survey reports 89.2%, so the film labels the 88% figure as 2022. Sources: https://www.federalreservehistory.org/essays/gold-convertibility-ends and https://www.bis.org/press/p221027.htm and https://www.bis.org/statistics/rpfx25_fx.htm.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python ceo_render_app.py --topic 'The Nixon Shock' --showcase --offline --resolution 1920x1080 --output renders/final_video.mp4
python qa_video.py renders/final_video.mp4 --sheet renders/qa_contact_sheet.png --resolution 1920x1080
python aesthetic_gatekeeper.py renders/final_video.mp4 --documentary
python -m pytest -q && npm test
```

The headless browser captures each shot at 2× output dimensions. Between shots, the compositor uses foreground pillar occlusion, a portal aperture or a stitched horizontal whip with a 20-tap smear; these use spatial replacement, not a full-frame alpha cross-dissolve. The title and physical geometry are stylized and not literal archival footage. Pillar and portal masks are screen-space compositing, not physically simulated foreground objects. Trade arcs are illustrative connections, not measured transaction flows.

The documentary QA checks shot timing, planned transition types, speed-ramp curves and sampled decoded transition motion. It cannot prove that all frames are free of dissolves or automatically identify unwanted visual subjects; inspect the contact sheet and footage. Audio/video QA independently checks stream presence, resolution, frame rate, contrast and motion. Actions uses Edge TTS Christopher Neural and Faster-Whisper; offline uses eSpeak and its word-event estimates, which can differ from accurate forced alignment. The AI-generated narration is not an actual archival recording. All frames pass through the optical finisher. GitHub Actions fits oversized MP4s under a 95 MiB safety limit before QA and committing outputs; this may reduce image quality.
