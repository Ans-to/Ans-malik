"""Compile semantic cues from the locked Whisper timestamps and audit causality.

The original master does not contain Edge WordBoundary events. These checks
therefore validate against existing Whisper estimates, not exact phoneme onset.
"""
import json,math,re,sys
from pathlib import Path

OFFSET_MS=40

def compile_cues(words,frames):
    def find(token,occurrence=0):
        matches=[w for w in words if re.sub(r'[^a-z0-9%]','',w['word'].lower())==token]
        if len(matches)<=occurrence:raise ValueError(f'Missing narration keyword: {token} occurrence {occurrence+1}')
        return matches[occurrence]
    specs=[('calendar','1971',0),('country','states',0),('ended','ended',0),('dollar','dollar',0),('conversion','conversion',0),('gold','gold',0),('year','2022',0),('dollar_later','dollar',1),('stat','88',0)]
    cues=[]
    for name,token,n in specs:
        word=find(token,n);trigger=word['start_ms'];frame=math.ceil((trigger+OFFSET_MS)*60/1000)
        cues.append({'id':name,'word':word['word'],'word_id':word['word_id'],'trigger_ms':trigger,'first_frame':frame})
    for cue,next_cue in zip(cues,cues[1:]):
        if cue['first_frame']>=next_cue['first_frame']:raise ValueError('Cue order is not strictly increasing')
        cue['end_frame']=next_cue['first_frame']
    cues[-1]['end_frame']=frames
    # Text is also gated: do not show percent, exchange, or trades early.
    extras={k:math.ceil((find(token)['start_ms']+OFFSET_MS)*60/1000) for k,token in [('percent','%'),('foreign','foreign'),('exchange','exchange'),('trades','trades')]}
    return cues,extras

def audit(meta):
    cues,extras=compile_cues(meta['words'],meta['frames'])
    print('Timing source: Faster-Whisper estimates (Edge WordBoundary events were not saved).')
    for token in ['1971','rewrote','gold','digital','today','88']:
        matches=[w for w in meta['words'] if re.sub(r'[^a-z0-9%]','',w['word'].lower())==token]
        print(f'{token}: '+(', '.join(str(w["start_ms"])+" ms" for w in matches) if matches else 'NOT SPOKEN / unavailable'))
    for cue in cues:
        first_ms=cue['first_frame']*1000/60
        assert first_ms>=cue['trigger_ms']+OFFSET_MS
        print(f"{cue['id']}: trigger {cue['trigger_ms']} ms; first possible frame {cue['first_frame']} ({first_ms:.2f} ms)")
    for frame in range(meta['frames']):
        active=[c for c in cues if c['first_frame']<=frame<c['end_frame']]
        assert len(active)<=1
        assert all(frame*1000/60>=c['trigger_ms']+OFFSET_MS for c in active)
    return cues,extras

if __name__=='__main__':audit(json.loads(Path(sys.argv[1]).read_text()))
