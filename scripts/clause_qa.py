"""Validate clause sample windows, encoded motion and within-clause contact sheet."""
import json, math, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from clause_audio import CLAUSES
from scripts.motion_qa import inspect


def qa(video, sheet):
    video=Path(video); meta=json.loads(Path(str(video)+'.json').read_text()); sr=meta['sample_rate']; cs=meta['clauses']; assert len(cs)==6
    audit=json.loads(Path(str(video)+'.audit.json').read_text());assert audit['audited_frames']==meta['frames'] and audit['early_visibility_errors']==0
    mix,rate=sf.read(video.parent/'clause-mix.wav',dtype='int16'); assert rate==sr and len(mix)==meta['total_samples']
    for i,c in enumerate(cs):
        assert c['clause_id']==i and c['spoken_text']==CLAUSES[i]
        source,source_sr=sf.read(Path('assets/clause-voice')/f'clause_{i}.wav',dtype='int16'); a,b=c['start_sample'],c['end_sample']
        assert source_sr==sr and b-a==len(source) and np.array_equal(source,mix[a:b])
        assert c['start_sec']==a/sr and c['end_sec']==b/sr
        if i: assert a-cs[i-1]['end_sample']==round(sr*.18) and not mix[cs[i-1]['end_sample']:a].any()
    frames=[[min(meta['frames']-1,round((c['start_sec']+(c['end_sec']-c['start_sec'])*p)*60)) for p in (.2,.5,.8)] for c in cs]
    pre=[max(0,math.floor((c['start_sec']-.15)*60)) for c in cs]
    stats,images=inspect(video,meta['frames'],set(pre+sum(frames,[])),(meta['width'],meta['height']))
    audit['encoded_motion']=stats;Path(str(video)+'.audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    font=ImageFont.truetype('shared_workspace/fonts/Inter-ExtraBold.ttf',18)
    small=ImageFont.truetype('shared_workspace/fonts/JetBrainsMono-Medium.ttf',13)
    width,height=480,270;canvas=Image.new('RGB',(3*width,6*(height+83)),'#111820');d=ImageDraw.Draw(canvas)
    for i,c in enumerate(cs):
        for j,n in enumerate(frames[i]):
            x=j*width;y=i*(height+83);image=Image.fromarray(images[n]).resize((width,height),Image.Resampling.LANCZOS);canvas.paste(image,(x,y))
            d.text((x+10,y+274),f"CLAUSE {i}   p = {(0.2,0.5,0.8)[j]:.2f}",font=font,fill='white')
            d.text((x+10,y+300),f"{c['start_sec']:.3f}s – {c['end_sec']:.3f}s | frame {n}",font=small,fill='#bcd4c2')
            d.text((x+10,y+318),c['spoken_text'],font=small,fill='#bcd4c2')
        print(f'Clause {i}: pre frame {pre[i]}, motion frames {frames[i]}')
    canvas.save(sheet)
    print('PCM boundaries and video motion gate:',json.dumps(stats))
if __name__=='__main__':qa(sys.argv[1],sys.argv[2])
