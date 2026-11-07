import numpy as np
import pytest
from scipy.signal import resample_poly
import ceo_render_app
from qa_video import qa

def test_render_encodes_only_finished_frames(tmp_path, monkeypatch):
    # Bypass audio preparation only in this encoding smoke test; separate tests
    # exercise the real minimum scene length and speech preservation.
    def short_audio(script,duration,tmp,whisper_model,require_online,offline):
        import soundfile as sf
        sr=24000; speech=np.zeros(sr,dtype=np.float32); path=tmp/'master.wav'
        sf.write(path,np.zeros((sr,2),dtype=np.float32),sr)
        words=[{'word_id':0,'word':'Example','act':1,'start_ms':250,'end_ms':350}]
        return path,speech,sr,['test']*5,words,1.0
    monkeypatch.setattr(ceo_render_app, 'prepare_audio', short_audio)
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
    path, speech, sr, modes, words,duration=ceo_render_app.prepare_audio(script, 10, tmp_path, 'tiny')
    assert path.exists() and np.max(np.abs(speech)) > .01
    assert modes == ['offline-espeak']
    assert {item['act'] for item in words} == {0}
    assert [item['word_id'] for item in words] == list(range(len(words)))
    assert duration >= 10
    assert all(item['start_ms'] < item['end_ms'] <= duration*1000 for item in words)
    assert all(int(item['start_ms']/1000/duration) == item['act'] for item in words)


def test_pacing_extends_to_fit_unmodified_speech(tmp_path, monkeypatch):
    class FakeVoice:
        def speak(self, text, sr):
            # Ten-second, identifiable signal; verify it is not resampled.
            voice=np.arange(sr*10,dtype=np.float32)/(sr*10)
            return voice,[{'word':text,'start_ms':100,'end_ms':9900}]
    monkeypatch.setattr(ceo_render_app, 'OfflineVoice', FakeVoice)
    script=['word']*5
    path,speech,sr,modes,words,duration=ceo_render_app.prepare_audio(script, 5, tmp_path, offline=True)
    assert duration >= 53 and len(speech) == round(duration*sr)
    assert len(words)==5 and all(w['end_ms']-w['start_ms']==9800 for w in words)
    for act in range(5):
        start=round(words[act]['start_ms']/1000*sr)-round(.1*sr)
        np.testing.assert_array_equal(speech[start:start+sr*10], np.arange(sr*10,dtype=np.float32)/(sr*10))

def test_required_online_failure_is_not_silently_downgraded(tmp_path, monkeypatch):
    async def unreachable(*args): raise OSError('no network')
    monkeypatch.setattr(ceo_render_app, 'synthesize', unreachable)
    with pytest.raises(RuntimeError, match='Online voice/alignment failed'):
        ceo_render_app.prepare_audio(['a']*5,30,tmp_path,require_online=True)

def test_neural_voice_configuration(monkeypatch,tmp_path):
    import asyncio, sys, types
    calls=[]
    class Communicate:
        def __init__(self, text, voice, **kw): calls.append((text,voice,kw))
        async def save(self, path, metadata): pass
    monkeypatch.setitem(sys.modules,'edge_tts',types.SimpleNamespace(Communicate=Communicate))
    asyncio.run(ceo_render_app.synthesize(['A test'],tmp_path/'a.mp3'))
    assert calls == [('A test','en-US-ChristopherNeural',{'rate':'+12%','pitch':'-2Hz','boundary':'WordBoundary'})]

def test_online_voice_and_whisper_are_automatic(tmp_path, monkeypatch):
    import sys, types, soundfile as sf
    calls=[]
    async def online(script, target): target.write_bytes(b'fake audio')
    def decode(command, check):
        sf.write(command[-1], np.ones(24000,dtype=np.float32)*.04, 24000)
    class FakeWhisper:
        def __init__(self, name, **kwargs): calls.append(('model',name,kwargs))
        def transcribe(self, path, word_timestamps):
            calls.append(('transcribe',word_timestamps))
            word=types.SimpleNamespace(word='hello',start=0.1,end=0.8)
            return [types.SimpleNamespace(words=[word])], None
    monkeypatch.setattr(ceo_render_app, 'synthesize', online)
    monkeypatch.setattr(ceo_render_app.subprocess, 'run', decode)
    monkeypatch.setitem(sys.modules,'faster_whisper',types.SimpleNamespace(WhisperModel=FakeWhisper))
    path,speech,sr,modes,words,duration=ceo_render_app.prepare_audio(['hello']*5,5,tmp_path)
    assert modes==['edge-tts+faster-whisper']*5
    assert calls[0][0:2]==('model','base.en') and len(calls)==6
    assert all(call==('transcribe',True) for call in calls[1:])
    assert duration>=30 and len(words)==5
    assert all(w['end_ms']-w['start_ms']==700 for w in words)

def test_whisper_mismatch_uses_edge_word_boundaries(tmp_path, monkeypatch):
    import json, sys, types, soundfile as sf
    async def online(script,target):
        target.write_bytes(b'fake')
        target.with_name(target.name+'.jsonl').write_text(json.dumps({'type':'WordBoundary','text':'hello','offset':1000000,'duration':7000000})+'\n')
    def decode(command,check): sf.write(command[-1],np.ones(24000,dtype=np.float32)*.04,24000)
    class FakeWhisper:
        def __init__(self,*args,**kwargs): pass
        def transcribe(self,*args,**kwargs):
            word=types.SimpleNamespace(word='wrong',start=.1,end=.8)
            return [types.SimpleNamespace(words=[word])],None
    monkeypatch.setattr(ceo_render_app,'synthesize',online)
    monkeypatch.setattr(ceo_render_app.subprocess,'run',decode)
    monkeypatch.setitem(sys.modules,'faster_whisper',types.SimpleNamespace(WhisperModel=FakeWhisper))
    _,_,_,modes,words,_=ceo_render_app.prepare_audio(['hello']*5,30,tmp_path,require_online=True)
    assert modes==['edge-tts-boundaries+faster-whisper']*5
    assert all(item['word']=='hello' and item['end_ms']-item['start_ms']==700 for item in words)

def test_showcase_refuses_to_speed_or_truncate_overlong_voice(tmp_path,monkeypatch):
    def too_long(script,duration,tmp,whisper_model,require_online,offline):
        return tmp/'unused.wav',np.zeros(1,dtype=np.float32),24000,['test'],[],15.5
    monkeypatch.setattr(ceo_render_app,'prepare_audio',too_long)
    with pytest.raises(ValueError,match='shorten the script'):
        ceo_render_app.render('test',15,(160,90),tmp_path/'test.mp4',showcase=True)
