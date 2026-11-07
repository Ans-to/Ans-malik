# The Nixon Shock — V2 documentary renderer

A twelve-second, 60 fps documentary with single, spoken-word anchor typography. The seven captions—1971, CLOSED, GOLD WINDOW, DIGITAL LEDGERS, DEBT TOWERS, FOUR HUBS and 88%—come from actual narration timing; they are visible only over their timed spoken phrase. Selected spoken-word ends trigger physical pillar, portal and whip transitions. The camera and spatial transition curves use cubic-bezier(0.85, 0, 0.15, 1), with shorter transition windows. Exact word boundaries are estimates provided by Faster-Whisper or the speech engine; they are not independently verified forced alignment.

The 1971 event ended official gold conversion for foreign monetary authorities, not the existence of gold. The 88% refers to foreign-exchange trades in April 2022, not global trade generally. See https://www.federalreservehistory.org/essays/gold-convertibility-ends and https://www.bis.org/press/p221027.htm. The 2025 BIS survey reports 89.2%, so 2022 is spoken in the film: https://www.bis.org/statistics/rpfx25_fx.htm.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python ceo_render_app.py --topic 'The Nixon Shock' --showcase --offline --resolution 1920x1080 --output renders/final_video.mp4
python qa_video.py renders/final_video.mp4 --sheet renders/qa_contact_sheet.png --resolution 1920x1080
python aesthetic_gatekeeper.py renders/final_video.mp4 --documentary
python -m pytest -q && npm test
```

The Three.js scenes include physical-metallic gold with environment reflections and a moving light, projected contact-shadow textures, exponential scene fog, depth-pass bokeh, drifting dust and raised land tiles with thick glowing arcs and hub beacons. Contact shadows and fog are approximations, not ray-traced AO or true volumetric height fog; land plates are instanced sampled tiles. The contact sheet is a limited set of samples and cannot demonstrate every frame or subjective visual quality.

Each anchor pop and cut is accompanied by a frame-scheduled click or stereo whoosh/sub-thud; a filtered 48 Hz drone ramps toward the 88% event. A 3 kHz voice-presence boost is applied. The offline mode uses eSpeak; GitHub Actions requires Edge TTS and Faster-Whisper. The final sentence receives a subtle 0.25-semitone pitch shift without changing its duration; onset alignment remains approximate. The float mastering bus aims for -14 LUFS with a 4× reconstructed -1 dBFS peak check; this is **not** a certified true-peak meter and AAC encoding may change peaks.

V2 QA verifies 720 decoded frames at 60 fps, single-anchor and event metadata, motion at transitions and event-band audio energy at scheduled frames. It is not OCR, cannot prove the absence of every tiny label, and does not independently verify exact lip/word sync or certified dBTP. The workflow re-encodes oversized MP4s to fit GitHub's file limit before QA; this can reduce image quality.
