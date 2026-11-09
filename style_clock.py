"""Map the locked narration's estimated word times to an authored GSAP clock."""
import re

def compile_visual_marks(meta):
    words=meta['words']
    def find(token,occurrence=0):
        found=[w for w in words if re.sub(r'[^a-z0-9%]','',w['word'].lower())==token]
        if len(found)<=occurrence:raise ValueError(f'Locked narration has no {token} occurrence {occurrence+1}')
        return found[occurrence]['start_ms']/1000
    # These are only words actually in the existing voiceover. There is no
    # recorded 'rewrote', 'digital' or 'today' word to use as a cue.
    specs=[('opening',0),('states',find('states')),('gold',find('gold')),
           ('2022',find('2022')),('dollar',find('dollar',1)),('88',find('88')),
           ('foreign',find('foreign')),('exchange',find('exchange')),
           ('trades',find('trades')),('end',meta['duration'])]
    marks=[{'name':name,'real':real,'virtual':i*2} for i,(name,real) in enumerate(specs)]
    if any(a['real']>=b['real'] for a,b in zip(marks,marks[1:])):raise ValueError('Narration markers must increase')
    return marks

def remap(t,marks):
    if t<=marks[0]['real']:return marks[0]['virtual']
    for a,b in zip(marks,marks[1:]):
        if t<=b['real']:
            fraction=(t-a['real'])/(b['real']-a['real'])
            return a['virtual']+fraction*(b['virtual']-a['virtual'])
    return marks[-1]['virtual']
