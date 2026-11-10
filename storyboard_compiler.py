"""Data-driven, fail-closed literal storyboard validation and sample planning."""
import json, math, re
from pathlib import Path

ACTORS={'dollar','gold','vault','globe','coin','document','server','scale','person','prompt','network','token','error','database','calculator'}
ACTIONS={'connect','sever','hold','flow','exchange','compare','write','spin','reveal'}
TOKEN=re.compile(r"[\w]+(?:['’-][\w]+)*",re.UNICODE)
def canonical(s):return [v.casefold().replace('’',"'") for v in TOKEN.findall(s)]

def validate_plan(plan):
    beats=plan.get('beats')
    if not isinstance(beats,list) or not beats:raise ValueError('storyboard must have a nonempty beats array')
    for i,b in enumerate(beats):
        if not isinstance(b,dict):raise ValueError(f'beat {i}: expected object')
        text=b.get('spoken_text','');trigger=b.get('trigger_word','');actors=b.get('visual_actors',[])
        if not text or len(canonical(trigger))!=1 or canonical(trigger)[0] not in canonical(text):raise ValueError(f'beat {i}: trigger_word must be one actual spoken word')
        if not isinstance(actors,list) or len(actors)!=2 or any(a not in ACTORS for a in actors):raise ValueError(f'beat {i}: unsupported or missing concrete actors: {actors}')
        if b.get('action') not in ACTIONS:raise ValueError(f'beat {i}: unsupported action {b.get("action")}')
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
    else:raise ValueError('No automatic planner is configured for this topic. Provide --storyboard with explicit beats; unsupported topics are not replaced by generic visuals.')
    plan=json.loads(Path(f'storyboard_examples/{example}.json').read_text());n=max(1,round(duration/3))
    if n>len(plan['beats']):raise ValueError(f'The built-in example has {len(plan["beats"])} unique beats; supply --storyboard for longer content')
    plan['beats']=plan['beats'][:n];validate_plan(plan)
    return {**plan,'topic':topic,'requested_duration':duration,'plan_source':f'built-in example: {example}'}
