"""Validate a literal render and generate a dynamically sized beat contact sheet."""
import json,math,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scripts.motion_qa import video_frames,evaluate_deltas
from storyboard_compiler import validate_plan

def qa(video,timeline_path,sheet):
    video=Path(video);meta=json.loads(Path(timeline_path).read_text());beats=meta['beats'];validate_plan(meta);assert meta['fps']==60
    audit=json.loads(Path(str(video)+'.audit.json').read_text());assert audit['frames_checked']==meta['frames'] and audit['trigger_mismatches']==0
    selected=[]
    for b in beats:
        assert b['start_sample']<=b['trigger_sample']<b['end_sample']
        assert b['trigger_frame']==math.ceil(b['trigger_sample']*60/meta['sample_rate'])
        assert b['trigger_frame']/60>=b['trigger_sample']/meta['sample_rate']
        selected.append(min(meta['frames']-1,b['trigger_frame']+round(.4*60)))
    wanted=set(selected);images={};deltas=[];prev=None;count=0
    for count,frame in enumerate(video_frames(video),1):
        assert frame.shape==(meta['height'],meta['width'],3)
        if count-1 in wanted:images[count-1]=frame.copy()
        x=frame.astype(np.float32)
        if prev is not None:deltas.append(float(np.mean(np.abs(x-prev))))
        prev=x
    assert count==meta['frames'] and len(images)==len(wanted)
    stats=evaluate_deltas(deltas)
    audit['encoded_motion']=stats;Path(str(video)+'.audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    w,h=480,270;cols=3;rows=math.ceil(len(beats)/cols);canvas=Image.new('RGB',(w*cols,(h+85)*rows),'#111820');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('shared_workspace/fonts/Inter-ExtraBold.ttf',16);small=ImageFont.truetype('shared_workspace/fonts/JetBrainsMono-Medium.ttf',13)
    for i,(b,n) in enumerate(zip(beats,selected)):
        x=i%cols*w;y=i//cols*(h+85);canvas.paste(Image.fromarray(images[n]).resize((w,h),Image.Resampling.LANCZOS),(x,y))
        draw.text((x+8,y+272),f"BEAT {i}  [{b['beat_start_ms']/1000:.2f}–{b['beat_end_ms']/1000:.2f}s]",font=font,fill='white')
        draw.text((x+8,y+294),f"{b['trigger_word']} @ {b['trigger_word_ms']:.1f} ms",font=small,fill='#ecd58a')
        draw.text((x+8,y+313),'Actors: '+', '.join(b['visual_actors']),font=small,fill='#bcd4c2')
        draw.text((x+8,y+330),b['spoken_text'],font=small,fill='#bcd4c2')
    canvas.save(sheet);print(json.dumps(stats))
if __name__=='__main__':qa(*sys.argv[1:])
