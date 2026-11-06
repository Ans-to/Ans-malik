"""Numba CPU signed-distance ray marcher for the liquid-metal cathedral."""
import math
import numpy as np
from numba import njit,prange
import cv2

@njit(fastmath=True)
def sdf(x,y,z,t):
    # Repeating vault arches and columns, warped as the camera flies through.
    x+=.4*math.sin(z*.3+t*.7); y+=.15*math.sin(z*.5+t)
    qz=abs((z+2.5)%5.-2.5)
    column=math.sqrt((abs(x)-3.)**2+(qz)**2)-.32
    arch=abs(math.sqrt(x*x+(y+1.0)**2)-3.1)-.18
    arch=max(arch,qz-.22)
    floor=y+2.5
    return min(column,arch,floor)

@njit(parallel=True,fastmath=True)
def raymarch(width,height,t):
    out=np.zeros((height,width,3),np.uint8); roll=.698*math.sin(t*1.2); c=math.cos(roll);s=math.sin(roll)
    z0=t*8.;cx=.9*math.sin(t*.7)
    for y in prange(height):
        for x in range(width):
            u=(x/width-.5)*width/height*1.3;v=(.5-y/height)*1.3
            dx=u*c-v*s;dy=u*s+v*c;dz=1.;length=math.sqrt(dx*dx+dy*dy+1.);dx/=length;dy/=length;dz/=length
            travel=.05;hit=False
            for _ in range(65):
                px=cx+dx*travel;py=dy*travel;pz=z0+dz*travel
                d=sdf(px,py,pz,t)
                if d<.012:hit=True;break
                travel+=max(.025,d*.7)
                if travel>32:break
            if hit:
                e=.02;nx=sdf(px+e,py,pz,t)-sdf(px-e,py,pz,t);ny=sdf(px,py+e,pz,t)-sdf(px,py-e,pz,t);nz=sdf(px,py,pz+e,t)-sdf(px,py,pz-e,t);n=math.sqrt(nx*nx+ny*ny+nz*nz)+.0001;nx/=n;ny/=n;nz/=n
                key=max(0.,nx*.4+ny*.6-nz*.69);spec=max(0.,nx*(-dx)+ny*(-dy)+nz*(-dz))**12
                ao=min(1.,max(.35,sdf(px+nx*.28,py+ny*.28,pz+nz*.28,t)/.28));fog=math.exp(-travel*.055)
                out[y,x,0]=min(255,12+fog*(110*key+90*spec)*ao);out[y,x,1]=min(255,15+fog*(85*key+130*spec)*ao);out[y,x,2]=min(255,25+fog*(90*key+150*spec)*ao)
            else:
                out[y,x,0]=8;out[y,x,1]=10;out[y,x,2]=17
    return out

def frame(width,height,t):
    # Render at reduced internal resolution; preserve the 16:9 camera field.
    w=min(480,width);h=max(1,round(w*height/width));return cv2.resize(raymarch(w,h,t),(width,height),interpolation=cv2.INTER_CUBIC)
