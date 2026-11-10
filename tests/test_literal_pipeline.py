import json
import numpy as np
import pytest
import soundfile as sf
from storyboard_compiler import load_plan,validate_plan
from literal_audio import compile_timeline

@pytest.mark.parametrize('topic',['Why the US Dollar is the King of Global Finance','Why Your AI Gives You Wrong Answers'])
def test_topic_examples_grow_with_duration(topic):
    assert len(load_plan(topic,15)['beats'])==5
    assert len(load_plan(topic,30)['beats'])==10
    assert len(load_plan(topic,60)['beats'])==20

def test_unknown_topic_is_not_silently_misrepresented(tmp_path):
    with pytest.raises(ValueError,match='--storyboard'):load_plan('Coral reefs',15)
    p=tmp_path/'custom.json';p.write_text(json.dumps({'beats':[{'spoken_text':'A document links a dollar.','trigger_word':'links','visual_actors':['document','dollar'],'action':'connect','mood':'archival'}]}))
    assert load_plan('Coral reefs',50,p)['topic']=='Coral reefs'

def test_rejects_unknown_actor_and_missing_trigger():
    beat={'spoken_text':'The moon glows.','trigger_word':'glows','visual_actors':['moon','globe'],'action':'flow','mood':'digital'}
    with pytest.raises(ValueError,match='unsupported'):validate_plan({'beats':[beat]})
    beat['visual_actors']=['gold','dollar'];beat['trigger_word']='breaks'
    with pytest.raises(ValueError,match='actual spoken word'):validate_plan({'beats':[beat]})

def test_sample_boundaries_and_trigger_from_edge_event(tmp_path):
    plan=load_plan('Why Your AI Gives You Wrong Answers',6);paths=[];events=[];sr=48000
    for i,b in enumerate(plan['beats']):
        p=tmp_path/f'{i}.wav';sf.write(p,np.ones(11017+i,dtype=np.float32)*.2,sr);paths.append(p)
        events.append([{'type':'WordBoundary','text':b['trigger_word'],'offset':1_000_000,'duration':100000}])
    plan['requested_duration']=.1
    speech,t=compile_timeline(plan,paths,events)
    assert len(t['beats'])==2 and len(speech)==t['total_samples']
    for b in t['beats']:
        assert b['trigger_sample']-b['start_sample']==4800
        assert b['trigger_frame']/60>=b['trigger_sample']/sr
    assert t['beats'][1]['start_sample']-t['beats'][0]['end_sample']==8640
    with pytest.raises(ValueError,match='WordBoundary'):compile_timeline(plan,paths,[[],events[1]])


def test_duration_padding_does_not_modify_speech(tmp_path):
    plan=load_plan('Why Your AI Gives You Wrong Answers',6);paths=[];events=[]
    for i,b in enumerate(plan['beats']):
        p=tmp_path/f'{i}.wav';sf.write(p,np.ones(4800,dtype=np.float32)*.2,48000);paths.append(p)
        events.append([{'type':'WordBoundary','text':b['trigger_word'],'offset':100000,'duration':100000}])
    speech,t=compile_timeline(plan,paths,events)
    assert len(speech)==6*48000 and t['frames']==360
    assert all(b['end_sample']-b['start_sample']==4800 for b in t['beats'])
