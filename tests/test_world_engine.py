import cv2
import numpy as np
import pytest
from forge_python.render.world_engine import WorldEngine, velocity_blur
from forge_python.render.document import ClassifiedDocument
from aesthetic_gatekeeper import motion_pair

def world():
    words=[{'word':'evidence','word_id':0,'act':0,'start_ms':0,'end_ms':500}]
    return WorldEngine(640,360,15,'Why AI can be wrong',ClassifiedDocument(words),words)

def test_camera_and_velocity_are_continuous_and_six_dimensional():
    engine=world()
    for time in np.linspace(.1,14.9,20):
        before, bv=engine.camera(time-1e-5); after, av=engine.camera(time+1e-5)
        assert before.shape==(6,) and bv.shape==(6,)
        assert np.linalg.norm(after-before)<.1
        assert np.linalg.norm(av-bv)<.1
    assert engine.camera(14)[0][0] > engine.camera(1)[0][0]+3000

def test_perspective_depth_has_different_motion():
    engine=world(); a=np.array([[0,0,0],[0,0,500]])
    x0=engine.project(a,0.5)[:,0];x1=engine.project(a,0.6)[:,0]
    assert abs((x1-x0)[0]-(x1-x0)[1]) > .01

def test_blur_changes_fast_frame_but_not_flat():
    x=np.zeros((48,64,3),np.uint8);x[:,32:,:]=180
    blurred=velocity_blur(x,12.,0.,0.)
    assert np.any(blurred!=x)
    flat=np.full((20,20,3),75,np.uint8)
    assert np.array_equal(velocity_blur(flat,4.,2.,.01),flat)

def test_continuity_detects_conspicuous_cut():
    a=np.zeros((180,320,3),np.uint8);b=np.full_like(a,245)
    assert motion_pair(a,b)['reset']
    assert not motion_pair(a,a)['reset']

def test_world_keeps_nodes_and_builds_without_discrete_scene_swap():
    engine=world()
    assert len(engine.nodes)==5 and len({node.position for node in engine.nodes})==5
    image0=np.asarray(engine.render_layer(2.99)); image1=np.asarray(engine.render_layer(3.01))
    assert image0.shape==(360,640,4) and np.any(image0[:,:,3]) and np.any(image1[:,:,3])
    # No complete raster reset across the node's camera waypoint.
    assert not motion_pair(image0[:,:,:3],image1[:,:,:3])['reset']

def test_isolated_motion_spike_is_reported_as_reset():
    from aesthetic_gatekeeper import detect_reset_spikes
    quiet={'reset':False,'change':.001,'histogram_distance':.01,'flow_spread':.1}
    cut={'reset':False,'change':.02,'histogram_distance':.09,'flow_spread':4.}
    assert detect_reset_spikes([quiet,quiet,cut,quiet,quiet])==[3]
    smooth={'reset':False,'change':.02,'histogram_distance':.09,'flow_spread':4.}
    assert detect_reset_spikes([smooth]*5)==[]
