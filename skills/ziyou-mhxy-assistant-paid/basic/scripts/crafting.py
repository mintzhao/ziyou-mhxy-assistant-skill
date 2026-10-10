#!/usr/bin/env python3
"""Bounded, offline, manual 玄灵珠 inventory planning. No game or network access.

Success traces are conditional mathematical projections, never execution logs.
A session stores only source inputs/events and derives its current state on read.
"""
from __future__ import annotations
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

CONFIG_SCHEMA = 'mhxy-crafting-config/v1'
SESSION_SCHEMA = 'mhxy-crafting-session/v1'
MAX_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 10000
MAX_ACTIONS = 5000
RECIPES = {2:(1,1,1), 3:(2,2,2), 4:(3,3,3), 5:(4,4,4,2),
           6:(5,5,5,3), 7:(6,6,6,4), 8:(7,7,7,5)}
WEIGHTS = {1:1}
for _g in range(2,9): WEIGHTS[_g] = sum(WEIGHTS[x] for x in RECIPES[_g])
CHECKS = {
    'current_recipes_match': '当前普通电脑版时间服、目标各级材料与列出的同效果配方一致',
    'compatible_inputs': '清单内均为本次可用的同效果散珠，等级/转移锁/材料资格已核对',
    'usable_capacity': '容量只算本流程实际可读取的格子，已扣无关物品；不是未核对的道具加行囊总格',
    'one_bead_per_cell_safe': '按每珠一格计算足以覆盖实际占格，不依赖堆叠腾空间',
    'one_output_cell_sufficient': '除现有材料外预留一格足够，无额外占格产物或要求；选中材料不腾格',
    'manual_access': '玩家可在不改变这份库存/容量的条件下手工取得缺料并合成；未默认仓库或商人旁窗口可用',
}
SOURCES = [
    {'id':'official-launch','url':'https://xyq.163.com/2024/hjzlp/',
     'published_on':'2023-12-12','checked_on':'2026-10-07',
     'scope':'官方历史基础关系：3颗同效果，成功升一级；有失败说明；非当前物流验证'},
    {'id':'official-high-grade','url':'https://xyq.163.com/news/20240520/4999_1156134.html',
     'published_on':'2024-05-20','effective_on':'2024-05-21','checked_on':'2026-10-07',
     'scope':'官方4–8级必成及5–8级附加料；完整配方是两份官方说明的组合推导'},
    {'id':'historical-video','url':'https://www.bilibili.com/video/BV1ix4y1U7fE/',
     'published_on':'2024-03-24','checked_on':'2026-10-07',
     'scope':'实际看过2024画面：商人旁购买与合成窗口共存；2026兼容性未知，不充当用户确认'},
]
LIMITS = [
    '只规划一颗散珠；逐级镶嵌不是同一个材料目标。',
    '整份步骤表假设每次成功，仅供条件演示；2/3级当前成功率未知，不保证买料总数、结束次数或费用。',
    '默认分段清单只读，玩家逐次核对游戏结果、到检查点再回报；逐步审计模式每次等待实际完整库存。未知结果不会视为成功。',
    '不操作游戏、不自动购买、不估区价/费用/体力、不依赖仓库、批量按钮或商人旁保留窗口。',
    '容量阻塞只说明此深度优先顺序不通过，不证明所有其他顺序都不可行，也不证明最少往返。',
    '来源标签、时间与摘要只检查一致性，不验证用户陈述真假；摘要不是签名或安全身份认证。',
]


def _guard(obj):
    stack=[(obj,0)]; count=0; chars=0
    while stack:
        v,depth=stack.pop(); count+=1
        if count>250000 or depth>24: raise ValueError('Input structure exceeds bounded limits')
        if isinstance(v,dict):
            if len(v)>10000: raise ValueError('Too many object fields')
            for k,x in v.items():
                if not isinstance(k,str) or len(k)>100: raise ValueError('Object keys must be bounded text')
                chars+=len(k); stack.append((x,depth+1))
        elif isinstance(v,list):
            if len(v)>MAX_EVENTS: raise ValueError('List exceeds limit')
            stack.extend((x,depth+1) for x in v)
        elif isinstance(v,str):
            if len(v)>2000: raise ValueError('Text exceeds limit')
            chars+=len(v)
        elif v is not None and type(v) not in (int,bool): raise ValueError('Only exact JSON integer values supported')
        elif type(v) is int and not -1000000<=v<=1000000: raise ValueError('Integer exceeds limit')
        if chars>MAX_BYTES: raise ValueError('Input text exceeds limit')


