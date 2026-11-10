"""Data-driven, fail-closed literal storyboard validation and sample planning."""
import json, math, re
from pathlib import Path
from icon_resolver import icon_body,topic_actors

ACTORS={'dollar','gold','vault','globe','coin','document','server','scale','person','prompt','network','token','error','database','calculator'}
ACTIONS={'connect','sever','hold','flow','exchange','compare','write','spin','reveal'}
RIGS={'editorial-strike','vault-unlock','sever-link','probability-wheel','ledger-cascade','network-hub','dominance-ring','bento-compare','multiply-press','split-paradox'}
TOKEN=re.compile(r"[\w]+(?:['’-][\w]+)*",re.UNICODE)
def canonical(s):return [v.casefold().replace('’',"'") for v in TOKEN.findall(s)]


def valid_icon(identifier):
    if not identifier.startswith('iconify:'):return False
    try:icon_body(identifier);return True
    except ValueError:return False

def validate_plan(plan):
    beats=plan.get('beats')
    if not isinstance(beats,list) or not beats:raise ValueError('storyboard must have a nonempty beats array')
    for i,b in enumerate(beats):
        if not isinstance(b,dict):raise ValueError(f'beat {i}: expected object')
        text=b.get('spoken_text','');trigger=b.get('trigger_word','');actors=b.get('visual_actors',[])
        if not text or len(canonical(trigger))!=1 or canonical(trigger)[0] not in canonical(text):raise ValueError(f'beat {i}: trigger_word must be one actual spoken word')
        if not isinstance(actors,list) or len(actors)!=2 or any(not isinstance(a,str) or (a not in ACTORS and not valid_icon(a)) for a in actors):raise ValueError(f'beat {i}: unsupported or missing concrete actors: {actors}')
        if b.get('action') not in ACTIONS:raise ValueError(f'beat {i}: unsupported action {b.get("action")}')
        if b.get('rig') and b['rig'] not in RIGS:raise ValueError(f'beat {i}: unsupported rig')
        if b.get('rig')=='dominance-ring' and not (isinstance(b.get('value'),int) and 0<=b['value']<=100):raise ValueError(f'beat {i}: dominance-ring requires an explicit value from 0 to 100')
        if b.get('mood') not in ('archival','digital'):raise ValueError(f'beat {i}: mood must be archival or digital')
    return plan


def load_plan(topic,duration,plan_path=None):
    if not topic.strip() or not math.isfinite(duration) or duration<=0:raise ValueError('topic and positive finite duration are required')
    if plan_path:
        plan=json.loads(Path(plan_path).read_text());validate_plan(plan)
        return {**plan,'topic':topic,'requested_duration':duration,'plan_source':str(plan_path)}
    t=topic.casefold()
    if t.strip()=='why the us dollar is the king of global finance':example='dollar'
    elif t.strip()=='why your ai gives you wrong answers':example='ai'
    else:return generic_plan(topic,duration)
    plan=json.loads(Path(f'storyboard_examples/{example}.json').read_text());n=max(1,round(duration/3))
    if n>len(plan['beats']):raise ValueError(f'The built-in example has {len(plan["beats"])} unique beats; supply --storyboard for longer content')
    plan['beats']=plan['beats'][:n];validate_plan(plan)
    return {**plan,'topic':topic,'requested_duration':duration,'plan_source':f'built-in example: {example}'}


def generic_plan(topic,duration):
    # A transparent, non-factual overview, not an LLM-written documentary.
    # Use reviewed input for meaningful claims and subject/verb semantics.
    subject=' '.join(topic.split())[:120].strip(' .!?') or 'this subject'
    subject=subject[:1].lower()+subject[1:]
    matches=topic_actors(subject);actors=[m['id'] for m in matches];n=max(1,round(duration/3))
    templates=[('Let us explore the topic.', 'explore','reveal'),('We examine its parts.', 'examine','compare'),('We compare the main elements.', 'compare','compare'),('We consider their connection.', 'consider','connect'),('This overview invites further questions.', 'invites','reveal')]
    beats=[]
    for i in range(n):
        text,trigger,action=templates[i%len(templates)]
        if i==0:
            candidates=('explore','examine','investigate','consider','review','discuss');used=set(canonical(subject));trigger=next((v for v in candidates if v not in used),'explore');text=f'We {trigger} {subject}.'
        beats.append({'spoken_text':text,'trigger_word':trigger,'visual_actors':actors,'action':action,'mood':'digital','semantic_review_required':True})
    plan={'topic':topic,'requested_duration':duration,'beats':beats,'plan_source':'automatic non-factual overview; editorial review required','icon_matches':matches,'semantic_review_required':True}
    return validate_plan(plan)
