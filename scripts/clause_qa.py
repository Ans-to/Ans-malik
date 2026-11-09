"""Verify sample windows and extract video frames for a labeled QA contact sheet."""
import json, math, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from forge_python.ffmpeg import get_ffmpeg_exe
from clause_audio import CLAUSES

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
    # Midpoints and pre-start frames are extracted from the encoded MP4 itself.
    font=ImageFont.truetype('shared_workspace/fonts/Inter-ExtraBold.ttf',18)
    small=ImageFont.truetype('shared_workspace/fonts/JetBrainsMono-Medium.ttf',14)
    canvas=Image.new('RGB',(3*640,2*440),'#111820');d=ImageDraw.Draw(canvas)
    with tempfile.TemporaryDirectory() as td:
        for i,c in enumerate(cs):
            pre=max(0,math.floor((c['start_sec']-.15)*60));mid=math.floor((c['start_sec']+c['end_sec'])*30)
            for kind,frame in [('pre',pre),('mid',mid)]:
                file=Path(td)/f'{i}-{kind}.png'
                subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(video),'-vf',f'select=eq(n\\,{frame}),scale=640:360','-fps_mode','passthrough','-frames:v','1',str(file)],check=True)
                assert file.exists() and file.stat().st_size>0
            x=(i%3)*640;y=(i//3)*440
            canvas.paste(Image.open(Path(td)/f'{i}-mid.png').convert('RGB'),(x,y))
            d.text((x+10,y+365),f"CLAUSE {i}   [{c['start_sec']:.6f} – {c['end_sec']:.6f}]",font=font,fill='white')
            import textwrap
            for j,line in enumerate(textwrap.wrap(c['spoken_text'],70)):
                d.text((x+10,y+392+j*17),line,font=small,fill='#bcd4c2')
            print(f'Clause {i}: pre frame {pre}, midpoint frame {mid}, sample window {c["start_sample"]}:{c["end_sample"]}')
    canvas.save(sheet)
    print('Verified exact PCM source windows and gaps; video scene gates checked in Chromium on every captured frame.')
if __name__=='__main__':qa(sys.argv[1],sys.argv[2])
