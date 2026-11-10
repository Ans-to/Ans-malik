"""Inspect the restored MP4, including all frames and narration AAC packets."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from art_render import audio_hash
from restore_timing import compile_times
from scripts.motion_qa import video_frames


def qa(video,sheet):
    video=Path(video);meta=json.loads(Path(str(video)+'.json').read_text());assert meta['width']==1920 and meta['height']==1080 and meta['fps']==60
    assert audio_hash(video)==meta['locked_audio_sha256']
    cues,times=compile_times(meta,meta['words']);assert cues==meta['cue_times'] and times==meta['scene_times']
    cs=meta['clauses'];samples=[[min(meta['frames']-1,round((c['start_sec']+(c['end_sec']-c['start_sec'])*p)*60)) for p in (.2,.5,.8)] for c in cs];wanted=set(sum(samples,[]));images={};deltas=[];prev=None;count=0
    for count,frame in enumerate(video_frames(video),start=1):
        assert frame.shape==(1080,1920,3)
        if count-1 in wanted:images[count-1]=frame.copy()
        current=frame.astype(np.float32)
        if prev is not None:deltas.append(float(np.mean(np.abs(current-prev))))
        prev=current
    assert count==meta['frames'] and len(images)==len(wanted)
    arr=np.asarray(deltas);stats={'pairs':len(arr),'fraction_above_065':float(np.mean(arr>.65)),'static_three_frame_windows':int(np.sum((arr[:-1]<.2)&(arr[1:]<.2))),'duplicate_pairs':int(np.sum(arr==0))}
    print('Motion diagnostic (not a gate on restored historical animation):',stats)
    font=ImageFont.truetype('shared_workspace/fonts/Inter-ExtraBold.ttf',18);small=ImageFont.truetype('shared_workspace/fonts/JetBrainsMono-Medium.ttf',13)
    w,h=480,270;canvas=Image.new('RGB',(3*w,6*(h+83)),'#111820');d=ImageDraw.Draw(canvas)
    for i,c in enumerate(cs):
        for j,n in enumerate(samples[i]):
            x=j*w;y=i*(h+83);canvas.paste(Image.fromarray(images[n]).resize((w,h),Image.Resampling.LANCZOS),(x,y));d.text((x+10,y+274),f"CLAUSE {i}   p = {(0.2,0.5,0.8)[j]:.2f}",font=font,fill='white');d.text((x+10,y+300),f"{c['start_sec']:.3f}s – {c['end_sec']:.3f}s | frame {n}",font=small,fill='#bcd4c2');d.text((x+10,y+318),c['spoken_text'],font=small,fill='#bcd4c2')
    canvas.save(sheet);Path(str(video)+'.audit.json').write_text(json.dumps({'decoded_frames':count,'motion_diagnostic':stats,'audio_hash':meta['locked_audio_sha256']},indent=2)+'\n')
    print('Verified video format, frame count, cue metadata and unchanged AAC.')
if __name__=='__main__':qa(sys.argv[1],sys.argv[2])
