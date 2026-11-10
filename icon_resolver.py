"""Offline Iconify name lookup. Name similarity does not establish semantics."""
import difflib,json,re
from functools import lru_cache
from pathlib import Path

SYNONYMS={'microchips':'microchip','microchip':'microchip','chip':'microchip','sand':'grain','silicon':'microchip','chips':'microchip'}
STOP=set('how why what when who where the a an is are was were be been from to of in for with and or into on by built made build making works work your our this that about'.split())

@lru_cache(maxsize=1)
def libraries():
    result={}
    for name in ('lucide','mdi'):
        p=Path('node_modules/@iconify-json')/name/'icons.json'
        if not p.exists():raise RuntimeError('Iconify data missing: run npm ci')
        result[name]=json.loads(p.read_text())
    return result

def icon_body(identifier):
    prefix,pack,name=identifier.split(':',2)
    if prefix!='iconify' or pack not in libraries():raise ValueError('Unsupported Iconify identifier')
    lib=libraries()[pack];entry=lib['icons'].get(name);alias=lib.get('aliases',{}).get(name)
    if entry is None and alias:
        entry=lib['icons'].get(alias.get('parent'))
        if entry is None:raise ValueError('Icon alias parent not found')
    if entry is None:raise ValueError(f'Unknown icon {identifier}')
    # Shapes are taken exclusively from locally installed packages, not user HTML.
    return {'body':entry['body'],'width':entry.get('width',lib.get('width',24)),'height':entry.get('height',lib.get('height',24)), 'alias_transform':alias or {}}

def resolve(noun):
    term=re.sub(r'[^a-z0-9]+','-',noun.casefold()).strip('-')
    if not term:return None
    original=term;term=SYNONYMS.get(term,term)
    variants=[term,term[:-1] if term.endswith('s') else term]
    for v in variants:
        for pack,lib in libraries().items():
            if v in lib['icons'] or v in lib.get('aliases',{}):return {'id':f'iconify:{pack}:{v}','match':'synonym' if original!=term else ('exact-name' if v==term else 'singular-name'),'query':noun}
    # Conservative lexical similarity; callers must review semantic appropriateness.
    choices=[]
    for pack,lib in libraries().items():
        matches=difflib.get_close_matches(term,list(lib['icons'])+list(lib.get('aliases',{})),n=1,cutoff=.88)
        if matches:choices.append((difflib.SequenceMatcher(None,term,matches[0]).ratio(),pack,matches[0]))
    if choices:
        _,pack,name=max(choices);return {'id':f'iconify:{pack}:{name}','match':'lexical-approximation','query':noun}
    return None

def topic_actors(topic):
    tokens=[x.lower() for x in re.findall(r'[A-Za-z][A-Za-z0-9-]*',topic) if x.lower() not in STOP]
    found=[]
    for token in tokens:
        r=resolve(token)
        if r and all(q['id']!=r['id'] for q in found):found.append(r)
        if len(found)==2:break
    while len(found)<2:found.append({'id':'iconify:lucide:circle-help','match':'unresolved','query':tokens[len(found)] if len(tokens)>len(found) else topic})
    return found
