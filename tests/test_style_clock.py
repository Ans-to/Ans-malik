import json
from pathlib import Path
import pytest
from style_clock import compile_visual_marks,remap

def sample():
    words=[('States',2060),('gold.',4760),('2022,',8640),('dollar',3260),('dollar',9980),('88',11580),('foreign',12780),('exchange',13080),('trades.',13340)]
    return {'duration':15.,'words':[{'word':w,'start_ms':t} for w,t in words]}

def test_remap_anchors_and_continuity():
    marks=compile_visual_marks(sample())
    for m in marks:assert remap(m['real'],marks)==m['virtual']
    for a,b in zip(marks,marks[1:]):
        midpoint=(a['real']+b['real'])/2
        assert remap(midpoint,marks)==pytest.approx((a['virtual']+b['virtual'])/2)
    assert marks[2]['name']=='gold' and marks[2]['real']==4.76
    assert marks[3]['name']=='2022' and marks[5]['name']=='88'

def test_missing_keyword_is_not_invented():
    data=sample();data['words']=[w for w in data['words'] if w['word']!='88']
    with pytest.raises(ValueError,match='88'):compile_visual_marks(data)

def test_no_tiny_corner_status_text():
    app=Path('web/morph/app.jsx').read_text()
    assert 'className="header"' not in app and 'className="foot"' not in app
    assert 'warpTime' in app
