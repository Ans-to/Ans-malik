# Environment audit — measured, not assumed

Sandbox: 2 vCPU, 3 GB RAM, no GPU, no OpenGL/EGL device.
Egress allowlist: github.com, codeload.github.com, api.github.com,
registry.npmjs.org, pypi.org, files.pythonhosted.org.

| Spec requirement | Tool | Status | Evidence |
|---|---|---|---|
| Blender 4.x (`bpy`) | bpy 4.2.0 wheel | AVAILABLE but impractical | 519 MB wheel downloads; Cycles on 2 CPU cores: 4K/512spp is ~10 min/frame → 3600 frames = days |
| Poly Haven HDRIs (Part E) | polyhaven.com / api.polyhaven.com | BLOCKED | curl → 000 (no route). Cannot download CC0 HDRIs. |
| OpenCLIP aesthetic gate (Part F) | weights on huggingface.co | BLOCKED | huggingface.co, cdn-lfs.huggingface.co → 000. Package installs, weights do not. |
| AnimateDiff / SVD (Part G) | weights on HF | BLOCKED | same as above; also needs GPU |
| Reference clips (Part D.1) | mixkit.co, pexels.com, coverr.co | BLOCKED | not on allowlist |
| Coqui TTS | weights via github releases + torch | UNTESTED / likely too heavy | torch ≈ 900 MB + espeak; 3 GB RAM |

## Consequence

Parts E, F, G and D.1 cannot be executed as written in this sandbox. They are
NOT silently skipped: each has a documented substitute in
`logs/SUBSTITUTION_LEDGER.md`, and the substitute is reported at every gate
with its real numbers. The user can run the literal parts on a GPU machine;
the pipeline emits the exact commands.
