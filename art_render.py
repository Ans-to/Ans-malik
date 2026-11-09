#!/usr/bin/env python3
"""Render new visuals against the exact AAC packets and timings of a locked master."""
import argparse, hashlib,json,subprocess,tempfile
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.money_document import create_money_document
from style_clock import compile_visual_marks

def audio_hash(path):
    # Hash encoded AAC packets, not decoded PCM or MP4 container metadata.
    result=subprocess.check_output([get_ffmpeg_exe(),'-v','error','-i',str(path),'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-'])
    return result.decode().strip()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='renders/final_video.mp4');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--samples');a=p.parse_args()
    root=Path.cwd();src=Path(a.source);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    meta=json.loads(Path(str(src)+'.json').read_text());assert meta['voice_mode']=='edge-tts+faster-whisper'
    assert meta['neural_rate']=='+0%' and meta['fps']==60
    original_hash=audio_hash(src);w,h=map(int,a.resolution.split('x'))
    with tempfile.TemporaryDirectory(prefix='.art-',dir=root) as td:
        tmp=Path(td);audio=tmp/'locked.m4a'
        subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(src),'-map','0:a:0','-c:a','copy',str(audio)],check=True)
        if audio_hash(audio)!=original_hash:raise RuntimeError('audio changed during extraction')
        _,box=create_money_document(tmp/'document.png')
        visual_marks=compile_visual_marks(meta)
        data={**meta,'visual_marks':visual_marks,'document':str((tmp/'document.png').relative_to(root)),'highlight':box};(tmp/'data.json').write_text(json.dumps(data))
        cmd=['node','web/morph/render.mjs',f'data={tmp/"data.json"}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={meta["frames"]}','copyaudio=1']
        if a.samples:cmd.append(f'samples={a.samples}')
        subprocess.run(cmd,check=True)
        if not a.samples:
            output_hash=audio_hash(out)
            if output_hash!=original_hash:raise RuntimeError(f'audio packets changed: {original_hash} != {output_hash}')
            
            for stale in ('cues','extras','audited_frames','pixel_audited_frames','audit_error_count'):meta.pop(stale,None)
            meta.update(visual_marks=visual_marks,locked_audio_sha256=original_hash,visual_renderer='Chromium React Remotion GSAP Three.js / mixed media');Path(str(out)+'.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__':main()
