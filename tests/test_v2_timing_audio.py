import numpy as np
from forge_python.render.documentary_timeline import make_v2_timeline, anchor_events
from forge_python.audio_mastering.trailer_sfx import trailer_sfx

def words():
    tokens=['In','1971','Nixon','closed','the','gold','window','digital','ledgers','debt','towers','four','hubs','dollars','were','in','eighty-eight','percent','of','FX','trades']
    return [{'word':w,'start_ms':i*500+50,'end_ms':i*500+400} for i,w in enumerate(tokens)]

def test_v2_anchor_labels_are_spoken_and_transitions_follow_word_ends():
    shots,transitions,anchors=make_v2_timeline(words())
    assert [a['text'] for a in anchors]==['1971','CLOSED','GOLD WINDOW','DIGITAL LEDGERS','DEBT TOWERS','FOUR HUBS','88%']
    assert len(shots)==8 and len(transitions)==7 and shots[-1]['end_frame']==720
    ends={round(w['end_ms']*60/1000) for w in words()}
    assert all(t['frame'] in ends for t in transitions)
    assert all(t['duration_frames'] in (4,5) for t in transitions)

def test_sfx_stereo_onsets_match_every_word_and_cut():
    shots,transitions,anchors=make_v2_timeline(words());sr=24000
    audio,events=trailer_sfx(12,sr,transitions,anchors)
    assert audio.shape==(sr*12,2) and len(events)==14 and np.isfinite(audio).all()
    assert {(e['kind'],e['frame']) for e in events}==({('anchor_click',a['start_frame']) for a in anchors}|{('transition_thud',t['frame']) for t in transitions})
    assert all(np.max(abs(audio[round(e['frame']*sr/60):round(e['frame']*sr/60)+20]))>.04 for e in events)

def test_template_has_only_one_visible_text_anchor():
    from pathlib import Path
    html=Path('web/documentary/index.html').read_text()
    js=Path('web/documentary/documentary.js').read_text()
    assert html.count('id="anchor"')==1
    assert all(x not in html for x in ('class="kicker"','class="detail"','class="smallprint"'))
    assert 'fillText(' not in js and 'numL.visible=false;numR.visible=false' in js and 'eight.visible=false' in js
