"""Five procedural documentary scenes; values in charts are illustrative."""
import json, math
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import PchipInterpolator
from numba import njit
from forge_python.motion.physics import drift

ROOT = Path(__file__).resolve().parents[2]
P = json.loads((ROOT/'design_system/palettes.json').read_text())
FONTS = ROOT/'shared_workspace/fonts'

@lru_cache(maxsize=128)
def font(name, size): return ImageFont.truetype(str(FONTS/name), max(8, int(size)))
def text(draw, xy, value, name, size, fill, **kw): draw.text(xy, value, font=font(name, size), fill=fill, **kw)
def wrap(draw, value, f, width):
    lines, line = [], ''
    for word in value.split():
        trial = (line+' '+word).strip()
        if draw.textlength(trial, font=f) > width and line: lines.append(line); line=word
        else: line=trial
    if line: lines.append(line)
    return lines

def base(w,h, archival=False):
    pal = P['archival_classified' if archival else 'obsidian_documentary']
    im=Image.new('RGB',(w,h),pal['background']); d=ImageDraw.Draw(im)
    color = '#d6d2c8' if archival else '#242935'
    step=max(12,int(w/65))
    for y in range(0,h,step):
        for x in range(0,w,step): d.point((x,y),fill=color)
    return im

def label(d, w, h, n, title, archival=False):
    ink='#18181B' if archival else '#F3F4F6'; accent='#DC2626' if archival else '#F59E0B'
    text(d,(w*.065,h*.06),f'FIELD NOTES    /    {n:02}', 'JetBrainsMono-Medium.ttf',h*.025,ink)
    text(d,(w*.065,h*.115),title.upper(),'JetBrainsMono-Medium.ttf',h*.022,accent)
    d.line((w*.065,h*.17,w*.935,h*.17),fill=ink,width=max(1,w//1000))

def scene_hook(w,h,t,p,topic,rms):
    im=base(w,h); d=ImageDraw.Draw(im); label(d,w,h,1,'The question')
    f=font('Inter-ExtraBold.ttf', min(h*.12,w*.065))
    for i,line in enumerate(wrap(d,topic,f,w*.83)[:4]): d.text((w*.065,h*(.27+i*.115)),line,font=f,fill='#F3F4F6',stroke_width=0)
    text(d,(w*.068,h*.77),'A closer look at the mechanism.', 'InstrumentSerif-Italic.ttf',h*.050,'#F59E0B')
    d.rectangle((w*.065,h*.90,w*(.065+.87*p),h*.906),fill='#06B6D4')
    return im

def scene_document(w,h,t,p,topic,rms):
    im=base(w,h,True); d=ImageDraw.Draw(im); label(d,w,h,2,'Evidence / reading room',True)
    d.rectangle((w*.11,h*.22,w*.89,h*.85),fill='#F8F5EE',outline='#BEB8AC',width=max(1,w//700))
    text(d,(w*.15,h*.27),'RESEARCH MEMO   /   001','JetBrainsMono-Medium.ttf',h*.026,'#DC2626')
    text(d,(w*.15,h*.37),'What is the system really doing?', 'InstrumentSerif-Italic.ttf',h*.050,'#18181B')
    is_ai = any(term in topic.lower() for term in (' ai', 'ai ', 'artificial intelligence', 'language model', 'chatgpt'))
    words=('A model predicts plausible language not guaranteed truth' if is_ai else 'Examine the evidence and check the context').split()
    f=font('Inter-ExtraBold.ttf',h*.035); x=w*.15; y=h*.55
    active=min(len(words)-1,int(p*len(words)))
    for i,word in enumerate(words):
        width=d.textlength(word+' ',font=f)
        if x+width > w*.83: x=w*.15; y+=h*.07
        if i==active: d.rectangle((x,y,x+width,y+h*.05),fill='#FACC15')
        d.text((x,y),word+' ',font=f,fill='#18181B'); x+=width
    text(d,(w*.15,h*.76),'ILLUSTRATIVE  /  NOT A SOURCE', 'JetBrainsMono-Medium.ttf',h*.022,'#77716A')
    return im

def scene_data(w,h,t,p,topic,rms):
    im=base(w,h); d=ImageDraw.Draw(im); label(d,w,h,3,'Signal / uncertainty')
    left,top,right,bottom=w*.09,h*.29,w*.91,h*.78
    for i in range(5):
        y=top+(bottom-top)*i/4; d.line((left,y,right,y),fill='#293442',width=1)
    xs=np.linspace(0,1,8); ys=np.array([.2,.27,.24,.45,.41,.67,.60,.84]); curve=PchipInterpolator(xs,ys)
    pts=[]
    for x in np.linspace(0,max(.001,p),100): pts.append((left+x*(right-left),bottom-float(curve(x))*(bottom-top)))
    d.line(pts,fill='#164457',width=max(3,int(w*.012)),joint='curve'); d.line(pts,fill='#06B6D4',width=max(2,int(w*.004)),joint='curve')
    text(d,(w*.09,h*.21),'PROBABILITY  /  ILLUSTRATIVE', 'JetBrainsMono-Medium.ttf',h*.026,'#F3F4F6')
    text(d,(w*.68,h*.20),f'{curve(p)*100:05.1f}', 'JetBrainsMono-Medium.ttf',h*.06,'#F59E0B')
    is_ai = any(term in topic.lower() for term in (' ai', 'ai ', 'artificial intelligence', 'language model', 'chatgpt'))
    text(d,(w*.09,h*.85),'A fluent answer is not a confidence guarantee.' if is_ai else 'Illustration only, not measured data.', 'InstrumentSerif-Italic.ttf',h*.040,'#F3F4F6')
    return im

@njit
def network(t):
    points=np.empty((30,2)); depth=np.empty(30)
    for i in range(30):
        a=i*2.399963; z=1-2*(i+.5)/30; r=math.sqrt(1-z*z); x=r*math.cos(a); y=r*math.sin(a)
        angle=t*.3; X=x*math.cos(angle)-z*math.sin(angle); Z=x*math.sin(angle)+z*math.cos(angle)
        points[i,0]=X/(2.7+Z); points[i,1]=y/(2.7+Z); depth[i]=Z
    return points,depth

def scene_neural(w,h,t,p,topic,rms):
    im=base(w,h); d=ImageDraw.Draw(im); label(d,w,h,4,'Inside the network')
    pts,depth=network(t); xy=[(w*.68+x*w*.63,h*.52+y*h*.95) for x,y in pts]
    for i in range(30):
        for j in range(i+1,30):
            if np.linalg.norm(pts[i]-pts[j]) < .18: d.line((*xy[i],*xy[j]),fill='#204052',width=1)
    for i,(x,y) in enumerate(xy):
        r=max(2,w*.004*(1+max(0,depth[i]))*(1+min(1,rms*5))); d.ellipse((x-r,y-r,x+r,y+r),fill='#06B6D4')
    text(d,(w*.07,h*.32),'PATTERN', 'Inter-ExtraBold.ttf',h*.075,'#F3F4F6')
    text(d,(w*.07,h*.42),'is not proof.', 'InstrumentSerif-Italic.ttf',h*.055,'#F59E0B')
    return im

def scene_hero(w,h,t,p,topic,rms):
    im=base(w,h); d=ImageDraw.Draw(im); label(d,w,h,5,'The takeaway')
    # A procedural illustrated monument; not a Three.js renderer.
    x=w*.75; y=h*.56; s=h*.23; shift=math.sin(t*.5)*w*.015
    d.polygon([(x+shift,y-s),(x+s*.55+shift,y-s*.7),(x+s*.55+shift,y+s*.7),(x+shift,y+s)],fill='#435467')
    d.polygon([(x+shift,y-s),(x-s*.55+shift,y-s*.7),(x-s*.55+shift,y+s*.7),(x+shift,y+s)],fill='#1F2B39')
    d.line((x+shift,y-s,x+shift,y+s),fill='#D5AD66',width=max(1,w//700))
    text(d,(w*.07,h*.31),'ASK.', 'Inter-ExtraBold.ttf',h*.11,'#F3F4F6')
    text(d,(w*.07,h*.43),'VERIFY.', 'Inter-ExtraBold.ttf',h*.11,'#F3F4F6')
    text(d,(w*.07,h*.60),'Think beyond the answer.', 'InstrumentSerif-Italic.ttf',h*.047,'#F59E0B')
    return im

SCENES=[scene_hook,scene_document,scene_data,scene_neural,scene_hero]
def render_frame(w,h,t,duration,topic,rms=0):
    section=min(4,int(t/duration*5)); p=min(1,(t-duration*section/5)/(duration/5))
    im=SCENES[section](w,h,t,p,topic,rms)
    a=np.asarray(im); d=drift(t)
    matrix=cv2.getRotationMatrix2D((w/2,h/2),0,d['scale']); matrix[0,2]+=d['x']*w; matrix[1,2]+=d['y']*h
    return cv2.warpAffine(a,matrix,(w,h),borderMode=cv2.BORDER_REFLECT_101)
