"""Derive scene timing from the current clause audio, without altering visuals.

Word times are independently estimated by Faster-Whisper, not exact phoneme
boundaries. Clause windows remain the measured source PCM sample windows.
"""
import re
from pathlib import Path


def aligned_words(meta, model):
    words=[];beats=[]
    for c in meta['clauses']:
        segments,_=model.transcribe(str(Path('assets/clause-voice')/f"clause_{c['clause_id']}.wav"),language='en',word_timestamps=True,beam_size=5,vad_filter=False)
        clause_words=[]
        for segment in segments:
            for w in segment.words or []:
                token=w.word.strip()
                if not token:continue
                start=max(c['start_sec'],min(c['end_sec'],c['start_sec']+w.start))
                end=max(start,min(c['end_sec'],c['start_sec']+w.end))
                item={'word':token,'start_ms':round(start*1000),'end_ms':round(end*1000),'word_id':len(words),'clause_id':c['clause_id']}
                words.append(item);clause_words.append(item)
        if not clause_words:raise ValueError(f'No speech alignment for clause {c["clause_id"]}')
        beats.append({'index':c['clause_id'],'start':c['start_sec'],'end':c['end_sec'], 'words':[x['word'] for x in clause_words],'word_ids':[x['word_id'] for x in clause_words]})
    return words,beats


def compile_times(meta, words):
    def find(clause,variants):
        for w in words:
            normalized=re.sub(r'[^a-z0-9]','',w['word'].lower())
            if w['clause_id']==clause and (normalized in variants or any(normalized.startswith(v) for v in variants)):
                # A modest delay relative to the estimator reduces early reveals,
                # but is not a guarantee of acoustic onset accuracy.
                return min(meta['clauses'][clause]['end_sec'],w['start_ms']/1000+.10)
        raise ValueError(f'Missing required cue {variants} in clause {clause}')
    cues={'states':find(1,('states',)), 'gold':find(2,('gold',)), 'digital':find(3,('digital',)), 'currency':find(4,('currency',)), 'stat':find(5,('88','eighty'))}
    if list(cues.values())!=sorted(cues.values()):raise ValueError('Word cues out of order')
    duration=meta['frames']/60
    times=[0,cues['states']+.18,cues['gold']+.25,cues['currency']+.20,cues['currency']+1.05,cues['stat'],cues['stat']+.5,cues['stat']+1.0,max(cues['stat']+1.25,duration-.6)]
    return cues,times
