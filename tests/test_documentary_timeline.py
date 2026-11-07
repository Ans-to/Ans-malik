import numpy as np
import pytest
from forge_python.render.documentary_timeline import make_timeline, speed_ramp, physical_transition

def test_timeline_has_eleven_ramped_shots_and_physical_transitions():
    shots,transitions=make_timeline(15,[{'word':'gold','start_ms':4100}])
    assert len(shots)==11 and len(transitions)==10
    assert all(72<=s['end_frame']-s['start_frame']<=96 for s in shots)
    assert {t['kind'] for t in transitions}=={'pillar','portal','whip'}
    assert any(t['frame']==246 for t in transitions)
    # The nine-frame arrivals and exits are much faster than the mid-shot glide.
    assert speed_ramp(.15,1.4)-speed_ramp(0,1.4)>4*(speed_ramp(.75,1.4)-speed_ramp(.6,1.4))
    assert speed_ramp(1.4,1.4)-speed_ramp(1.25,1.4)>4*(speed_ramp(.75,1.4)-speed_ramp(.6,1.4))

def test_spatial_transitions_preserve_both_endpoints():
    a=np.full((90,160,3),30,np.uint8);b=np.full_like(a,200)
    for mode in ('pillar','portal','whip'):
        assert np.array_equal(physical_transition(a,b,0,mode),a)
        assert np.array_equal(physical_transition(a,b,1,mode),b)
        mid=physical_transition(a,b,.5,mode)
        assert mid.min()<50 and mid.max()>180

def test_timeline_fails_when_beat_constraints_impossible():
    with pytest.raises(ValueError):make_timeline(5)
