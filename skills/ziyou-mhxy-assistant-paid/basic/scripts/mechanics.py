#!/usr/bin/env python3
"""Bounded official-fact mechanics and user-quoted guild resource accounting.

No full combat simulator or market estimator. See current-game-decisions.md.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
try:
    from . import decisions as d, resources, grounded, scene_leveling as scene_module
except ImportError:
    import decisions as d
    import resources, grounded, scene_leveling as scene_module

CHECKED='2026-10-06'

def scope(data):
    if data['ruleset']!='pc_time':raise ValueError('ruleset must be pc_time; this ruleset does not apply to other game editions')

def intv(value,label,low=0,high=1000000):return resources._integer(value,label,low,high)


@d.exact_calculation
def focus(data):
    d.fields(data,('ruleset','casts','period','cost_basis'),('cost_context','paid_mana_quote','extra_purchase_quote'))
    scope(data);d.text(data['period'],'period');d.text(data['cost_basis'],'cost basis')
    mana=Decimal(0)
    for row in d.rows(data['casts'],'casts'):
        d.fields(row,('label','count','effective_mana_cost','eligibility'))
        d.text(row['label'],'spell label');count=intv(row['count'],'cast count')
        cost=d.num(row['effective_mana_cost'],'effective MP cost')
        if row['eligibility']!='confirmed':raise ValueError('Expected focus savings need confirmed eligible battle spell casts')
        mana+=count*cost
    saved=mana*Decimal('0.15')
    ctx=None if data.get('cost_context') is None else d.context(data['cost_context'])
    if (data.get('paid_mana_quote') is not None or data.get('extra_purchase_quote') is not None) and ctx is None:raise ValueError('Money estimates require cost_context and attributed quotes')
    paidq=None if data.get('paid_mana_quote') is None else d.quote(data['paid_mana_quote'],ctx,'marginal mana price')
    premiumq=None if data.get('extra_purchase_quote') is None else d.quote(data['extra_purchase_quote'],ctx,'extra purchase cost')
    paid=None if paidq is None else paidq['amount'];premium=None if premiumq is None else premiumq['amount']
    cash=None if paid is None else saved*paid
    return {'calculator':'focus_expectation','period':data['period'],'baseline_eligible_mp':d.fmt(mana),
            'expected_mp_saved':d.fmt(saved),'expected_mp_spent':d.fmt(mana-saved),
            'expected_cash_saved_if_marginal_cost_model_holds':d.fmt(cash),
            'extra_purchase_cost':d.fmt(premium),'expected_break_even_periods':None if premium is None or cash is None else d.ratio(premium,cash),
            'cost_basis':data['cost_basis'],'cost_context':data.get('cost_context'),'paid_mana_quote':d.quote_output(paidq),'extra_purchase_quote':d.quote_output(premiumq),'quotes_stale':any(q and q['stale'] for q in (paidq,premiumq)),'citations':[{'url':'https://xyq.163.com/introduce/jn002.html','checked_date':CHECKED}],
            'interpretation':'专注15%施法免魔的数学期望；不是每战固定省15%，不改变战意/愤怒消耗',
            'limits':['输入仅含确认为专注可适用的战斗施法，耗蓝须已计实际加成/减免',
                      'paid_mana_quote是实际可减少的边际补蓝成本；免费恢复、药品溢出或消费频次不变时不能直接套药价/恢复量',
                      '回本只是给定工作量与边际成本下的期望，不保证任何一天回本；未计属性/套装损失、维护与残值',
                      '专注与神农不能同时出现；低于标称耗蓝能否施法等边界未核实']}


@d.exact_calculation
def guild_skill(data):
    d.fields(data,('ruleset','skill','current_level','target_level','steps','source','guild_fee_index','context'),('starting_contribution',))
    scope(data);d.text(data['skill'],'skill');d.text(data['source'],'quote source');ctx=d.context(data['context'])
    if ctx['currency']!='两':raise ValueError('Guild skill costs use 两')
    start=intv(data['current_level'],'current level',0,200);target=intv(data['target_level'],'target level',start,200)
    index=d.num(data['guild_fee_index'],'guild fee index')
    steps=d.rows(data['steps'],'steps')
    if len(steps)!=target-start:raise ValueError('One explicit step per target level is required')
    totals={k:Decimal(0) for k in ('experience','money_liang','contribution_spent','materials')}
    known={k:True for k in totals};prior=Decimal(0);required_stock=Decimal(0);stock_known=True;clean=[]
    for level,row in zip(range(start+1,target+1),steps):
        d.fields(row,('target_level','experience','money_liang','contribution_spent','contribution_gate','materials'))
        if intv(row['target_level'],'step level',1,200)!=level:raise ValueError('Step levels must be complete, ordered and consecutive')
        normalized={'target_level':str(level)}
        for key in totals:
            value=None if row[key] is None else d.num(row[key],key)
            normalized[key]=d.fmt(value)
            if value is None:known[key]=False
            else:totals[key]+=value
        gate=None if row['contribution_gate'] is None else d.num(row['contribution_gate'],'contribution gate')
        normalized['contribution_gate']=d.fmt(gate)
        if gate is None:stock_known=False
        elif stock_known:required_stock=max(required_stock,prior+gate)
        # A known debit also requires that stock exists; gate might be lower than debit.
        debit=None if row['contribution_spent'] is None else d.num(row['contribution_spent'],'contribution spent')
        if debit is None:stock_known=False
        else:
            prior+=debit
            if stock_known:required_stock=max(required_stock,prior)
        clean.append(normalized)
    starting=None if data.get('starting_contribution') is None else d.num(data['starting_contribution'],'starting contribution')
    return {'calculator':'guild_skill_quote_budget','skill':data['skill'],'current_level':str(start),'target_level':str(target),
            'totals':{k:d.fmt(v) if known[k] else None for k,v in totals.items()},
            'known_subtotals':{k:d.fmt(v) for k,v in totals.items()},'incomplete_columns':[k for k in totals if not known[k]],
            'minimum_starting_contribution_without_earning_more':d.fmt(required_stock) if stock_known else None,
            'starting_contribution_sufficient':None if starting is None or not stock_known else starting>=required_stock,
            'guild_fee_index':d.fmt(index),'source':data['source'],'context':data['context'],'steps':clean,
            'citations':[{'url':'https://xyq.163.com/introduce/sys/bp0015.html','checked_date':CHECKED}],
            'limits':['逐级费用来自用户指定游戏内/官方工具报价，此工具只汇总，不把该表认证为全服规则',
                      '经验、两、帮贡实际消耗、门槛与资材分列；未知不为0，门槛不再加进实际消费',
                      '需要起始帮贡是沿途已花帮贡加当步门槛的最大值，含实际扣款必须足额；只对应录入的>=门槛',
                      '费用指数只记录，未核其换算公式，不按比例缩放；仍需核本帮研究等级与当前学习资格']}


@d.exact_calculation
def pet_stage(data):
    d.fields(data,('ruleset','current_spirit','target_spirit','owned_pills','absorption_in_progress','remaining_absorption_hours','eligibility'),('context','pill_quote'))
    scope(data);current=intv(data['current_spirit'],'current spirit',0,50);target=intv(data['target_spirit'],'target spirit',current,50)
    if current%10:raise ValueError('This deterministic stage only supports 0/10/20/30/40/50 spirit boundaries')
    owned=intv(data['owned_pills'],'owned pills',0,1000)
    running=data['absorption_in_progress']
    if not isinstance(running,bool):raise ValueError('absorption_in_progress must be boolean')
    remaining=intv(data['remaining_absorption_hours'],'remaining absorption hours',0,96)
    if (not running and remaining) or (running and (current==50 or remaining==0)):raise ValueError('Absorption status and remaining time contradict')
    if data['eligibility'] not in ('confirmed','unknown','ineligible'):raise ValueError('Invalid pet advancement eligibility')
    count=(target-current+9)//10
    active=1 if running and count else 0
    newly_used=max(0,count-active)
    buy=max(0,newly_used-owned)
    hours=(remaining if active else 0)+96*newly_used
    ctx=None if data.get('context') is None else d.context(data['context'])
    if ctx is not None and ctx['currency']!='两':raise ValueError('Pet pill costs use 两')
    if data.get('pill_quote') is not None and ctx is None:raise ValueError('Pill price needs attributed context')
    quote=None if data.get('pill_quote') is None else d.quote(data['pill_quote'],ctx,'pill quote')
    price=None if quote is None else quote['amount']
    return {'calculator':'pet_advance_to_50','status':'conditional_budget' if data['eligibility']=='confirmed' else 'eligibility_'+data['eligibility'],
            'current_spirit':str(current),'target_spirit':str(target),'ending_spirit':str(current+10*count),
            'additional_potential_points':str(20*count),'remaining_absorptions':str(count),'new_pills_to_use':str(newly_used),
            'new_pills_to_buy':str(buy),'natural_sequential_hours':str(hours),'new_pill_cash_liang':'0' if buy==0 else None if price is None else d.fmt(price*buy),'pill_quote':d.quote_output(quote),
            'citations':[{'url':'https://xyq.163.com/introduce/2015/11/16/5018_580451.html','checked_date':CHECKED}],
            'limits':['只算50灵性前确定性易经丹阶段，宠物等级与灵性分开；超过50不套用此模型',
                      '已吃且正在吸收的丹不再次收费；库存只抵新增采购，不代表没有机会成本',
                      '自然逐颗吸收时间，不含触发资格、内丹补齐、加速费用、仙露、特性或重置',
                      '每颗报价为人工条件输入，须在报告另附区服、日期和来源；不会自动认定当前可买',
                      '官方旧页基础资格为携带等级≥45、内丹格满且低级内丹5层；特殊宠物资格另核']}

def pet_repair(data):
    """Compatibility API backed by the same dated pearl qualification engine."""
    d.fields(data,('ruleset','equipment_kind','equipment_level','repair_failures'),
             ('pearl_level','as_of','current_durability','maximum_durability'))
    if data['equipment_kind']!='pet':raise ValueError('This rule is for pet equipment, not character equipment')
    values={k:v for k,v in data.items() if k!='pearl_level'}
    values.update(method='pearl',material_level=data.get('pearl_level'))
    result=grounded.repair_guidance(values)
    level=intv(data['equipment_level'],'pet equipment level',1,200)
    failures=intv(data['repair_failures'],'repair failures',0,3)
    live=result['blocked_by_three_failures'] is False
    result.update(calculator='pet_equipment_repair',equipment_level=str(level),repair_failures=str(failures),
        minimum_pearl_level_threshold=result['minimum_material_level_from_verified_rule'],
        provided_pearl_level=None if data.get('pearl_level') is None else str(data['pearl_level']),
        provided_pearl_level_eligible=result['provided_material_level_eligible'],
        heaven_bead_blocked_by_three_failures=failures>=3,
        pearl_blocked_by_three_failures=result['blocked_by_three_failures'],
        pearl_three_failure_eligibility='official_explicit_allowed' if live else 'not_all_servers_released_at_snapshot',
        conclusion='官方明确三失败宠装仍可用珍珠；等级+5须达到宠装等级，补200受耐久上限限制。' if live else '本快照未到2013-03-19全服日，不追溯使用后来珍珠规则。')
    return result


def cage_eligibility(data):
    d.fields(data,('ruleset','pet_level','target_pet_level','character_level','character_stage','has_courtyard','has_cage'),('as_of',))
    scope(data)
    checked='2026-10-07'
    asof=d.day(data.get('as_of',checked),'as_of').isoformat()
    time_rule_live=asof>='2015-06-16'
    time_rollout='all_servers_released' if time_rule_live else 'partial_server_test_only' if asof>='2015-06-09' else 'not_yet_effective'
    display_live=asof>='2026-02-03'
    display_rollout='all_servers_released' if display_live else 'partial_server_test_only' if asof>='2026-01-27' else 'not_yet_effective'
    current=intv(data['pet_level'],'pet level',0,180);target=intv(data['target_pet_level'],'target pet level',current,180)
    role=intv(data['character_level'],'character level',0,175)
    caps={'not_flyup':150,'flyup_not_dujie':160,'dujie':180}
    if data['character_stage'] not in caps:raise ValueError('character_stage must be not_flyup/flyup_not_dujie/dujie')
    for field in ('has_courtyard','has_cage'):
        if not isinstance(data[field],bool):raise ValueError(field+' must be boolean')
    cap=min(role+10,caps[data['character_stage']]);needed=target>current;blockers=[]
    if needed and current<30:blockers.append('召唤兽须先通过其他合法路线练到至少30级，不能0级直接入笼')
    if needed and target>cap:blockers.append('目标超过当前人物等级/阶段允许的炼兽笼上限')
    if needed and not data['has_courtyard']:blockers.append('须有庭院放置炼兽笼，庭院费用未计')
    if needed and not data['has_cage']:blockers.append('需先取得并在庭院放置炼兽笼')
    return {'calculator':'pet_cage_eligibility','status':'no_training_needed' if not needed else 'prerequisites_missing' if blockers else 'known_prerequisites_met',
            'knowledge_checked_date':checked,'rule_snapshot_date':asof,
            'experience_time_rule':{'rollout':time_rollout,'test_effective_on':'2015-06-09','all_server_effective_on':'2015-06-16',
                                    'double_time_effective':False if time_rule_live else None,'jingxiu_time_effective':True if time_rule_live else None},
            'jingxiu_status_display':{'rollout':display_rollout,'test_effective_on':'2026-01-27','all_server_effective_on':'2026-02-03',
                                     'all_servers_available':True if display_live else None,'current_pet_bonus_observed':None},
            'cage_level_cap':str(cap),'minimum_character_level_for_target':str(max(0,target-10)),
            'pet_level_entry_minimum':'30','maximum_hours_per_day':'4','max_cages_per_courtyard':'2','concurrent_pets':'1',
            'blockers':blockers,'cage_npc_price_on_official_page_liang':'2000000',
            'additional_cage_cash_at_published_npc_price':'0' if not needed or data['has_cage'] else '2000000',
            'total_leveling_cash':None if needed else '0','total_training_hours':None if needed else '0',
            'citations':[{'url':u,'checked_date':checked} for u in ('https://xyq.163.com/introduce/2012/2/6/5014_262875.html','https://xyq.163.com/introduce/cy008.html')]+
                        [{'url':u,'published_on':published,'effective_on':effective,'source_scope':source_scope,'checked_date':checked}
                         for u,published,effective,source_scope in (
                             ('https://xyq.163.com/2015/6/6/4905_529431.html','2015-06-09','2015-06-09','partial_server_test_only'),
                             ('https://xyq.163.com/2015/6/15/4907_531671.html','2015-06-15','2015-06-16','all_server_release'),
                             ('https://xyq.163.com/wh/20260123/4907_1283382.html','2026-01-26','2026-01-27','partial_server_status_display_test'),
                             ('https://xyq.163.com/wh/20260202/4907_1284942.html','2026-02-02','2026-02-03','all_server_status_display_release'))],
            'limits':['这是路线资格检查，不是0到目标的完整价格或时间；总经验、每次经验量和间隔未核实',
                      '已有笼子不重复购买；NPC官方页标价与庭院、点卡、精修资源和练到30的费用分开',
                      '炼兽笼经验不受双倍时间影响，仍受精修时间影响；2015-06-09部分服务器测试，2015-06-16全服。' if time_rule_live else '本快照未到2015-06-16全服日；不把后来的双倍无效、精修有效规则追溯为当时全服结论。',
                      '炼兽笼界面可查看精修时间是否生效；2026-01-27测试，2026-02-03全服。本工具未读取玩家当前状态。' if display_live else '本快照未到2026-02-03全服日，不保证已有精修时间生效状态显示。',
                      '2015公告的2倍与3.2倍均相对调整前同一基础经验；3.2不是调整后基础经验的倍率，不据此计算速度或总经验',
                      '每次获得经验扣2体力，体力不足经验减半；使用2小时后不再消耗体力，使用中人物不能移动',
                      '同日4小时上限不推导出升级所需天数；当前角色阶段由用户确认',
                      '规则核验日固定为2026-10-07；as_of不代表重新核验，不保证此后更新已覆盖']}

repair_guidance = grounded.repair_guidance
xiuyedian_guidance = grounded.xiuyedian_guidance
gem_operations = grounded.gem_operations
scene_leveling = scene_module.scene_leveling

OPERATIONS={'scene_leveling':scene_leveling,'repair_guidance':repair_guidance,'xiuyedian_guidance':xiuyedian_guidance,'gem_operations':gem_operations,'focus':focus,'guild_skill':guild_skill,'pet_stage':pet_stage,'pet_repair':pet_repair,'cage_eligibility':cage_eligibility}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input');parser.add_argument('--kind',required=True,choices=tuple(OPERATIONS));parser.add_argument('--output');parser.add_argument('--format',choices=('json','text'),default='json');args=parser.parse_args(argv)
    try:
        result=OPERATIONS[args.kind](d.read_input(args.input))
        if args.format=='text':
            if args.kind not in ('repair_guidance','pet_repair','scene_leveling','xiuyedian_guidance','gem_operations'):
                raise ValueError('text format is supported for the grounded guidance operations only')
            try:
                from . import dossier
            except ImportError:
                import dossier
            out='\n'.join(dossier._report_grounded(result))+'\n'
        else:out=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as stream:stream.write(out)
        else:sys.stdout.write(out)
    except (ValueError,OSError,TypeError,RecursionError) as error:parser.error(str(error))
    return 0

if __name__=='__main__':raise SystemExit(main())
