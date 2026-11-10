# Historical style restore

The active visual source (`web/morph`) was restored from commit `288d795`, the last output commit before `ef544c7` introduced centered semantic visuals. The original layout, visual assets, CSS and animation shapes remain; the top header and bottom corner source label were removed, and timeline cue times are adjusted against the current independently synthesized narration. `restore_render.py` copies the existing AAC packets unchanged.

The six PCM clause files provide exact clip boundaries, but not word boundaries. `restore_timing.py` estimates actual word starts with Faster-Whisper base.en on each clause and adds 100 ms before triggering cues. Those estimates are not sample-exact phoneme onsets and are not guaranteed never to precede a word; the original recording lacks trustworthy word-boundary events. No token-ratio timing is used. The vault is tied to the estimated “gold”, the vault ledger lines to “digital”, the globe to “currency”, and the statistic to “eighty-eight”. The original layout's digital treatment is the vault's ledger lines, not the separate digital ledger scene invented in later layouts.

A whole-frame motion diagnostic is reported but not enforced: forcing the prior frame-delta gate would require altering the historically restored animations, contrary to the strict restore request. The contact sheet samples 20%, 50% and 80% of each clause.

The narration is retained verbatim, including historically inaccurate claims: the 88% statistic concerns USD involvement in foreign-exchange transactions in 2022, not all global trade, and gold was not replaced by digital ledgers in 1971. The original source card correctly identifies foreign exchange.
