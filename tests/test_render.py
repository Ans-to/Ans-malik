import numpy as np
import pytest
from scipy.signal import resample_poly
import ceo_render_app
from qa_video import qa

def test_render_encodes_only_finished_frames(tmp_path, monkeypatch):
    async def offline(*args): raise OSError('offline test')
    monkeypatch.setattr(ceo_render_app, 'synthesize', offline)
    original = ceo_render_app.finish_frame
    calls = []
    def finish(frame, rng):
        calls.append(1)
        return original(frame, rng)
    monkeypatch.setattr(ceo_render_app, 'finish_frame', finish)
    video=tmp_path/'test.mp4'; sheet=tmp_path/'sheet.png'
    ceo_render_app.render('Why Your AI Gives You Wrong Answers', 1, (160, 90), video)
    assert len(calls)==60 and video.stat().st_size>0
    qa(video, sheet, (160,90))
    assert sheet.stat().st_size>0
    from aesthetic_gatekeeper import gatekeep
    with pytest.raises(ValueError,match="below 1920x1080"):
        gatekeep(video)

def test_audio_peak_estimate():
    from forge_python.audio_mastering.pedalboard_master import master
    sr=24000; t=np.arange(2*sr)/sr
    result=master(.3*np.sin(t*2100).astype(np.float32), .1*np.sin(t*90).astype(np.float32),sr)
    assert np.max(np.abs(result)) <= .892
    assert np.max(np.abs(resample_poly(result,4,1,axis=0))) <= .892

def test_lookahead_oversampled_peak_for_transient():
    from forge_python.audio_mastering.pedalboard_master import constrain_oversampled_peak
    x=np.zeros((24000,2),np.float32); x[12000:12004,:]=[[-2,2],[2,-2],[-2,2],[2,-2]]
    y=constrain_oversampled_peak(x,24000)
    assert np.max(np.abs(resample_poly(y,4,1,axis=0))) <= 10**(-1/20)

def test_pdf_words_match_speech_and_perspective():
    from forge_python.render.document import ClassifiedDocument
    from forge_python.render.voice import OfflineVoice
    audio, words=OfflineVoice().speak('A fluent answer is not proof.')
    assert len(audio)>1000 and len(words)==6
    for index, word in enumerate(words): word['word_id']=index
    doc=ClassifiedDocument(words)
    assert doc.pdf.startswith(b'%PDF') and len(doc.boxes)==len(words)
    assert doc.frame(320,180,.5,words).shape == (180,320,3)
    assert all(w['start_ms'] < w['end_ms'] for w in words)

def test_online_voice_failure_uses_speech_and_timed_words(tmp_path, monkeypatch):
    import sys, types
    class FakeWhisper:
        def __init__(self,*args,**kwargs): pass
    monkeypatch.setitem(sys.modules, 'faster_whisper', types.SimpleNamespace(WhisperModel=FakeWhisper))
    async def unreachable(*args): raise OSError('offline')
    monkeypatch.setattr(ceo_render_app, 'synthesize', unreachable)
    script=ceo_render_app.script_for('Why Your AI Gives You Wrong Answers')
    path, speech, sr, modes, words=ceo_render_app.prepare_audio(script, 10, tmp_path, 'tiny')
    assert path.exists() and np.max(np.abs(speech)) > .01
    assert modes == ['offline-espeak']*5
    assert {item['act'] for item in words} == set(range(5))
    assert [item['word_id'] for item in words] == list(range(len(words)))
    assert all(item['start_ms'] < item['end_ms'] <= 10000 for item in words)
