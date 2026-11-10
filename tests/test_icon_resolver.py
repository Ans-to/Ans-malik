from icon_resolver import libraries,resolve,icon_body,topic_actors
from storyboard_compiler import load_plan

def test_icon_library_and_mapping():
    d=libraries();names=sum(len(p['icons'])+len(p.get('aliases',{})) for p in d.values());assert names>10000
    assert resolve('microchips')['id']=='iconify:lucide:microchip'
    assert '<' in icon_body(resolve('sand')['id'])['body']
    r=topic_actors('How Microchips Are Built From Sand');assert all(x['match']!='unresolved' for x in r)

def test_unknown_topic_compiles_but_flags_review():
    x=load_plan('How Microchips Are Built From Sand',60)
    assert len(x['beats'])==20 and x['semantic_review_required']
    assert all(len(b['visual_actors'])==2 for b in x['beats'])

def test_ten_rigs_are_valid_and_ring_requires_explicit_value():
    import pytest
    from storyboard_compiler import RIGS,validate_plan
    assert len(RIGS)==10
    base={'spoken_text':'The object changes.','trigger_word':'changes','visual_actors':['gold','dollar'],'action':'compare','mood':'digital'}
    for rig in RIGS:
        beat={**base,'rig':rig}
        if rig=='dominance-ring':
            with pytest.raises(ValueError):validate_plan({'beats':[beat]})
            beat['value']=88
        assert validate_plan({'beats':[beat]})
