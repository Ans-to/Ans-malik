import numpy as np
from forge_python.morph_audio import strip_dead_air, compile_beats, prepare

def test_strip_dead_air_compresses_gaps_without_moving_voice():
    sr=10000;v=np.r_[np.ones(1000)*.2,np.zeros(5000),np.ones(1000)*.2].astype(np.float32)
    result, remap=strip_dead_air(v,sr)
    assert 0.22 < len(result)/sr < 0.26
    assert abs(remap(.61)-.145)<.03
    assert np.max(np.abs(np.diff(result)))<=np.max(np.abs(np.diff(v)))

def test_short_silence_is_preserved():
    sr=10000;v=np.r_[np.ones(1000)*.2,np.zeros(500),np.ones(1000)*.2].astype(np.float32)
    result,_=strip_dead_air(v,sr);assert len(result)==len(v)

def test_beat_groups_cover_every_word():
    words=[{'word':str(i),'word_id':i,'start_ms':i*300,'end_ms':i*300+200} for i in range(39)]
    beats=compile_beats(words,12)
    assert len(beats)==10 and all(3<=len(b['words'])<=4 for b in beats)
    assert [i for b in beats for i in b['word_ids']]==list(range(39))

def test_offline_alignment_is_monotonic_and_morphs(tmp_path):
    _,words,beats,mode,_,frames=prepare(tmp_path,offline=True)
    assert mode=='offline-espeak' and frames>0
    assert all(w['start_ms']<=w['end_ms'] for w in words)
    assert all(a['start']<b['start'] for a,b in zip(beats,beats[1:]))
