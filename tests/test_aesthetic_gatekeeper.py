import numpy as np
from aesthetic_gatekeeper import analyze_frame

def test_flat_frame_fails_density_and_range():
    result=analyze_frame(np.full((1080,1920,3),25,dtype=np.uint8))
    assert any('edge density' in s for s in result['failures'])
    assert any('edge coverage' in s for s in result['failures'])
    assert any('range' in s for s in result['failures'])

def test_distributed_detail_can_pass():
    import cv2
    frame=np.full((1080,1920,3),25,dtype=np.uint8)
    for y in range(10,1080,25): cv2.line(frame,(0,y),(1919,y),(95,95,95),2)
    for x in range(10,1920,25): cv2.line(frame,(x,0),(x,1079),(200,200,200),2)
    assert not analyze_frame(frame)['failures']

def test_grain_alone_does_not_count_as_detail():
    rng=np.random.default_rng(4)
    grain=np.clip(25+rng.normal(0,6.4,(1080,1920)),0,255).astype(np.uint8)
    frame=np.repeat(grain[:,:,None],3,axis=2)
    assert any('edge density' in error for error in analyze_frame(frame)['failures'])
