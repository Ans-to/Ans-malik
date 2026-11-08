#!/usr/bin/env python3
"""Prepare narration and document texture, then render every frame in Chromium."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from forge_python.editorial_audio import make_audio,create_document
from forge_python.ffmpeg import get_ffmpeg_exe

def main():
    p=argparse.ArgumentParser();p.add_argument('--topic',default='Why Your AI Gives You Wrong Answers');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--offline',action='store_true');p.add_argument('--require-online',action='store_true');p.add_argument('--whisper-model',default='base.en');p.add_argument('--samples',help='Save five representative frames at this path prefix rather than render the video');p.add_argument('--frames',type=int,default=900);args=p.parse_args()
    w,h=map(int,args.resolution.split('x'));assert w%2==0 and h%2==0
    root=Path.cwd();out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    # Chromium's static server only serves repo paths.
    with tempfile.TemporaryDirectory(prefix='.editorial-',dir=root) as td:
        tmp=Path(td);audio,words,mode,text=make_audio(args.topic,15,tmp,args.offline,args.require_online,args.whisper_model)
        _,box=create_document(args.topic,tmp/'document.png')
        data={'topic':args.topic,'words':words,'document':str((tmp/'document.png').relative_to(root)),'highlight':box};(tmp/'data.json').write_text(json.dumps(data))
        cmd=['node','web/editorial/render.mjs',f'data={tmp/"data.json"}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={args.frames}']
        if args.samples:cmd.append(f'samples={args.samples}')
        subprocess.run(cmd,check=True)
        if not args.samples:Path(str(out)+'.json').write_text(json.dumps({'topic':args.topic,'duration':15,'fps':60,'frames':args.frames,'resolution':args.resolution,'narration':text,'voice_mode':mode,'word_timestamps':words,'visual_renderer':'Chromium React Remotion GSAP Three.js'},indent=2))
if __name__=='__main__':main()
