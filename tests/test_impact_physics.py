import numpy as np
from forge_python.render.impact_physics import ImpactPhysicsEngine,impact_music,beat_times

def test_beat_and_keyword_impacts_modify_frame_and_decay():
    engine=ImpactPhysicsEngine(160,90,15,[{'word':'verify','start_ms':9000}])
    assert engine.beats[:6]==[0.,1.2,3.8,5.2,7.6,11.4]
    assert 12.4 in beat_times(15)
    rng=np.random.default_rng(2); frame=rng.integers(0,255,(90,160,3),dtype=np.uint8)
    assert not np.array_equal(frame,engine.transform(frame,1.22))
    assert np.array_equal(frame,engine.transform(frame,2.5))

def test_score_includes_low_frequency_impact_transients():
    sr=8000;music=impact_music(3,sr)
    assert music.shape==(3*sr,) and np.isfinite(music).all()
    assert np.sqrt(np.mean(music[:sr//5]**2))>np.sqrt(np.mean(music[sr:sr+sr//5]**2))
