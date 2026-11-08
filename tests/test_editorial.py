from pathlib import Path
import pytest
from forge_python.editorial_audio import prepare_narration,create_document

def test_narration_word_alignment_and_scene_timing(tmp_path):
    voice,sr,words,mode,text=prepare_narration('Why AI gives wrong answers',15,tmp_path,offline=True)
    assert len(voice)==15*sr
    assert len(words)>12 and all(w['start_ms']<w['end_ms'] for w in words)
    assert any(3000<=w['start_ms']<6000 and 'predict' in w['word'] for w in words)
    assert any(12000<=w['start_ms']<15000 for w in words)
    assert mode=='offline-espeak'

def test_topic_limit_is_explicit(tmp_path):
    with pytest.raises(ValueError,match='AI explainer only'):
        prepare_narration('The dollar',15,tmp_path,offline=True)

def test_document_texture(tmp_path):
    png=tmp_path/'document.png';pdf,box=create_document('AI',png)
    assert png.exists() and pdf.exists() and 0<box['y']<980

def test_chromium_controls_frame_timing():
    app=Path('web/editorial/app.jsx').read_text()
    assert 'globalTimeline.seek(frame/60' in app and 'useCurrentFrame' in app
    assert 'animateMotion' not in app
