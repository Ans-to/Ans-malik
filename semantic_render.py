#!/usr/bin/env python3
"""Word-locked visual rebuild over the exact prior AAC and saved timing data."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from art_render import audio_hash
from forge_python.ffmpeg import get_ffmpeg_exe
from qa_inspector import audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='renders/final_video.mp4');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--samples');a=p.parse_args()
    root=Path.cwd();src=Path(a.source);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    meta=json.loads(Path(str(src)+'.json').read_text());assert meta['voice_mode']=='edge-tts+faster-whisper' and meta['neural_rate']=='+0%' and meta['fps']==60
    cues,extras=audit(meta);original_hash=audio_hash(src);w,h=map(int,a.resolution.split('x'))
    with tempfile.TemporaryDirectory(prefix='.semantic-',dir=root) as td:
        tmp=Path(td);audio=tmp/'locked.m4a';report=tmp/'audit.json'
        subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(src),'-map','0:a:0','-c:a','copy',str(audio)],check=True)
        if audio_hash(audio)!=original_hash:raise RuntimeError('audio changed during extraction')
        data={'frames':meta['frames'],'cues':cues,'extras':extras};(tmp/'data.json').write_text(json.dumps(data))
        cmd=['node','web/semantic/render.mjs',f'data={tmp/"data.json"}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={meta["frames"]}','copyaudio=1',f'auditoutput={report}']
        if a.samples:cmd.append(f'samples={a.samples}')
        subprocess.run(cmd,check=True)
        if not a.samples:
            if audio_hash(out)!=original_hash:raise RuntimeError('output audio packets changed')
            result=json.loads(report.read_text())
            if result['frames']!=meta['frames'] or result['pixelFrames']!=meta['frames'] or result['errors']:raise ValueError('Frame audit failed')
            meta.update(cues=cues,extras=extras,audited_frames=result['frames'],pixel_audited_frames=result['pixelFrames'],audit_error_count=len(result['errors']),locked_audio_sha256=original_hash,visual_renderer='Chromium React Remotion GSAP / semantic safe-zone');Path(str(out)+'.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__':main()
