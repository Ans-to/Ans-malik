# Mixed-media morph explainer

The active workflow renders a handcrafted archival-to-obsidian visual upgrade over the **locked** natural voice master. `art_render.py` extracts the existing AAC audio with `-c:a copy`, retains its word timestamps and duration, renders only new visuals in Chromium, and verifies the source and output encoded-audio SHA-256 hashes. It does not call TTS, trim silence, change speed, or remix the voice. A prior successful natural-voice render and its JSON metadata must already exist at `renders/final_video.mp4` and `renders/final_video.mp4.json`.

The composition peels apart a halftone paper world into a dark ledger, uses an inked document with animated seal, a mechanical vault and Three.js gold bars, an expanding globe, and a 100-node currency graphic. Circular lenses duplicate and magnify the underlying document and grid at 1.45×. Staggered child movement, velocity-derived tilt and blurred foreground objects provide secondary motion. The portal and tear use composited 2D/3D layers; they are motion-graphics approximations, not physical simulations or ray-traced refraction. The contact sheet includes additional moments for the tear, vault and 88% grid.

The 88% figure is **not global trade**: the BIS reports that the US dollar was on one side of approximately 88% of foreign-exchange trades in its April 2022 survey. The United States suspended conversion for foreign monetary authorities; gold itself did not disappear. Sources: [Federal Reserve History](https://www.federalreservehistory.org/essays/gold-convertibility-ends) and [BIS 2022 survey](https://www.bis.org/press/p221027.htm).

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python art_render.py --source renders/final_video.mp4 --samples renders/art-preview
python art_render.py --source renders/final_video.mp4 --output renders/art-video.mp4
python -m pytest tests/test_art_render.py tests/test_morph.py -q
```

The GitHub workflow renders 1080p60 and verifies the audio packet hash, frame count and metadata before committing the MP4 and contact sheet to the session branch. It listens for `main` and session-branch pushes but does not push directly to `main`. Do not treat older outputs as the visual upgrade until its workflow succeeds. Python is used for the ReportLab document texture and FFmpeg orchestration, not drawing animation frames. Narration timing from Faster-Whisper is approximate.
