"""Render the restored 288d795 visual layout against the current locked AAC."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.money_document import create_money_document
from art_render import audio_hash
from restore_timing import aligned_words,compile_times


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='renders/final_video.mp4');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--samples');p.add_argument('--alignment-json');a=p.parse_args()
    src=Path(a.source);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    meta=json.loads(Path(str(src)+'.json').read_text());assert meta['fps']==60 and len(meta['clauses'])==6
    original_hash=audio_hash(src)
    if a.alignment_json:
        aligned=json.loads(Path(a.alignment_json).read_text());words,beats=aligned['words'],aligned['beats']
    else:
        from faster_whisper import WhisperModel
        model=WhisperModel('base.en',device='cpu',compute_type='int8')
        words,beats=aligned_words(meta,model)
    cues,times=compile_times(meta,words);print('Scene cue estimates (+100ms):',cues,flush=True)
    with tempfile.TemporaryDirectory(prefix='.art-',dir=Path.cwd()) as td:
        tmp=Path(td);audio=tmp/'locked.m4a'
        subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(src),'-map','0:a:0','-c:a','copy',str(audio)],check=True)
        if audio_hash(audio)!=original_hash:raise RuntimeError('AAC extraction changed packets')
        _,box=create_money_document(tmp/'document.png')
        data={**meta,'words':words,'beats':beats,'cue_times':cues,'scene_times':times,'document':str((tmp/'document.png').relative_to(Path.cwd())),'highlight':box};(tmp/'data.json').write_text(json.dumps(data))
        w,h=map(int,a.resolution.split('x'))
        cmd=['node','web/morph/render.mjs',f'data={tmp/"data.json"}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={meta["frames"]}','copyaudio=1']
        if a.samples:cmd.append(f'samples={a.samples}')
        subprocess.run(cmd,check=True)
        if not a.samples:
            if audio_hash(out)!=original_hash:raise RuntimeError('AAC packets changed during render')
            meta.update(words=words,beats=beats,cue_times=cues,scene_times=times,locked_audio_sha256=original_hash,visual_renderer='288d795 restored Chromium React GSAP Three.js',timing_source='Faster-Whisper base.en estimated word starts plus 100ms',width=w,height=h)
            Path(str(out)+'.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__':main()
