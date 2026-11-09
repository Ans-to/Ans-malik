"""Check the full motion output and sample one frame per compiled beat."""
import json,subprocess,sys,re
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe
from art_render import audio_hash
from qa_inspector import audit

def main():
    path=Path(sys.argv[1]);sheet=Path(sys.argv[2]);meta=json.loads(Path(str(path)+'.json').read_text())
    # Validate with the bundled FFmpeg, avoiding OS-package/ffprobe installs.
    result=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-i',str(path),'-map','0:v:0','-c:v','copy','-progress','pipe:1','-f','null','-'],capture_output=True,text=True,check=True)
    description=result.stderr
    video=next((line for line in description.splitlines() if 'Video:' in line),'')
    audio=next((line for line in description.splitlines() if 'Audio:' in line),'')
    frames_seen=re.findall(r'^frame=(\d+)$',result.stdout,flags=re.M)
    duration_match=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',description)
    assert '1920x1080' in video and 'yuv420p' in video and re.search(r'\b60 fps\b',video),video
    assert frames_seen and int(frames_seen[-1])==meta['frames'],frames_seen
    assert duration_match and audio,description
    h,m,seconds=duration_match.groups();probed_duration=int(h)*3600+int(m)*60+float(seconds)
    assert abs(probed_duration-meta['duration'])<.05,(probed_duration,meta['duration'])
    assert meta['voice_mode']=='edge-tts+faster-whisper'
    if meta.get('locked_audio_sha256'):assert audio_hash(path)==meta['locked_audio_sha256'], 'Narration AAC packets changed'
    assert len(meta['beats'])>=5 and all(3<=len(b['words'])<=4 for b in meta['beats'])
    assert sum(len(b['word_ids']) for b in meta['beats'])==len(meta['words'])
    cues,extras=audit(meta)
    assert meta.get('audited_frames')==meta['frames'] and meta.get('pixel_audited_frames')==meta['frames'] and meta.get('audit_error_count')==0, 'Per-frame DOM audit missing or failed'
    # One sample after every actually spoken trigger.
    frames=[min(meta['frames']-1,c['first_frame']+max(1,min(18,(c['end_frame']-c['first_frame'])//2))) for c in cues]
    frames=sorted(set(frames+[min(meta['frames']-1,extras['trades']+5)]))
    filt="select='"+'+'.join(f'eq(n,{n})' for n in frames)+"',scale=480:270,tile=3x"+str((len(frames)+2)//3)+":padding=8:margin=8:color=0x11131b"
    subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(path),'-vf',filt,'-frames:v','1',str(sheet)],check=True)
    print(f"QA OK: {meta['frames']} frames at 1080p60, {len(meta['beats'])} aligned beats, audio stream present")
if __name__=='__main__':main()
