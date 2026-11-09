import math,re
from pathlib import Path
import pytest
from qa_inspector import compile_cues, audit

@pytest.fixture
def meta():
    values=[('In',0),('1971,',360),('States',2060),('ended',2480),('dollar',3260),('conversion',3820),('gold.',4760),('2022,',8640),('dollar',9980),('88',11580),('%',11960),('foreign',12780),('exchange',13080),('trades.',13340)]
    return {'frames':900,'words':[{'word':word,'word_id':i,'start_ms':ms} for i,(word,ms) in enumerate(values)]}

def test_all_frames_are_causal_and_exclusive(meta):
    cues,extra=audit(meta)
    for f in range(meta['frames']):
        active=[c for c in cues if c['first_frame']<=f<c['end_frame']]
        assert len(active)<=1
        if active:assert f*1000/60>=active[0]['trigger_ms']+40
    assert extra['percent']*1000/60>=12000
    assert extra['trades']*1000/60>=13380

def test_missing_spoken_trigger_fails_instead_of_guessing(meta):
    meta['words']=[w for w in meta['words'] if w['word']!='conversion']
    with pytest.raises(ValueError,match='conversion'):compile_cues(meta['words'],900)

def test_audit_reports_missing_edge_boundary_and_absent_words(meta,capsys):
    audit(meta);out=capsys.readouterr().out
    assert 'Edge WordBoundary events were not saved' in out
    assert 'rewrote: NOT SPOKEN' in out and 'digital: NOT SPOKEN' in out

def test_no_small_font_css_and_audit_guard_present():
    css=Path('web/semantic/style.css').read_text();sizes=re.findall(r'font-size:\s*(\d+)px',css)
    assert sizes and all(int(n)>=48 for n in sizes)
    app=Path('web/semantic/app.jsx').read_text()
    assert 'window.auditFrame(frame)' in app and "el.dataset.cue" in app
    assert 'data-audit-text' in app and 'data-focal-object' in app
