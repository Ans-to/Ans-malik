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

def test_cosmic_shader_samples_acts_and_is_deterministic():
    from forge_python.render.cosmic_shader import render_shader
    frames=[render_shader(96,54,t) for t in (.9,4.7,9.,13.)]
    assert all(a.shape==(54,96,3) and a.dtype==np.uint8 for a in frames)
    assert np.array_equal(frames[0],render_shader(96,54,.9))
    assert all(np.std(a)>2 for a in frames)

def test_title_mask_is_spaced_and_has_shadow_compositor():
    from forge_python.render.cosmic_shader import CosmicRenderer
    renderer=CosmicRenderer(320,180,160)
    assert renderer.mask.max()>.7 and np.sum(renderer.mask)>10
    assert not np.array_equal(renderer.frame(12),renderer.frame(13))

def test_chroma_variance_rejects_grey_images():
    from impact_gatekeeper import chroma_variance
    gray=np.tile(np.arange(128,dtype=np.uint8),(64,1)); gray=np.repeat(gray[:,:,None],3,axis=2)
    assert chroma_variance(gray)==0
    color=gray.copy();color[:,:64,2]=200;color[:,64:,0]=200
    assert chroma_variance(color)>4