def _fields(o, required, optional=()):
    if not isinstance(o,dict) or set(o)-set(required)-set(optional) or set(required)-set(o):
        raise ValueError('Missing or unsupported fields; expected '+','.join(required))


def _int(x,label,lo,hi):
    if type(x) is not int or not lo<=x<=hi: raise ValueError(label+' must be an integer in '+str((lo,hi)))
    return x


def _text(x,label,limit=160):
    if not isinstance(x,str) or not x.strip() or len(x)>limit or any(ord(c)<32 for c in x):
        raise ValueError(label+' must be bounded single-line text')
    return x


def _time(x):
    if not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',x):
        raise ValueError('Timestamp must use exact UTC YYYY-MM-DDTHH:MM:SSZ')
    try: return datetime.strptime(x,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError: raise ValueError('Invalid UTC timestamp') from None


def _inventory(value, capacity, complete=False):
    if complete and (not isinstance(value,dict) or set(value)!={str(i) for i in range(1,9)}):
        raise ValueError('Complete actual inventory requires all eight explicit grade keys, including zeros')
    if not isinstance(value,dict) or any(k not in [str(i) for i in range(1,9)] for k in value):
        raise ValueError('Inventory uses canonical grade keys 1–8 only')
    inv={str(g):_int(value.get(str(g),0),'inventory',0,200) for g in range(1,9)}
    if sum(inv.values())>capacity: raise ValueError('Observed inventory exceeds usable capacity')
    return inv


def _source(s,c,live=False,not_before=None):
    _fields(s,('kind','server','bead_type','observed_at','note'))
    if s['kind'] not in ('user_observation','scenario'): raise ValueError('Unsupported source kind; historical sources cannot confirm current inventory')
    if live and s['kind']!='user_observation': raise ValueError('Actual operations require user_observation, not a scenario')
    if s['server']!=c['server'] or s['bead_type']!=c['bead_type']: raise ValueError('Source server or bead type does not match')
    t=_time(s['observed_at']); _text(s['note'],'source note',500)
    if not_before is not None and t<_time(not_before): raise ValueError('Stale observation precedes latest state')
    return copy.deepcopy(s)


def confirmation_scope(c):
    return {k:c[k] for k in ('ruleset','server','bead_type','target_grade','capacity','acquire_grade')}


def _confirmations(value,c):
    if not isinstance(value,dict) or set(value)-set(CHECKS): raise ValueError('Unsupported confirmation')
    out={}
    for key,item in value.items():
        _fields(item,('status',),('source','scope'))
        if item['status'] not in ('unknown','user_confirmed'): raise ValueError('Confirmation status invalid')
        if item['status']=='user_confirmed':
            if 'source' not in item or 'scope' not in item: raise ValueError('User confirmation needs its attributed source and configuration scope')
            if _digest(item['scope'])!=_digest(confirmation_scope(c)): raise ValueError('Confirmation scope does not match current target/capacity/acquisition context')
            source=_source(item['source'],c,True)
            if _time(source['observed_at'])>_time(c['as_of']): raise ValueError('Confirmation cannot be from the future')
            out[key]={'status':'user_confirmed','source':source,'scope':confirmation_scope(c)}
        else:
            if 'source' in item or 'scope' in item: raise ValueError('Unknown confirmation must not carry a confirmed source')
            out[key]={'status':'unknown'}
    return out


def validate_config(value):
    _guard(value)
    _fields(value,('schema','ruleset','server','bead_type','objective','target_grade','capacity',
                  'as_of','inventory','inventory_source'),('acquire_grade','confirmations'))
    c=copy.deepcopy(value)
    if c['schema']!=CONFIG_SCHEMA or c['ruleset']!='pc_time': raise ValueError('Unsupported schema or ruleset')
    if c['objective']!='loose': raise ValueError('Only one loose bead supported; equipped sequential targets need a separate bill of materials')
    _text(c['server'],'server'); _text(c['bead_type'],'bead_type',40)
    _int(c['target_grade'],'target_grade',2,8); _int(c['capacity'],'capacity',1,200)
    c['acquire_grade']=_int(c.get('acquire_grade',1),'acquire_grade',1,3)
    if c['acquire_grade']>=c['target_grade']: raise ValueError('acquire_grade must be below target_grade')
    _time(c['as_of']); c['inventory_source']=_source(c['inventory_source'],c)
    c['inventory']=_inventory(c['inventory'],c['capacity'],c['inventory_source']['kind']=='user_observation')
    if _time(c['inventory_source']['observed_at'])>_time(c['as_of']): raise ValueError('Inventory observation cannot be from the future')
    c['confirmations']=_confirmations(c.get('confirmations',{}),c)
    return c


def _gate(c):
    missing=[]
    if c['inventory_source']['kind']!='user_observation': missing.append('current_user_inventory')
    if c['inventory_source']['observed_at'][:10]!=c['as_of'][:10]: missing.append('fresh_inventory_observation')
    for key in CHECKS:
        x=c['confirmations'].get(key,{})
        if x.get('status')!='user_confirmed' or x['source']['observed_at'][:10]!=c['as_of'][:10]: missing.append(key)
    return missing


def _weight(inv): return sum(WEIGHTS[int(g)]*n for g,n in inv.items())


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _schedule(c, first_only=False):
    inv=dict(c['inventory']); reserved=Counter(); steps=[]; blocked=None
    class Stop(Exception): pass
    def perform(action,grade):
        nonlocal blocked
        before=dict(inv); used=Counter(RECIPES[grade]) if action=='craft_one' else Counter()
        after=dict(inv)
        for g,n in used.items(): after[str(g)]-=n
        after[str(grade)]+=1
        required=max(sum(before.values()),sum(after.values()))+1
        step={'number':len(steps)+1,'action':action,'grade':grade,
              'consumed':{str(g):n for g,n in sorted(used.items())},
              'inventory_before':before,'inventory_after_if_success':after,
              'occupied_before':sum(before.values()),'occupied_after_if_success':sum(after.values()),
              'reserved_output_cells':1,'required_cells':required,
              'material_weight_before':_weight(before),'material_weight_after_if_success':_weight(after),
              'acquired_weight_if_success':WEIGHTS[grade] if action=='obtain_one' else 0,
              'actual_outcome':'unknown_until_user_observation'}
        if required>c['capacity']:
            blocked={'reason':'capacity_blocked_under_this_order','required_cells':required,
                     'capacity':c['capacity'],'blocked_action':step}
            raise Stop()
        if any(x<0 for x in after.values()): raise AssertionError('Negative simulated inventory')
        if step['material_weight_after_if_success']!=step['material_weight_before']+step['acquired_weight_if_success']:
            raise AssertionError('Conservation failure')
        steps.append(step); inv.update(after)
        if first_only: raise Stop()
        if len(steps)>MAX_ACTIONS: raise ValueError('Schedule exceeds action bound')
    def ensure(g):
        if inv[str(g)]>reserved[g]: return
        if g<=c['acquire_grade']:
            perform('obtain_one',g); return
        for child in RECIPES[g]:
            ensure(child); reserved[child]+=1
        for child in RECIPES[g]: reserved[child]-=1
        perform('craft_one',g)
    try: ensure(c['target_grade'])
    except Stop: pass
    return steps,inv,blocked


def _checkpoints(steps,target):
    """Group a conditional trace for reading; never mark actions as completed."""
    groups=[]; first=0
    for i,step in enumerate(steps):
        before_final=(i+1<len(steps) and steps[i+1]['action']=='craft_one' and steps[i+1]['grade']==target)
        milestone=step['action']=='craft_one' and step['grade']>=max(2,target-1)
        if not (milestone or before_final or i==len(steps)-1): continue
        part=steps[first:i+1]
        if step['action']=='craft_one' and step['grade']==target: purpose='尝试合出目标散珠'
        elif before_final: purpose='补齐最后一次合成材料，保留所有已完成珠'
        elif step['action']=='craft_one': purpose=f"形成并保留一颗{step['grade']}级中间珠"
        else: purpose='核对这段条件材料准备'
        groups.append({'checkpoint':len(groups)+1,'purpose':purpose,'mode':'read_only_conditional',
                       'first_action_number':first+1,'last_action_number':i+1,'logical_actions':len(part),
                       'inventory_before':part[0]['inventory_before'],
                       'inventory_at_checkpoint_if_all_succeed':step['inventory_after_if_success'],
                       'conditional_obtain_counts':{str(g):sum(x['action']=='obtain_one' and x['grade']==g for x in part) for g in range(1,9)},
                       'conditional_craft_counts':{str(g):sum(x['action']=='craft_one' and x['grade']==g for x in part) for g in range(2,9)},
                       'required_cells_if_all_succeed':max(x['required_cells'] for x in part),
                       'stop_on_failure_deviation_or_unknown':True,'actually_completed':False})
        first=i+1
    return groups


def plan(config):
    c=validate_config(config); steps,final,blocked=_schedule(c)
    missing=_gate(c)
    status='already_held' if c['inventory'][str(c['target_grade'])]>0 else ('capacity_blocked_under_this_order' if blocked else 'conditional_success_projection')
    return {'schema':'mhxy-crafting-plan/v1','status':status,'current_inventory':c['inventory'],
            'source_attribution':{'inventory':c['inventory_source'],'user_confirmations':c['confirmations'],
                                  'published_evidence':copy.deepcopy(SOURCES)},
            'execution_gate':'illustrative_only' if missing else 'one_manual_step_after_current_operation_check',
            'missing_checks':missing,'minimal_checks':[
                '确认实际可用容量和现有同效果各级散珠，其他物品占格已扣；只先补会改变下一步的信息。',
                '在当前界面核对下一步材料、可用性和占格；若要用商人旁窗口，另确认它现在确实可用。'],
            'server':c['server'],'bead_type':c['bead_type'],'as_of':c['as_of'],
            'target_grade':c['target_grade'],'capacity':c['capacity'],'acquire_grade':c['acquire_grade'],
            'conditional_actions':steps,'read_only_checkpoints':_checkpoints(steps,c['target_grade']),
            'checkpoint_policy':'Read-only groups do not advance the session. Locally check every game result; stop on any failure, deviation or uncertainty. At a chosen checkpoint supply complete actual inventory via refresh. No need for one chat reply per logical action.',
            'conditional_final_inventory':final,'capacity_blocker':blocked,
            'conditional_peak_occupied_cells':max([sum(c['inventory'].values())]+[s['occupied_after_if_success'] for s in steps]),
            'conditional_peak_with_reserve':max([sum(c['inventory'].values())+1]+[s['required_cells'] for s in steps]),
            'conditional_obtain_counts':{str(g):sum(s['action']=='obtain_one' and s['grade']==g for s in steps) for g in range(1,9)},
            'conditional_craft_counts':{str(g):sum(s['action']=='craft_one' and s['grade']==g for s in steps) for g in range(2,9)},
            'counts_scope':'success_path_only' if not blocked else 'feasible_prefix_only',
            'guaranteed_purchase_total':None,'success_probability':None,'fees':None,'stamina':None,'minimum_trips':None,
            'next_action':copy.deepcopy(steps[0]) if steps and not blocked and not missing else None,
            'illustrative_first_action':copy.deepcopy(steps[0]) if steps and not blocked else None,
            'conditions':list(LIMITS)}


def start(config):
    return {'schema':SESSION_SCHEMA,'initial':validate_config(config),'events':[]}


def _token(c,revision,pending,paused):
    return _digest({'config':c,'revision':revision,'pending':pending,'paused':paused})


def _apply(c,pending,paused,event,revision,full_path_fits):
    kind=event.get('kind') if isinstance(event,dict) else None
    if kind=='begin':
        _fields(event,('kind','plan_token','manual_check'))
        if event['plan_token']!=_token(c,revision,pending,paused): raise ValueError('Stale or mismatched plan token')
        if pending is not None or paused: raise ValueError('Pending or paused operation must be reconciled first')
        if _gate(c): raise ValueError('Unconfirmed conditions: illustrative plan cannot start an actual operation')
        if not full_path_fits: raise ValueError('Complete conditional path is capacity-blocked; do not spend into the prefix')
        check=_source(event['manual_check'],c,True,c['as_of'])
        if check['observed_at'][:10]!=c['as_of'][:10]: raise ValueError('New day requires fresh inventory and confirmations')
        actions,_,blocked=_schedule(c,first_only=True)
        if blocked or not actions: raise ValueError('No capacity-feasible next action')
        pending=actions[0]; c['as_of']=check['observed_at']
        return c,pending,False,'awaiting_actual_inventory'
    if kind=='reconcile':
        _fields(event,('kind','observation'))
        if pending is None: raise ValueError('No pending operation to reconcile')
        o=event['observation']; _fields(o,('outcome','source'),('inventory',))
        source=_source(o['source'],c,True,c['as_of'])
        if o['outcome']=='unknown':
            if o.get('inventory') is not None: raise ValueError('Unknown outcome must not apply a partial or assumed inventory')
            c['as_of']=source['observed_at']
            return c,pending,paused,'waiting_for_observation'
        if o['outcome'] not in ('success','failure'): raise ValueError('Unsupported outcome')
        if 'inventory' not in o: raise ValueError('Complete observed inventory required')
        observed=_inventory(o['inventory'],c['capacity'],True); before=c['inventory']
        classification='unexpected_outcome'; should_pause=True
        if o['outcome']=='success' and observed==pending['inventory_after_if_success']:
            classification='observed_success'; should_pause=False
        elif o['outcome']=='failure' and pending['action']=='obtain_one' and observed==before:
            classification='observed_no_acquisition'; should_pause=False
        elif o['outcome']=='failure' and pending['action']=='craft_one' and pending['grade'] in (2,3):
            lost_grade=pending['grade']-1; expected=dict(before); expected[str(lost_grade)]-=1
            if observed==expected:
                classification='observed_one_lost_two_survived'; should_pause=False
        c['inventory']=observed; c['inventory_source']=source; c['as_of']=source['observed_at']
        if should_pause: c['confirmations']={}
        return c,None,should_pause,classification
    if kind=='refresh':
        _fields(event,('kind','observation','resolve_pending'),('confirmations',))
        if type(event['resolve_pending']) is not bool: raise ValueError('resolve_pending must be boolean')
        if pending is not None and not event['resolve_pending']: raise ValueError('Refresh must explicitly resolve the pending operation from a complete current observation')
        o=event['observation']; _fields(o,('inventory','source'))
        source=_source(o['source'],c,True,c['as_of'])
        c['inventory']=_inventory(o['inventory'],c['capacity'],True); c['inventory_source']=source; c['as_of']=source['observed_at']
        c['confirmations']=_confirmations(event.get('confirmations',{}),c)
        return c,None,False,'refreshed_from_actual_inventory'
    raise ValueError('Unsupported event kind')


def _replay(session):
    _guard(session); _fields(session,('schema','initial','events'))
    if session['schema']!=SESSION_SCHEMA or not isinstance(session['events'],list) or len(session['events'])>MAX_EVENTS:
        raise ValueError('Unsupported session or event limit')
    c=validate_config(session['initial']); pending=None; paused=False; last='started'
    feasibility_cache={}
    def full_fits():
        # Reuse only arithmetic for an identical inventory and immutable scope.
        # Every event still passes _apply validation, including fresh sources,
        # pending-state resolution, timestamps and confirmation expiry.
        key=tuple(c[k] for k in ('ruleset','server','bead_type','target_grade','capacity','acquire_grade'))+tuple(c['inventory'][str(g)] for g in range(1,9))
        if key not in feasibility_cache: feasibility_cache[key]=_schedule(c)[2] is None
        return feasibility_cache[key]
    full_path_fits=full_fits()
    for revision,event in enumerate(session['events']):
        c,pending,paused,last=_apply(c,pending,paused,event,revision,full_path_fits)
        if event['kind']=='refresh' or last=='observed_one_lost_two_survived':
            full_path_fits=full_fits()
        # Rebuilding an initially owned intermediate may require more capacity
        # than the original success-only projection, so recheck every loss.
        # Expected successes preserve the previously checked path.
    return c,pending,paused,last,full_path_fits


def inspect(session):
    c,pending,paused,last,_=_replay(session); projection=plan(c); revision=len(session['events'])
    status='paused_unexpected_outcome' if paused else ('awaiting_actual_inventory' if pending else projection['status'])
    next_action=None if (pending or paused or _gate(c)) else projection['next_action']
    return {'schema':'mhxy-crafting-inspection/v1','revision':revision,'status':status,'last_event_result':last,
            'plan_token':_token(c,revision,pending,paused),'current_inventory':dict(c['inventory']),
            'pending':pending,'next_action':next_action,'plan':projection}


def _append(session,expected_revision,event):
    c,pending,paused,_,full_path_fits=_replay(session)
    _int(expected_revision,'expected_revision',0,MAX_EVENTS)
    if expected_revision!=len(session['events']): raise ValueError('Stale revision')
    if expected_revision>=MAX_EVENTS: raise ValueError('Event limit reached; archive and create a fresh observed session')
    _guard(event); _apply(c,pending,paused,event,expected_revision,full_path_fits)
    result=copy.deepcopy(session); result['events'].append(copy.deepcopy(event)); _guard(result)
    # Bound the pretty-printed persisted form too, so a returned session can be
    # reopened by the CLI under the same file-size limit. Never truncate events.
    if len(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode())+1>MAX_BYTES:
        raise ValueError('Session file limit reached; archive and create a fresh observed session')
    return result


def begin(session,expected_revision,plan_token,manual_check):
    """Record a user-checked, about-to-be-attempted action; never execute it."""
    return _append(session,expected_revision,{'kind':'begin','plan_token':plan_token,'manual_check':manual_check})


def reconcile(session,expected_revision,observation):
    return _append(session,expected_revision,{'kind':'reconcile','observation':observation})


def refresh(session,expected_revision,observation,confirmations=None,resolve_pending=False):
    e={'kind':'refresh','observation':observation,'resolve_pending':resolve_pending}
    if confirmations is not None: e['confirmations']=confirmations
    return _append(session,expected_revision,e)


def _inventory_text(inv):
    return '、'.join(f'{g}级×{n}' for g,n in inv.items() if n) or '无珠'


def _recipe_ladder_lines(r):
    lines=['配方阶梯（只用于同效果、当前界面资格已确认的散珠）：',
           '每次先逐个做完并保留三个基础子材料，再补该级附加珠，最后合一次；已有可用材料可抵用，不必重做。']
    if r['acquire_grade']>1:
        lines.append(f"本计划把缺少的{r['acquire_grade']}级及以下材料列为手工取得，不展开这些低阶合成，也不假定商人有售。")
    for g in range(2,r['target_grade']+1):
        if g<=r['acquire_grade']:
            lines.append(f"{g}级：本计划直接取得，不在本路线内合成。")
            continue
        base=f"{g}级：先逐个备好并保留3颗{g-1}级"
        extra=f"，再补1颗{g-3}级附加珠" if g>=5 else ''
        lines.append(base+extra+f" → 尝试合出1颗{g}级。")
    if r['acquire_grade']<3:
        lines.append('2/3级当前是否必成及失败消耗仍未知；逐次看实际产物，任何失败、数量偏差或结果不明立即停段，按完整实际库存重算。')
    else:
        lines.append('本路线不推算取得低阶珠之前的合成成功率、失败损耗或一级采购总数。')
    lines.extend([
        '依据：官方2023-12-12基础关系与2024-05-21高阶调整组合推导；4–8级必成是该历史公告的规则，仍须核对当前界面。读取核验2026-10-07，不是当前实机验证。',
        '基础规则：https://xyq.163.com/2024/hjzlp/；高阶及附加料：https://xyq.163.com/news/20240520/4999_1156134.html',
        '保留规则：已为同一上层做好的兄弟珠不要拿去别处消耗；附加珠按上述顺序补齐，不能漏。做6级时保留三个5级，再补最后的3级附加珠。' if r['target_grade']>=6 else '保留规则：已为同一上层做好的兄弟珠不要拿去别处消耗；若该级有附加珠，按上述顺序补齐，不能漏。',
        '格子规则：始终另留1个输出格；选中材料仍按占格算。只补下一次缺料，不要一次买齐本段总量，不能以堆叠或仓库代替尚未确认的容量。',
    ])
    return lines


def render(result,detail='checkpoints'):
    if detail not in ('checkpoints','steps'): raise ValueError('Unsupported report detail')
    r=result['plan'] if result.get('schema')=='mhxy-crafting-inspection/v1' else result
    status_labels={'already_held':'已持有目标散珠','conditional_success_projection':'条件成功路径',
                   'capacity_blocked_under_this_order':'此顺序容量不足','paused_unexpected_outcome':'实际结果异常，已暂停',
                   'awaiting_actual_inventory':'等待实际完整库存'}
    gate_label='只供条件演示' if r['execution_gate']=='illustrative_only' else '模型条件已确认；逐步审计模式才逐次记一步，分段清单仍只读'
    status=result.get('status',r['status'])
    source=r['source_attribution']['inventory']
    source_label='场景示例' if source['kind']=='scenario' else '用户报告的实际观察（未独立实机验证）'
    check_labels=dict(CHECKS,current_user_inventory='需要用户实际库存观察',fresh_inventory_observation='需要本核对日的新库存观察')
    lines=['玄灵珠手工安排（条件模型，不是当前游戏保证）',
           f"区服：{r['server']}；效果：{r['bead_type']}；核对时点：{r['as_of']}",
           f"库存来源：{source_label}，{source['observed_at']}；{source['note']}",
           f"目标：一颗{r['target_grade']}级散珠；可用容量{r['capacity']}格；库存：{_inventory_text(r['current_inventory'])}",
           f"状态：{status_labels.get(status,status)}；来源门槛：{gate_label}",
           f"条件成功路径峰值：{r['conditional_peak_occupied_cells']}颗珠 + 1输出预留 = {r['conditional_peak_with_reserve']}格",
           '上述容量含保留的中间珠；材料选中不扣占格。不保证低阶必成、总采购量、总价或往返数。']
    lines.append('条件成功路径的取得数量：'+_inventory_text(r['conditional_obtain_counts'])+'；这些不是保证采购数，未计失败损耗。')
    if r['counts_scope']=='feasible_prefix_only': lines.append('注意：这里的数量和峰值仅统计阻塞前的可行前缀，不是完成目标的总数。')
    if r['missing_checks']: lines.append('待确认：'+'；'.join(check_labels.get(x,x) for x in r['missing_checks']))
    if result.get('pending'): lines.append('已有手工动作待观察：暂停，先提供各级完整剩余库存；不要按后续演示继续。')
    if result.get('status')=='paused_unexpected_outcome': lines.append('实际结果与本分支不符，已经暂停；新库存已保留，重新核对条件后再继续。')
    if r['capacity_blocker']: lines.append('此顺序在条件演示中容量不足，步骤仅为可行前缀；不建议按前缀先花费。')
    lines.append('默认按小段看清单，不必每次取得/合成都发一条聊天确认；逐步事件记录是可选审计模式。')
    lines.append('玩家在游戏里逐次核对结果；任何失败、库存不同或结果不明都立即停段。到选定检查点再报告完整实际库存，用refresh重算；下列预计库存不会写成实际。')
    lines.append('做法：需要某级材料时，有可用库存就保留；否则先逐个完成它的子材料再合一次。每次只补眼前缺料，绝不能一次买齐本段取得总数。')
    lines.extend(_recipe_ladder_lines(r))
    if detail=='checkpoints':
        lines.append('分段只读清单（全段成功才有下面的预计库存；非批量按钮、非自动执行）：')
        for g in r['read_only_checkpoints']:
            lines.append(f"{g['checkpoint']}. {g['purpose']}。条件取得 {_inventory_text(g['conditional_obtain_counts'])}；合成次数 {_inventory_text(g['conditional_craft_counts'])}。检查点预计剩 {_inventory_text(g['inventory_at_checkpoint_if_all_succeed'])}；本段含预留峰值{g['required_cells_if_all_succeed']}格，对应审计步骤{g['first_action_number']}–{g['last_action_number']}。")
        lines.append('要看每一步前后库存和守恒，使用--detail steps；分段不减少实际游戏购买/点击次数，不承诺更少操作。')
    else:
        lines.append('条件演示细步骤（每行都假设此前动作成功；任何偏差停止，不能按后续预计库存继续）：')
        for s in r['conditional_actions']:
            action=f"手工取得1颗{s['grade']}级" if s['action']=='obtain_one' else f"手工尝试合{s['grade']}级，投入{_inventory_text(s['consumed'])}"
            lines.append(f"{s['number']}. {action}；若成功剩 {_inventory_text(s['inventory_after_if_success'])}；占{s['occupied_after_if_success']}格，本步含预留需{s['required_cells']}格；材料权重{s['material_weight_before']}→{s['material_weight_after_if_success']}")
    lines.extend(['未知：手续费、商人价格/库存、体力、低阶成功概率。材料权重仅为配方等价值，不是价格。']+r['conditions'])
    lines.extend('来源：'+x['url']+'（'+x['scope']+'；读取核验'+x['checked_on']+'）' for x in SOURCES)
    return '\n'.join(lines)+'\n'


def _no_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValueError('Duplicate JSON key')
        out[k]=v
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path); p.add_argument('--kind',choices=('plan','start','inspect','begin','reconcile','refresh'),default='plan')
    p.add_argument('--format',choices=('json','text'),default='json'); p.add_argument('--output',type=Path)
    p.add_argument('--detail',choices=('checkpoints','steps'),default='checkpoints',help='Text report detail; checkpoint groups never advance actual state')
    args=p.parse_args()
    try:
        if not stat.S_ISREG(args.input.stat().st_mode) or args.input.stat().st_size>MAX_BYTES: raise ValueError('Input must be a bounded regular file')
        with args.input.open('r',encoding='utf-8') as f: raw=f.read(MAX_BYTES+1)
        if len(raw.encode())>MAX_BYTES: raise ValueError('Input exceeds byte limit')
        value=json.loads(raw,object_pairs_hook=_no_duplicates,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
        _guard(value)
        if args.kind=='plan': result=plan(value)
        elif args.kind=='start': result=start(value)
        elif args.kind=='inspect': result=inspect(value)
        else:
            required=('session','expected_revision')
            if args.kind=='begin':
                _fields(value,required+('plan_token','manual_check')); result=begin(**value)
            elif args.kind=='reconcile':
                _fields(value,required+('observation',)); result=reconcile(**value)
            else:
                _fields(value,required+('observation',),('confirmations','resolve_pending')); result=refresh(**value)
        if args.format=='text':
            report=inspect(result) if result.get('schema')==SESSION_SCHEMA else result
            out=render(report,args.detail)
        else: out=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream: stream.write(out)
        else: sys.stdout.write(out)
    except (OSError,ValueError,TypeError,RecursionError) as e: p.error(str(e))
    return 0


if __name__=='__main__': raise SystemExit(main())
