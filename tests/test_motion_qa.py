import pytest
from scripts.motion_qa import evaluate_deltas

def test_static_and_repeated_frames_fail():
    with pytest.raises(AssertionError): evaluate_deltas([0]*200)
    with pytest.raises(AssertionError): evaluate_deltas([1]*100+[0]+[1]*100)
    with pytest.raises(AssertionError): evaluate_deltas([1]*99+[0,0]+[1]*100)

def test_98_percent_threshold_is_strict():
    assert evaluate_deltas([1]*98+[.3]*2)['fraction_above_065']==.98
    with pytest.raises(AssertionError): evaluate_deltas([1]*97+[.3]*3)

def test_empty_and_short_videos_rejected():
    with pytest.raises(AssertionError): evaluate_deltas([])

def test_inspection_measures_actual_rgb_deltas(monkeypatch):
    import numpy as np
    import scripts.motion_qa as motion
    frames=[np.full((2,3,3),i,dtype=np.uint8) for i in range(10)]
    monkeypatch.setattr(motion,'video_frames',lambda path:iter(frames))
    stats,images=motion.inspect('ignored',10,{0,9},(3,2))
    assert stats['pairs']==9 and stats['minimum_delta']==1
    assert images[0][0,0,0]==0 and images[9][0,0,0]==9
    frames[5]=frames[4].copy();frames[6]=frames[4].copy()
    with pytest.raises(AssertionError): motion.inspect('ignored',10,set(),(3,2))
