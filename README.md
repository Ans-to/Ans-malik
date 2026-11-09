# Word-locked, center-stage explainer

The active render keeps the existing natural narration **unchanged**, including its AAC packets, timestamps and 15-second duration. Each visible focal object is selected from the actual spoken words, with its earliest frame at least 40 ms after the stored Faster-Whisper start time. Each outgoing object fades away before the next is introduced; this is a fade-through-empty transition, not a literal physical morph. There is never more than one focal object in the active composition.

The locked recording says “In 1971 … ended official dollar conversion into gold … In 2022 … eighty-eight percent of foreign exchange trades.” It does **not** say “rewrote,” “digital,” or “today”; the engine does not fabricate timestamps or show a digital ledger for those absent words. The 88% refers to foreign-exchange trades in the BIS April 2022 survey, not global trade. The visual gold stays in the vault rather than suggesting that gold disappeared. Sources: [Federal Reserve History](https://www.federalreservehistory.org/essays/gold-convertibility-ends) and [BIS 2022](https://www.bis.org/press/p221027.htm).

`qa_inspector.py` reports the stored word timings, unavailable phrases, and cue-frame schedule. The original master did not save Edge TTS WordBoundary events; Faster-Whisper timestamps are estimates, not independently verified phoneme onsets. Accordingly, the 40 ms rule is verified against those estimates, not guaranteed against the actual acoustic onset. On every captured frame Chromium checks DOM geometry and font size, counts focal objects, checks cue visibility, and captures an isolated text mask to check for lit text pixels outside the specified 260 px / 150 px safe zone. This audit assumes all visible text is tagged with `data-audit-text`; it is not general-purpose OCR.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python qa_inspector.py renders/final_video.mp4.json
python semantic_render.py --source renders/final_video.mp4 --samples renders/preview
python -m pytest tests/test_semantic_audit.py tests/test_art_render.py tests/test_morph.py -q
```

The workflow renders 1080p60 using Chromium and preserves the existing AAC by stream-copy; it verifies the AAC packet hash, cue schedule, frame count, and frame-audit report before publishing. A prior successful neural render and its JSON metadata must already exist at `renders/final_video.mp4` and `renders/final_video.mp4.json`. Outputs go to the session branch rather than `main`. Python handles verification and encoding orchestration, not drawing animation frames.
