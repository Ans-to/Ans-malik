# Cosmic shader trailer renderer

A 15-second four-act trailer with continuous Numba-compiled procedural fields: a six-octave gradient-fBm/Voronoi magma surface and expanding plasma, a turbulent black-hole disk and double image, a domain-warped colored nebula, and a tracked title with mask-based shadow rays and light wrap. The former polygon shards, point-particle ring and repeated arches have been removed from the render path.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python ceo_render_app.py --topic 'Invisible Storm' --showcase --offline --resolution 1920x1080 --output renders/final_video.mp4
python qa_video.py renders/final_video.mp4 --sheet renders/qa_contact_sheet.png --resolution 1920x1080
python impact_gatekeeper.py renders/final_video.mp4
python -m pytest -q && npm test
```

**Implementation limits:** The default CPU shader runs at the requested output resolution, including native 1920×1080; this is computationally expensive. Tests may request a smaller internal resolution. The magma surface uses a displaced SDF ray march and short sampled smoke approximation. The black-hole image combines a simple inverse-square numerical deflection with artistically projected disk arcs; it is **not** a Schwarzschild geodesic raytracer or an astrophysically validated image. Its blackbody colors use Planck spectral samples, not a calibrated color-science pipeline. The nebula uses domain-warped fractal-style layers and short density integration; it is not a Mandelbox distance estimator or a physically accurate thin-film/subsurface simulation. Title shadow rays and light wrap are screen-space approximations. None of these approximations guarantee the requested cinematic reference quality.

Actions uses Edge TTS Christopher Neural at +12% and Faster-Whisper, failing instead of silently falling back. Local `--offline` uses eSpeak and its estimated word events. Audio combines synthesized brass, risers and metallic transients. Every frame passes through shockwave/trauma and optical finishing. GitHub Actions fits oversized MP4s under a 95 MiB safety limit before audiovisual QA and commits outputs to the session branch; this re-encoding can reduce quality. QA checks per-act CIELAB chroma variance as well as motion and video/audio streams, but cannot prove artistic quality or the absence of every unwanted object.
