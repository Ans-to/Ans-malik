import json,subprocess
from pathlib import Path
from art_render import audio_hash
from forge_python.ffmpeg import get_ffmpeg_exe

def test_audio_hash_survives_copy_remux(tmp_path):
    ff=get_ffmpeg_exe();source=tmp_path/'source.mp4';audio=tmp_path/'locked.m4a';output=tmp_path/'out.mp4'
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','color=black:s=64x64:r=60:d=1','-f','lavfi','-i','sine=frequency=440:sample_rate=24000:duration=1','-c:v','libx264','-c:a','aac',str(source)],check=True)
    subprocess.run([ff,'-v','error','-y','-i',str(source),'-map','0:a:0','-c:a','copy',str(audio)],check=True)
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','color=black:s=64x64:r=60:d=1','-i',str(audio),'-c:v','libx264','-c:a','copy',str(output)],check=True)
    assert audio_hash(source)==audio_hash(audio)==audio_hash(output)

def test_renderer_reuses_prior_audio_and_word_timings():
    code=Path('art_render.py').read_text();workflow=Path('.github/workflows/render_video.yml').read_text()
    assert "'-c:a','copy'" in code and 'locked_audio_sha256' in code
    assert "data={**meta" in code and 'morph_render.py --require-online' in workflow
    assert 'strip_dead_air' not in code

def test_art_has_metaphors_and_no_global_trade_misstatement():
    code=Path('web/morph/app.jsx').read_text()
    for token in ['archival-left','vault-wheel','paper-loupe','ledger-loupe','sealpath','ring-marker','NodeGrid']:
        assert token in code
    assert 'OF FOREIGN-EXCHANGE TRADES' in code
