import numpy as np
import pyloudnorm as pyln
import pytest
from forge_python.post_fx.optical_lens import finish_frame
from forge_python.audio_mastering.pedalboard_master import duck_envelope, master
from forge_python.motion.physics import spring, drift

def test_optics_deterministic_and_bounded():
    frame = np.full((24, 32, 3), 220, dtype=np.uint8)
    a = finish_frame(frame, np.random.default_rng(4))
    b = finish_frame(frame, np.random.default_rng(4))
    assert np.array_equal(a, b) and a.dtype == np.uint8 and a.shape == frame.shape
    assert np.any(a != frame)
    with pytest.raises(ValueError): finish_frame(frame.astype(float))

def test_duck_and_master():
    sr = 8000
    voice = np.zeros((sr*3, 2), dtype=np.float32)
    voice[sr:2*sr] = 0.1
    gain = duck_envelope(voice, sr)
    assert gain[sr-1] == 1 and gain[2*sr-1] == pytest.approx(10**(-5.5/20), abs=.001)
    assert gain[-1] > gain[2*sr]
    music = np.sin(np.arange(sr*3)*2*np.pi*220/sr).astype(np.float32)*.03
    out = master(music, voice, sr)
    assert out.shape == (sr*3, 2)
    assert np.max(np.abs(out)) <= 0.892
    assert pyln.Meter(sr).integrated_loudness(out) == pytest.approx(-14, abs=.5)

def test_spring_and_drift():
    result = spring([0, .5, 1])
    assert result[0] == 0 and result[-1] == pytest.approx(1, abs=.01)
    assert drift(0) != drift(1)

def test_cinematic_bgr_adapter_and_tiny_frame():
    from forge_python.post_fx.optical_lens import process_frame_cinematic, _finish_with_seed
    frame = np.zeros((16, 20, 3), dtype=np.uint8)
    frame[:, :, 0] = 30
    frame[:, :, 2] = 220
    a = process_frame_cinematic(frame, 7)
    assert np.array_equal(a, process_frame_cinematic(frame, 7))
    assert not np.array_equal(a, process_frame_cinematic(frame, 8))
    assert np.array_equal(a, _finish_with_seed(frame[:, :, ::-1], 7)[:, :, ::-1])
    assert process_frame_cinematic(np.zeros((1, 1, 3), dtype=np.uint8), 0).shape == (1, 1, 3)
    with pytest.raises(ValueError): process_frame_cinematic(np.zeros((0, 1, 3), dtype=np.uint8), 0)

def test_vignette_darkens_edges_and_bloom_uses_luminance():
    from forge_python.post_fx.optical_lens import apply_bloom_vignette_and_grain
    frame = np.full((25, 25, 3), 0.5, dtype=np.float32)
    bloom = np.zeros_like(frame)
    graded = apply_bloom_vignette_and_grain(frame, bloom, 0)
    assert graded[0, 0, 0] < graded[12, 12, 0] - .1
    lit = apply_bloom_vignette_and_grain(frame, np.full_like(frame, 0.5), 0)
    assert lit[12, 12, 0] > graded[12, 12, 0]
