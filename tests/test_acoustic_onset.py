import numpy as np
from acoustic_onset import estimate_onset

def test_detects_audible_rise_near_event():
    sr=48000;x=np.zeros(sr,dtype=np.float32);onset=int(.5*sr);t=np.arange(sr-onset)/sr;x[onset:]=.4*np.sin(2*np.pi*700*t)
    result=estimate_onset(x,sr,onset+round(.035*sr))
    assert result['status']=='snapped' and abs(result['sample']-onset)<.03*sr
    assert result['rms_rise']>0 and result['flux']>0

def test_silent_or_stationary_signal_falls_back_without_fabricating_onset():
    x=np.zeros(48000);r=estimate_onset(x,48000,10000)
    assert r['status']=='fallback' and r['sample']==10000
