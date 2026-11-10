"""Compile a literal-actor storyboard, record each beat, and render it in Chromium."""
import argparse,asyncio,json,subprocess,tempfile
from pathlib import Path
from storyboard_compiler import load_plan
from icon_resolver import icon_body
from literal_audio import edge_clips,compile_timeline,write_master
from forge_python.ffmpeg import get_ffmpeg_exe


def render(topic,duration,output,storyboard=None,resolution='1920x1080',samples=None,timeline_path=None):
    plan=load_plan(topic,duration,storyboard);out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    w,h=map(int,resolution.split('x'))
    if w<64 or h<64 or w%2 or h%2:raise ValueError('Resolution must be even and at least 64x64')
    with tempfile.TemporaryDirectory(prefix='.literal-',dir=Path.cwd()) as d:
        tmp=Path(d);paths,events=asyncio.run(edge_clips(plan,tmp));speech,meta=compile_timeline(plan,paths,events);meta.update(width=w,height=h,plan_source=plan['plan_source'],semantic_review_required=plan.get('semantic_review_required',False),icon_matches=plan.get('icon_matches',[]),icon_definitions={a:icon_body(a) for b in plan['beats'] for a in b['visual_actors'] if a.startswith('iconify:')});audio=tmp/'master.wav';write_master(speech,meta,audio)
        import soundfile as sf
        raw=out.parent/(out.stem+'.speech.flac');sf.write(raw,speech,meta['sample_rate'],format='FLAC',subtype='PCM_16');meta['speech_source']=raw.name
        timeline=Path(timeline_path) if timeline_path else out.parent/'timeline.json';timeline.parent.mkdir(parents=True,exist_ok=True);timeline.write_text(json.dumps(meta,indent=2)+'\n');Path(str(out)+'.json').write_text(json.dumps(meta,indent=2)+'\n')
        cmd=['node','web/literal/render.mjs',f'data={timeline}',f'audio={audio}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={meta["frames"]}']
        if samples:cmd.append(f'samples={samples}')
        subprocess.run(cmd,check=True)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--topic',required=True);p.add_argument('--duration',type=float,default=15);p.add_argument('--storyboard',help='JSON storyboard for custom topics');p.add_argument('--resolution',default='1920x1080');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--samples');p.add_argument('--timeline');a=p.parse_args();print('Rendered',render(a.topic,a.duration,a.output,a.storyboard,a.resolution,a.samples,a.timeline))
if __name__=='__main__':main()
