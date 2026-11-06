"""150,000 deterministic particles evolved in an analytical curl velocity field."""
import math
import numpy as np
from numba import njit,prange

@njit(parallel=True,fastmath=True)
def particle_positions(seed,time):
    out=np.empty_like(seed)
    # Curl of A=(sin(y), sin(z), sin(x)); each velocity component is
    # independent of its corresponding coordinate, hence divergence is zero.
    for i in prange(len(seed)):
        x=seed[i,0];y=seed[i,1];z=seed[i,2]
        r=math.sqrt(x*x+y*y)+.04;a=math.atan2(y,x)+time*(1.5+.8/r)
        radius=1.3+6.5*r**1.4
        px=math.cos(a)*radius;py=math.sin(a)*radius;pz=z*4
        vx=-math.cos(pz*1.3-time);vy=-math.cos(px*1.5+time);vz=-math.cos(py*1.7+time)
        phase=min(1.,max(0.,(time-.3)/1.05));phase=phase*phase*(3-2*phase)
        blast=min(1.,max(0.,(time-1.4)/.95));blast=blast*blast*(3-2*blast)
        scale=1-.72*phase+1.4*blast
        out[i,0]=(px+vx*.35)*scale;out[i,1]=(py+vy*.35)*scale;out[i,2]=(pz+vz*.35)*scale
    return out

class ParticleField:
    def __init__(self,count=150000):
        self.seed=np.random.default_rng(31897).uniform(-1,1,(count,3)).astype(np.float32)
    def frame(self,t):return particle_positions(self.seed,t)
