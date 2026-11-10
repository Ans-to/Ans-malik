# Restored historical visual layout

The active workflow restores the visual renderer from commit `288d795` with only edge-label removal and timing adjustments. See [RESTORED_STYLE.md](RESTORED_STYLE.md) for timing and audio details.

The following previous workflow is retained for reference and is no longer active.

# Clause-locked narration and layered visuals

The active workflow uses individually synthesized selected-voice WAV files, exact PCM sample windows, and per-frame scene gating. See [CLAUSE_SYNC.md](CLAUSE_SYNC.md) for reproduction, frame-quantization and factual limitations.

The prior visual workflow is retained below for reference, but is no longer active.

# Style C: layered, audio-remapped motion graphics

The active composition restores the multi-plane archival paper world, dossier and 1.45× loupe, center tear, mechanical vault, Three.js globe and dollar, translucent bento network, 88-node grid, and foreground bokeh. Only the tiny top/bottom corner status text was removed; graphic layers still extend across the frame. Reveals use nested clipping, scale and 3D transforms to unfold planes within the same composition. The loupe and portal are composited motion-graphics approximations, not physically simulated refraction.

The locked natural narration and its AAC packets are unchanged. The visual master timeline is authored in a separate clock; `style_clock.py` builds word-timed anchors and `web/morph/timewarp.mjs` maps audio time to GSAP time with a continuous, piecewise-linear function. The tear/vault begins at the saved “gold” timestamp; the portal and currency/bento phases use the spoken “2022” and later “dollar,” and 88-node ignition begins at “88.” The recording has no “rewrote,” “digital,” or “today” word timestamps, so those phrases cannot be literal sync points without replacing the locked narration. Faster-Whisper word times are estimates, not verified phoneme onsets.

The 88% figure refers to US dollar involvement on one side of approximately 88% of **foreign-exchange trades** in the BIS April 2022 survey, not global trade. Sources: [Federal Reserve History](https://www.federalreservehistory.org/essays/gold-convertibility-ends) and [BIS 2022](https://www.bis.org/press/p221027.htm).

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python art_render.py --source renders/final_video.mp4 --samples renders/preview
python -m pytest tests/test_style_clock.py tests/test_art_render.py tests/test_morph.py -q
node --test tests/timewarp.test.js
```

The GitHub workflow requires the previous natural-voice MP4 and timing JSON as the locked source. It stream-copies the AAC, checks its packet hash, renders Chromium frames at 1080p60, checks the remap markers, and publishes a contact sheet with transition samples. Outputs go to the session branch, not directly to `main`. The previous flashcard-specific text-mask and one-object checks do not apply to this intentionally layered composition. Python prepares the ReportLab paper texture and orchestrates the audio copy/encoding; it does not draw animation frames.
