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

def test_compositor_rejects_empty_layer():
    import pytest
    from forge_python.render.compositor import SevenLayerCompositor
    from forge_python.render.document import ClassifiedDocument
    words=[{'word':'Example','word_id':0,'act':1,'start_ms':0,'end_ms':500}]
    doc=ClassifiedDocument(words)
    compositor=SevenLayerCompositor(160,90,'Example',words,doc,None,finisher=lambda image,rng:image)
    compositor._dust=lambda t: compositor.blank()
    with pytest.raises(ValueError,match='Layer 6'):
        compositor.compose(0,0,.2,0,5)


def test_grain_alone_does_not_count_as_detail():
    rng=np.random.default_rng(4)
    grain=np.clip(25+rng.normal(0,6.4,(1080,1920)),0,255).astype(np.uint8)
    frame=np.repeat(grain[:,:,None],3,axis=2)
    assert any('edge density' in error for error in analyze_frame(frame)['failures'])

def test_chart_projection_and_damped_title_motion():
    from forge_python.render.compositor import chart_points
    from forge_python.motion.physics import spring
    result=chart_points(np.array([0.,1.]), np.array([0.,1.]),10.,90.,100.,80.)
    assert np.allclose(result,[[10,90],[110,10]])
    values=spring(np.array([0.,.25,1.]))
    assert values[0] == 0 and values[1] > 0 and abs(values[2]-1) < .02
