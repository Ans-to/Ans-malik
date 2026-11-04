"""Seven-layer, 2x supersampled editorial compositor used for every app frame."""
import math
from functools import lru_cache
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from scipy.interpolate import PchipInterpolator
from numba import njit
from forge_python.render.scenes import font, wrap
from forge_python.post_fx.optical_lens import finish_frame
from forge_python.motion.physics import spring, drift

@njit
def points3d(t, count=180):
    pts=np.empty((count,3))
    for i in range(count):
        a=i*2.399963; z=1-2*(i+.5)/count; r=math.sqrt(1-z*z)
        x=r*math.cos(a); y=r*math.sin(a); angle=t*.24
        X=x*math.cos(angle)-z*math.sin(angle); Z=x*math.sin(angle)+z*math.cos(angle)
        pts[i,0]=X/(2.7+Z);pts[i,1]=y/(2.7+Z);pts[i,2]=Z
    return pts

@njit
def chart_points(xs, values, left, bottom, width, height):
    """Project interpolated chart coordinates in compiled code."""
    result=np.empty((len(xs),2),dtype=np.float64)
    for i in range(len(xs)):
        result[i,0]=left+xs[i]*width
        result[i,1]=bottom-values[i]*height
    return result

class SevenLayerCompositor:
    def __init__(self,w,h,topic,words,document,hero,finisher=finish_frame,world=None):
        self.w,self.h=w,h;self.W,self.H=w*2,h*2; self.topic=topic;self.words=words;self.doc=document;self.hero=hero
        self.world=world; self.finisher=finisher; self.rng=np.random.default_rng(42); self.background=self._background();self.depth=self._depth()
        self.particles=np.random.default_rng(18).random((56,4))
        self.spring_curve=spring(np.arange(121,dtype=float)/60)
    def blank(self): return Image.new('RGBA',(self.W,self.H),(0,0,0,0))
    def _background(self):
        W,H=self.W,self.H
        # Precompute at output resolution and upscale; linework is added at 2x.
        y,x=np.mgrid[:self.h,:self.w]; r=np.sqrt(((x-self.w*.47)/(self.w*.72))**2+((y-self.h*.43)/(self.h*.83))**2)
        light=np.clip(1-r,0,1); a=np.empty((self.h,self.w,3),np.uint8)
        for c,(base,amp) in enumerate(((9,12),(11,15),(16,21))): a[:,:,c]=np.clip(base+amp*light,0,255)
        image=Image.fromarray(a).resize((W,H),Image.Resampling.LANCZOS).convert('RGBA'); grid=self.blank(); d=ImageDraw.Draw(grid,'RGBA'); step=max(20,W//40)
        for x in range(0,W,step): d.line((x,0,x,H),fill=(195,214,230,13),width=2)
        for y in range(0,H,step): d.line((0,y,W,y),fill=(195,214,230,13),width=2)
        for x in (W*.035,W*.965):
            for y in (H*.06,H*.94):
                d.line((x-8,y,x+8,y),fill=(145,177,194,110),width=2);d.line((x,y-8,x,y+8),fill=(145,177,194,110),width=2)
        return Image.alpha_composite(image,grid)
    def _depth(self):
        layer=self.blank();d=ImageDraw.Draw(layer,'RGBA');W,H=self.W,self.H
        for i in range(8):
            r=H*(.13+i*.055); x=W*.73;y=H*.47
            d.ellipse((x-r,y-r,x+r,y+r),outline=(75,157,180,40),width=2)
        for i in range(25):
            x=W*(.08+(i*0.137)%0.85);y=H*(.2+(i*.173)%0.63);d.line((x,y,x+W*.025,y),fill=(81,146,166,40),width=3)
        return layer.filter(ImageFilter.GaussianBlur(max(1,W//1600)))
    def _subject(self,act,t,p,rms):
        W,H=self.W,self.H; layer=self.blank();d=ImageDraw.Draw(layer,'RGBA')
        if act==1: return Image.fromarray(self.doc.frame(W,H,t,self.words,transparent=True),'RGBA')
        if act==4:
            frame=self.hero.frame(round((p)*self.scene_seconds*60),60,'')
            # Keep only the WebGL monument/right side; editorial copy is layer 5.
            arr=np.asarray(frame).copy(); light=np.max(arr,axis=2).astype(np.int16); alpha=np.clip((light-14)*5,0,255).astype(np.uint8);alpha[:,:int(W*.48)]=0
            return Image.fromarray(np.dstack((arr,alpha)),'RGBA')
        if act==2:
            left,top,right,bottom=W*.43,H*.25,W*.92,H*.75
            for i in range(6):
                y=top+i*(bottom-top)/5;d.line((left,y,right,y),fill=(133,165,187,95),width=2)
            for i in range(7):
                x=left+i*(right-left)/6;d.line((x,top,x,bottom),fill=(96,132,155,43),width=2)
            curve=PchipInterpolator(np.linspace(0,1,9),[.18,.27,.23,.45,.37,.59,.55,.7,.84]); end=max(.02,(1-math.exp(-4*p))/(1-math.exp(-4)))
            xs=np.linspace(0,end,240); points=[tuple(point) for point in chart_points(xs,curve(xs),left,bottom,right-left,bottom-top)]
            poly=[(left,bottom),*points,(points[-1][0],bottom)]
            mask=Image.new('L',(W,H));ImageDraw.Draw(mask).polygon(poly,fill=1); mask=np.asarray(mask,dtype=np.uint8)
            grad=np.zeros((H,W,4),np.uint8); grad[:,:,0]=6;grad[:,:,1]=145;grad[:,:,2]=174; grad[:,:,3]=(mask*np.broadcast_to(np.linspace(100,5,H,dtype=np.uint8)[:,None],(H,W)))
            layer=Image.alpha_composite(layer,Image.fromarray(grad));d=ImageDraw.Draw(layer,'RGBA')
            avg=[(left+x*(right-left),bottom-float(curve(max(0,x-.05))*.88)*(bottom-top)) for x in xs]
            d.line(avg,fill=(245,158,11,135),width=max(2,W//1800),joint='curve')
            d.line(points,fill=(6,182,212,60),width=max(8,W//220),joint='curve')
            data=np.asarray(layer).copy(); vertices=np.asarray(points,dtype=np.int32).reshape(-1,1,2)
            cv2.polylines(data,[vertices],False,(93,225,238,245),max(3,W//850),lineType=cv2.LINE_AA)
            x,y=points[-1]; radius=H*(.012+.003*math.sin(t*5));cv2.circle(data,(int(x),int(y)),int(radius),(245,190,70,230),3,lineType=cv2.LINE_AA)
            cv2.line(data,(int(x-radius*1.6),int(y)),(int(x+radius*1.6),int(y)),(243,244,246,180),2,lineType=cv2.LINE_AA)
            layer=Image.fromarray(data,'RGBA')
            d=ImageDraw.Draw(layer,'RGBA')
            d.text((right-W*.15,top-H*.055), f'{float(curve(end))*100:05.1f}', font=font('JetBrainsMono-Medium.ttf',H*.035), fill=(245,158,11,235))
            d.text((left,top-H*.045),'ILLUSTRATIVE  /  INDEX',font=font('JetBrainsMono-Medium.ttf',H*.014),fill=(150,182,196,200))
        elif act==3:
            pts=points3d(t);xy=np.column_stack((W*.71+pts[:,0]*W*.75,H*.49+pts[:,1]*H*1.45));order=np.argsort(pts[:,2])
            for i in order:
                ds=np.sum((pts[:,:2]-pts[i,:2])**2,axis=1); near=np.argsort(ds)[1:5]
                for j in near:
                    if j>i:
                        pulse=.6+.4*math.sin(t*3+i*.37+j*.19)
                        d.line((*xy[i],*xy[j]),fill=(40,145,170,int((25+35*(pts[i,2]+1))*pulse)),width=2)
            for i in order:
                x,y=xy[i]; z=pts[i,2]; r=max(2,H*.003*(1.2+z*.5)*(1+min(1,rms*3)))
                # Analytic warm key, cool fill and rim on the rotating spherical normals.
                normal=np.array([pts[i,0]*(2.7+z),pts[i,1]*(2.7+z),z]); normal/=max(1e-6,np.linalg.norm(normal))
                key=np.array([.45,-.5,.74]); fill=np.array([-.7,.1,.71]); rim=np.array([0.,-.3,-.95])
                diffuse=max(0.,float(normal@key))*.9+max(0.,float(normal@fill))*.45+max(0.,float(normal@rim))*1.1
                spec=max(0.,float(normal@np.array([.23,-.25,.94])))**24
                red=int(min(240,45+diffuse*60+spec*125)); green=int(min(240,105+diffuse*85+spec*110)); blue=int(min(245,130+diffuse*75+spec*100))
                d.ellipse((x-r*2,y-r*2,x+r*2,y+r*2),fill=(6,182,212,35));d.ellipse((x-r,y-r,x+r,y+r),fill=(red,green,blue,215))
        else:
            x,y=W*.72,H*.48
            for i in range(7):
                r=H*(.12+i*.035); d.ellipse((x-r,y-r*.65,x+r,y+r*.65),outline=(48,160,185,65+i*8),width=3)
            for i in range(26):
                a=i*2*math.pi/26+t*.17;r=H*(.18+.05*math.sin(i*2.4));px=x+math.cos(a)*r;py=y+math.sin(a)*r*.65
                d.ellipse((px-5,py-5,px+5,py+5),fill=(90,208,222,200))
            d.line((x-H*.24,y,x+H*.24,y),fill=(245,158,11,125),width=2)
        return layer
    def _hud(self,act,t):
        W,H=self.W,self.H; img=self.blank();d=ImageDraw.Draw(img,'RGBA')
        x,y=int(W*.065),int(H*.66); cw,ch=int(W*.295),int(H*.105)
        d.rounded_rectangle((x,y,x+cw,y+ch),radius=H//100,fill=(25,37,48,190),outline=(155,189,207,130),width=2)
        d.line((x+3,y+3,x+cw*.55,y+3),fill=(226,238,243,170),width=3)
        labels=['SIGNAL / 01','SOURCE / 02','MODEL / 03','NETWORK / 04','REVIEW / 05']
        d.text((x+cw*.05,y+ch*.15),labels[act],font=font('JetBrainsMono-Medium.ttf',H*.019),fill=(115,214,226,255))
        d.text((x+cw*.05,y+ch*.51),'EVIDENCE  •  CONTEXT  •  VERIFY',font=font('JetBrainsMono-Medium.ttf',H*.014),fill=(228,231,234,205))
        sx=x+cw;sy=y+ch*.5; ex=W*.42;ey=H*.58
        local=max(0,t-act*self.scene_seconds); progress=1-math.exp(-6*local/max(self.scene_seconds,.01))
        middle=(sx+W*.025,sy)
        if progress < .35: d.line((sx,sy,sx+(middle[0]-sx)*progress/.35,sy),fill=(115,198,211,150),width=2)
        else:
            d.line((sx,sy,*middle),fill=(115,198,211,150),width=2); q=(progress-.35)/.65
            d.line((*middle,middle[0]+(ex-middle[0])*q,middle[1]+(ey-middle[1])*q),fill=(115,198,211,150),width=2)
        if progress > .9:
            r=H*.009;d.ellipse((ex-r,ey-r,ex+r,ey+r),outline=(245,158,11,210),width=2)
        return img
    def _type(self,act,t,p):
        W,H=self.W,self.H;img=self.blank();d=ImageDraw.Draw(img,'RGBA')
        names=['THE QUESTION','THE RECORD','SIGNAL & UNCERTAINTY','THE NETWORK','THE TAKEAWAY']
        d.text((W*.065,H*.075),f'[{act+1:02} // {names[act]}]',font=font('JetBrainsMono-Medium.ttf',H*.022),fill=(6,182,212,255))
        d.line((W*.065,H*.12,W*.36,H*.12),fill=(180,207,220,120),width=2)
        headings=[self.topic,'A closer\nreading.','Confidence\nis not truth.','Patterns\nare not proof.','Ask.\nThen verify.']
        size=H*(.077 if act==0 else .082)
        while True:
            f=font('Inter-ExtraBold.ttf',size); lines=[]
            for line in headings[act].split('\n'): lines.extend(wrap(d,line,f,W*.35))
            if (len(lines)<=4 and all(d.textlength(line,font=f)<=W*.35 for line in lines)) or size<=H*.025: break
            size*=.90
        # Excessively long unbreakable words get an explicit ellipsis instead of clipping.
        if len(lines)>4: lines=lines[:4]; lines[-1]=lines[-1]+'…'
        for n,line in enumerate(lines):
            while len(line)>1 and d.textlength(line,font=f)>W*.35: line=line[:-2]+'…'
            lines[n]=line
        # Temporal supersampling of a damped spring entrance: 180-degree shutter,
        # ten samples, on a tightly cropped alpha mask rather than ten full frames.
        local=max(0,t-act*self.scene_seconds)
        mask=Image.new('L',(int(W*.43),int(H*.41)))
        samples=10 if local < 1.5 else 1
        for k in range(samples):
            sample_time=max(0,local-(k+.5)/samples/120)
            index=min(len(self.spring_curve)-1,int(sample_time*60))
            value=self.spring_curve[index]
            x=W*(.065-.04*(1-value))
            part=Image.new('L',mask.size);pd=ImageDraw.Draw(part)
            for i,line in enumerate(lines): pd.text((x,H*(.21+i*.09)-H*.18),line,font=f,fill=255//samples)
            mask=ImageChops.add(mask,part)
        img.paste((243,244,246,255),(0,int(H*.18)),mask)
        d=ImageDraw.Draw(img,'RGBA')
        d.text((W*.065,H*.56),['Look beyond the answer.','Read the fine print.','Illustrative, not measured.','Inside the model.','A better question begins here.'][act],font=font('InstrumentSerif-Italic.ttf',H*.037),fill=(245,158,11,255))
        active=next((word for word in self.words if word['start_ms']<=t*1000<word['end_ms']),None)
        selected=[word for word in self.words if word['act']==act]
        if active:
            i=next((j for j,v in enumerate(selected) if v['word_id']==active['word_id']),0);lo=max(0,i-2);parts=selected[lo:min(len(selected),lo+5)]
            size=H*.025; available=W*(.37 if act==1 else .70)
            while True:
                f=font('JetBrainsMono-Medium.ttf',size); lengths=[d.textlength(z['word']+' ',font=f) for z in parts];total=sum(lengths)
                if total<=available or size<=H*.012: break
                size*=.9
            x=W*.065 if act==1 else max(W*.1,(W-total)/2); y=H*.89
            d.rounded_rectangle((x-H*.025,y-H*.013,x+total+H*.025,y+H*.044),radius=H*.02,fill=(10,15,21,220),outline=(130,156,170,100),width=2)
            for z,length in zip(parts,lengths):
                d.text((x,y),z['word'],font=f,fill=(245,158,11,255) if z['word_id']==active['word_id'] else (224,228,233,220));x+=length
        else: d.text((W*.42,H*.91),'FIELD NOTES   /   VISUAL ESSAY',font=font('JetBrainsMono-Medium.ttf',H*.016),fill=(125,153,170,160))
        return img
    def _world_type(self,t):
        W,H=self.W,self.H;img=self.blank();d=ImageDraw.Draw(img,'RGBA')
        d.text((W*.055,H*.055),'CONTINUOUS FIELD / VISUAL ESSAY',font=font('JetBrainsMono-Medium.ttf',H*.019),fill=(130,205,220,210))
        active=next((word for word in self.words if word['start_ms']<=t*1000<word['end_ms']),None)
        if active:
            idx=next(i for i,item in enumerate(self.words) if item['word_id']==active['word_id'])
            parts=self.words[max(0,idx-2):min(len(self.words),idx+3)]
            size=H*.023; available=W*.8
            while True:
                f=font('JetBrainsMono-Medium.ttf',size); lengths=[d.textlength(z['word']+' ',font=f) for z in parts]; total=sum(lengths)
                if total<=available or size<=H*.012:break
                size*=.9
            x=max(W*.05,(W-total)/2);y=H*.91
            d.rounded_rectangle((x-H*.02,y-H*.012,x+total+H*.02,y+H*.04),radius=H*.018,fill=(10,15,21,225),outline=(130,156,170,110),width=2)
            for z,length in zip(parts,lengths):
                d.text((x,y),z['word'],font=f,fill=(245,158,11,255) if z['word_id']==active['word_id'] else (224,228,233,220));x+=length
        else:
            d.text((W*.06,H*.92),'FOLLOW THE EVIDENCE',font=font('JetBrainsMono-Medium.ttf',H*.017),fill=(125,153,170,160))
        return img
    def _dust(self,t):
        W,H=self.W,self.H;img=self.blank();d=ImageDraw.Draw(img,'RGBA')
        for i,(a,b,c,e) in enumerate(self.particles):
            x=((a+t*(.002+c*.003))%1)*W; y=((b+t*(.001+e*.002))%1)*H;r=max(2,H*(.0012+c*.002))
            d.ellipse((x-r*2,y-r*2,x+r*2,y+r*2),fill=(147,198,218,18));d.ellipse((x-r,y-r,x+r,y+r),fill=(210,230,235,35+int(c*50)))
        return img
    def compose(self,act,t,p,rms,duration):
        self.scene_seconds=duration/5; W,H=self.W,self.H
        layers=[]
        ground=self.background.copy(); gd=ImageDraw.Draw(ground,'RGBA')
        frame=round(t*60); hours=frame//216000; minutes=(frame//3600)%60; seconds=(frame//60)%60; frames=frame%60
        gd.text((W*.80,H*.075),f'{hours:02}:{minutes:02}:{seconds:02}:{frames:02}',font=font('JetBrainsMono-Medium.ttf',H*.020),fill=(166,192,208,200))
        layers.append(ground)
        dx=int(math.sin(t*.11)*W*.002);dy=int(math.sin(t*.09)*H*.002)
        layers.append(self.depth.transform((W,H),Image.Transform.AFFINE,(1,0,dx,0,1,dy),resample=Image.Resampling.BILINEAR))
        subject=self.world.render_layer(t,rms) if self.world else self._subject(act,t,p,rms)
        # Project the subject's actual silhouette into an ambient shadow rather
        # than placing a generic oval under unrelated foreground content.
        silhouette=subject.getchannel('A').filter(ImageFilter.GaussianBlur(max(2,W//350)))
        silhouette=silhouette.point(lambda a: int(a*.28))
        shadow=self.blank(); shadow.paste((2,4,8,255),(max(1,W//250),max(1,H//180),W,H),silhouette.crop((0,0,W-max(1,W//250),H-max(1,H//180))))
        layers.append(shadow); layers.append(subject); layers.append(self._hud(0 if self.world else act,t));layers.append(self._world_type(t) if self.world else self._type(act,t,p));layers.append(self._dust(t))
        canvas=Image.new('RGBA',(W,H))
        for i,layer in enumerate(layers):
            pixels=np.asarray(layer)
            sample=pixels[::max(1,H//200),::max(1,W//200)]
            if pixels.shape != (H,W,4) or np.count_nonzero(pixels[:,:,3]) == 0 or not np.any(np.var(sample,axis=(0,1)) >= .01):
                raise ValueError(f'Layer {i} is empty or lacks variance')
            if i == 4:
                # Blur only the area underneath the glass card; keep its rim crisp.
                x0,y0,x1,y1=map(int,(W*.065,H*.66,W*.36,H*.765))
                crop=canvas.crop((x0,y0,x1,y1)).filter(ImageFilter.GaussianBlur(max(2,W//900)))
                mask=Image.new('L',(x1-x0,y1-y0)); ImageDraw.Draw(mask).rounded_rectangle((0,0,x1-x0-1,y1-y0-1),radius=H//100,fill=210)
                canvas.paste(crop,(x0,y0),mask)
            canvas=Image.alpha_composite(canvas,layer)
        output=cv2.resize(np.asarray(canvas.convert('RGB')),(self.w,self.h),interpolation=cv2.INTER_AREA)
        # A continuous micro-camera drift applies to every composition.
        motion=drift(t)
        mat=cv2.getRotationMatrix2D((self.w/2,self.h/2),0,motion['scale'])
        mat[0,2]+=motion['x']*self.w; mat[1,2]+=motion['y']*self.h
        output=cv2.warpAffine(output,mat,(self.w,self.h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        if self.world: output=self.world.apply_blur(output,t)
        return self.finisher(output,self.rng)
