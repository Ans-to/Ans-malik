# Invisible Storm trailer renderer

A four-act procedural 3D trailer: a molten obsidian monolith bursts into 320 individually tumbling polyhedra; 150,000 particles move in an analytically divergence-free curl field and collapse/detonate; a Numba SDF raymarcher flies through a vaulted liquid-metal cathedral; a singularity and extruded metallic title conclude the film. There are no diagnostic interfaces or charts in the rendering path.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && npm ci
python ceo_render_app.py --topic 'Invisible Storm' --showcase --offline --resolution 1920x1080 --output renders/final_video.mp4
python qa_video.py renders/final_video.mp4 --sheet renders/qa_contact_sheet.png --resolution 1920x1080
python impact_gatekeeper.py renders/final_video.mp4
python -m pytest -q && npm test
```

Actions uses Edge TTS Christopher Neural at +12% and Faster-Whisper, failing instead of silently falling back. Local offline mode uses eSpeak at a faster trailer pace and its own estimated word events. Audio combines synthesized overdriven brass, risers and metallic transients with processed music, voice and room tone. Each frame passes through bloom, horizontal highlight streaks, vignette, chromatic aberration and grain. OpenCV handles timed shockwave, lensing and camera trauma. The final -14 LUFS target and reconstructed peak checks are not broadcast-certified.

The Three.js shards use deterministic ballistic trajectories and angular velocity, not a collision-solving rigid-body engine. The curl field is analytic rather than simplex noise; particles use procedural trajectories with curl displacement, rather than a Navier-Stokes solver. The CPU SDF raymarcher renders at up to 480 pixels wide then upscales, with finite-difference normals, approximate ambient occlusion, highlights and fog; it is not path-traced and has no physically accurate reflections. Point glow approximates bokeh. Volumetric shafts are approximated by blooms, not volumetric path tracing. These limits matter when comparing with cinematic reference footage.

GitHub Actions renders the showcase on relevant pushes, validates video and audio, uploads artifacts, and commits the MP4 and contact sheet to the session branch. It requires available neural services and GitHub write permissions. Before QA, the workflow re-encodes oversized MP4s at progressively higher CRF until they fit under a 95 MiB safety limit; if none fits it fails without truncating the video. This can reduce image quality. Larger files require Git LFS or external storage. The contact sheet and automated motion checks do not prove a subjective quality benchmark or absence of every unwanted visual element.
