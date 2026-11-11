import re
import numpy as np
from forge_python.morph_audio import cap_long_pauses, compile_beats, prepare, SCRIPT, canonical
from forge_python.audio_mastering.pedalboard_master import warm_vocal,limit_foley

def test_ordinary_silences_and_quiet_consonants_are_untouched():
    sr=10000
    for pause in (70,150,280,500):
        # A quiet initial consonant comes immediately before the silent gap.
        v=np.r_[np.ones(1000)*.2,np.ones(30)*.008,np.zeros(pause*10),np.ones(1000)*.2].astype(np.float32)
        result,remap=cap_long_pauses(v,sr)
        np.testing.assert_array_equal(result,v)
        assert remap(.101)==.101

def test_only_long_interior_pause_is_capped():
    sr=10000;v=np.r_[np.ones(1000)*.2,np.zeros(8000),np.ones(1000)*.2].astype(np.float32)
    result,remap=cap_long_pauses(v,sr)
    assert abs(len(result)/sr-.48)<.002
    np.testing.assert_array_equal(result[:1000],v[:1000]);np.testing.assert_array_equal(result[-1000:],v[-1000:])
    assert abs(remap(.91)-.39)<.002

def test_natural_number_transcript_normalization():
    assert canonical('In 1971 and 2022, 88%')==canonical('in nineteen seventy one and twenty twenty two eighty eight percent')
    assert 32<=len(re.findall(r"[\w]+(?:-[\w]+)?",SCRIPT))<=38

def test_beat_groups_cover_every_word():
    words=[{'word':str(i),'word_id':i,'start_ms':i*300,'end_ms':i*300+200} for i in range(39)]
    beats=compile_beats(words,12)
    assert all(3<=len(b['words'])<=4 for b in beats)
    assert [i for b in beats for i in b['word_ids']]==list(range(39))

def test_processing_does_not_change_speech_length():
    voice=np.sin(np.arange(24000)*.1).astype(np.float32)*.1
    assert len(warm_vocal(voice,24000))==len(voice)
    fx=np.ones((24000,2),np.float32);quiet=limit_foley(fx,voice)
    assert np.sqrt(np.mean(quiet**2)) <= np.sqrt(np.mean(voice**2))*10**(-18/20)+1e-6

def test_offline_alignment_uses_audio_length_and_lead_in(tmp_path):
    import soundfile as sf
    path,words,beats,mode,_,frames=prepare(tmp_path,offline=True)
    audio,sr=sf.read(path);assert len(audio)==frames*sr//60
    assert mode=='offline-espeak' and words[0]['start_ms']>=150
    assert all(w['start_ms']<=w['end_ms'] for w in words)
    assert all(a['start']<b['start'] for a,b in zip(beats,beats[1:]))

def test_speed_a_silence_stripper_and_time_remap():
    from forge_python.morph_audio import strip_dead_air
    sr=10000
    voice=np.r_[np.full(1000,.2),np.zeros(1200),np.full(1000,.2)].astype(np.float32)
    trimmed,remap=strip_dead_air(voice,sr)
    assert abs(len(trimmed)/sr-.235)<.002
    assert abs(remap(.22)-.135)<.002
    np.testing.assert_array_equal(trimmed[:950],voice[:950])
    np.testing.assert_array_equal(trimmed[-950:],voice[-950:])

def test_speed_a_preserves_short_and_boundary_silence():
    from forge_python.morph_audio import strip_dead_air
    sr=10000
    voice=np.r_[np.zeros(1000),np.ones(500)*.1,np.zeros(600),np.ones(500)*.1,np.zeros(1000)].astype(np.float32)
    result,_=strip_dead_air(voice,sr)
    np.testing.assert_array_equal(result,voice)
