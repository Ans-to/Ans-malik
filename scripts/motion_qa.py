"""Frame-by-frame RGB motion measurement for the encoded deliverable."""
import re
import subprocess
from collections import deque
import numpy as np
from forge_python.ffmpeg import get_ffmpeg_exe


def evaluate_deltas(deltas):
    values=np.asarray(deltas,dtype=np.float64)
    if not len(values):raise AssertionError('Video must contain at least two frames')
    fraction=float(np.count_nonzero(values>.65)/len(values))
    frozen=np.where((values[:-1]<.20)&(values[1:]<.20))[0]
    duplicates=int(np.count_nonzero(values==0))
    if fraction < .98 or len(frozen) or duplicates:
        raise AssertionError(f'motion gate failed: {fraction:.3%} pairs above .65; {len(frozen)} static three-frame windows; {duplicates} duplicate pairs; minimum delta {values.min():.4f}')
    return {'pairs':len(values),'fraction_above_065':fraction,'static_three_frame_windows':len(frozen),'duplicate_pairs':duplicates,'minimum_delta':float(values.min())}


def video_frames(path):
    probe=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-i',str(path)],capture_output=True,text=True)
    video=next((line for line in probe.stderr.splitlines() if 'Video:' in line),'')
    match=re.search(r'(\d{2,5})x(\d{2,5})',video)
    if not match or not re.search(r'\b60 fps\b',video):raise AssertionError(f'Expected 60fps video, got {video}')
    width,height=map(int,match.groups())
    process=subprocess.Popen([get_ffmpeg_exe(),'-v','error','-i',str(path),'-map','0:v:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=width*height*3*2)
    size=width*height*3
    try:
        while True:
            raw=process.stdout.read(size)
            if not raw:break
            if len(raw)!=size:raise AssertionError('Partial decoded video frame')
            yield np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3)
        error=process.stderr.read().decode();status=process.wait()
        if status:raise AssertionError(f'FFmpeg decode failed: {error}')
    finally:
        if process.poll() is None:process.kill();process.wait()


def inspect(path, expected_frames, wanted, expected_size=None):
    images={}; deltas=[]; previous=None; count=0
    for count,frame in enumerate(video_frames(path),start=1):
        if expected_size and (frame.shape[1],frame.shape[0])!=expected_size:raise AssertionError(f'Wrong dimensions: {frame.shape}')
        if count-1 in wanted:images[count-1]=frame.copy()
        current=frame.astype(np.float32)
        if previous is not None:deltas.append(float(np.mean(np.abs(current-previous))))
        previous=current
    if count!=expected_frames:raise AssertionError(f'Expected {expected_frames} frames, decoded {count}')
    stats=evaluate_deltas(deltas)
    if len(images)!=len(wanted):raise AssertionError('Missing QA sample frames')
    return stats,images
