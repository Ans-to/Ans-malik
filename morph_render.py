#!/usr/bin/env python3
"""Prepare audio/document assets; render the entire visual chain in Chromium."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from forge_python.morph_audio import prepare
from forge_python.editorial_audio import create_document
from forge_python.ffmpeg import get_ffmpeg_exe

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--offline',action='store_true');p.add_argument('--require-online',action='store_true');p.add_argument('--whisper-model',default='base.en');p.add_argument('--samples');a=p.parse_args()
    if a.offline and a.require_online:p.error('offline and require-online are incompatible')
    w,h=map(int,a.resolution.split('x'));root=Path.cwd();out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.morph-',dir=root) as td:
        tmp=Path(td);audio,words,beats,mode,text,frames=prepare(tmp,a.offline,a.require_online,a.whisper_model)
        _,box=create_document('AI',tmp/'document.png')
        data={'topic':'Why Your AI Gives You Wrong Answers','words':words,'beats':beats,'document':str((tmp/'document.png').relative_to(root)),'highlight':box,'frames':frames}
        (tmp/'data.json').write_text(json.dumps(data))
        cmd=['node','web/morph/render.mjs',f'data={tmp/"data.json"}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={frames}']
        if a.samples:cmd.append(f'samples={a.samples}')
        subprocess.run(cmd,check=True)
        if not a.samples:Path(str(out)+'.json').write_text(json.dumps({**data,'document':'ReportLab PDF texture','duration':frames/60,'fps':60,'resolution':a.resolution,'narration':text,'voice_mode':mode,'visual_renderer':'Chromium React Remotion GSAP Three.js'},indent=2))
if __name__=='__main__':main()
