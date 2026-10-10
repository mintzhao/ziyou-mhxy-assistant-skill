#!/usr/bin/env python3
"""Exact finite-budget selection of explicitly evidenced, whole upgrade projects.

Discrete goals describe confirmed target states (e.g. a specific item at 10 forge),
not inferred combat value. Cross-system budgets, prerequisites, exclusive routes,
and shared stock are checked together. Runtime is bounded to 16 project choices.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
import itertools
import json
from pathlib import Path
import sys
try:
    from . import decisions as d
except ImportError:
    import decisions as d

MAX_OPTIONS=16


def identifiers(value,label,limit=100):
    d.rows(value,label)
    if len(value)>limit or any(not isinstance(x,str) or not x.strip() for x in value) or len(set(value))!=len(value):
        raise ValueError(label+' must contain unique nonempty identifiers')
    return value


@d.exact_calculation
def plan(data):
    d.fields(data,('title','context','budget','goals','already_met','options','available_resources'),('reserve','evidence_notes','system_budgets','completed_options'))
    d.text(data['title'],'title');ctx=d.context(data['context'])
    if data['context'].get('ruleset','pc_time') not in ('pc_time','电脑版时间服','梦幻西游电脑版时间服'):raise ValueError('Only PC time-server planning is supported')
    budget=d.num(data['budget'],'budget');reserve=d.num(data.get('reserve',0),'reserve')
    if reserve>budget:raise ValueError('reserve cannot exceed available budget')
    available=budget-reserve
    raw_caps=data.get('system_budgets',{})
    if not isinstance(raw_caps,dict) or len(raw_caps)>100:raise ValueError('system_budgets must map at most100 systems to amounts in the same currency')
    system_caps={d.text(k,'system budget name',100):d.num(v,'system budget') for k,v in raw_caps.items()}
    goals={}
    for goal in d.rows(data['goals'],'goals'):
        d.fields(goal,('id','target','basis'))
        key=d.text(goal['id'],'goal id',80)
        if key in goals:raise ValueError('Duplicate goal id')
        d.text(goal['target'],'goal target');d.text(goal['basis'],'user goal basis');goals[key]=goal
    if not goals:raise ValueError('At least one explicit target is required; do not optimize empty goals')
    met=set(identifiers(data['already_met'],'already_met'))
    if not met<=set(goals):raise ValueError('Unknown already-met goal')
    completed=set(identifiers(data.get('completed_options',[]),'completed_options'))
    if not isinstance(data['available_resources'],dict) or len(data['available_resources'])>100:raise ValueError('available_resources must be a mapping of at most 100 resources')
    stock={d.text(k,'resource id',80):d.num(v,'available resource') for k,v in data['available_resources'].items()}
    options={};review=[];quote_conditions=[]
    rows=d.rows(data['options'],'options')
    if len(rows)>MAX_OPTIONS:raise ValueError('At most 16 whole-project alternatives; split a larger decision into explicit stages')
    for option in rows:
        d.fields(option,('id','label','system','goals','costs','eligibility','effect_basis','requires','conflicts','consumes'),('route_group','owned_materials'))
        key=d.text(option['id'],'option id',80)
        if key in options:raise ValueError('Duplicate option id')
        for field in ('label','system','effect_basis'):d.text(option[field],field)
        gs=set(identifiers(option['goals'],'option goals'))
        if not gs<=set(goals):raise ValueError('Option covers unknown goal')
        if option['eligibility'] not in ('confirmed','unknown','ineligible'):raise ValueError('Invalid eligibility')
        req=identifiers(option['requires'],'requires');con=identifiers(option['conflicts'],'conflicts')
        if key in req or key in con:raise ValueError('Self dependency/conflict is invalid')
        if not isinstance(option['consumes'],dict):raise ValueError('consumes must be a mapping')
        consumes={d.text(k,'resource id',80):d.num(v,'resource consumption') for k,v in option['consumes'].items()}
        if key not in completed and not set(consumes)<=set(stock):raise ValueError('Every shared resource needs explicit available stock; unknown stock is not zero')
        group=option.get('route_group')
        if group is not None:d.text(group,'route group',80)
        costs=[d.money_line(row,ctx,'cost') for row in d.rows(option['costs'],'costs')]
        owned=[d.money_line(row,ctx,'owned opportunity cost') for row in d.rows(option.get('owned_materials',[]),'owned materials')]
        cash=d.line_total(costs);opp=d.line_total(owned)
        conditional_kinds=sorted({row['kind'] for row in costs if row.get('kind') in ('estimate','sold')})
        if conditional_kinds and key not in completed:quote_conditions.append({'id':key,'kinds':conditional_kinds,'meaning':'估算或历史成交金额，只支持条件算术，不证明当前可买'})
        stale=any(row['status']=='stale_quote' for row in costs)
        owned_stale=any(row['status']=='stale_quote' for row in owned)
        if owned_stale: opp=None
        reasons=[]
        if option['eligibility']!='confirmed':reasons.append('eligibility_'+option['eligibility'])
        if cash is None:reasons.append('unknown_cash_cost')
        if stale:reasons.append('stale_quote')
        if reasons and key not in completed:review.append({'id':key,'reasons':reasons})
        options[key]={'id':key,'label':option['label'],'system':option['system'],'goals':gs,'cash':cash,
                      'opportunity':opp,'cost_lines':costs,'owned_materials':owned,'requires':set(req),'conflicts':set(con),
                      'consumes':consumes,'group':group,'ready':not reasons and key not in completed,'effect_basis':option['effect_basis']}
    if not completed<=set(options):raise ValueError('Unknown completed option')
    systems={o['system'] for o in options.values()}
    unused_caps=set(system_caps)-systems
    if unused_caps:raise ValueError('system_budgets has names matching no option: '+', '.join(sorted(unused_caps))+'; available systems: '+', '.join(sorted(systems)))
    uncapped_systems=sorted(systems-set(system_caps))
    for o in options.values():
        if not (o['requires']|o['conflicts'])<=set(options):raise ValueError('Unknown dependency or conflict')
    active=set();visited=set();topology=[]
    def visit(key):
        if key in active:raise ValueError('Cyclic prerequisites')
        if key in visited:return
        active.add(key)
        for req in sorted(options[key]['requires']):visit(req)
        active.remove(key);visited.add(key);topology.append(key)
    for key in options:visit(key)
    done=[options[key] for key in topology if key in completed]
    if any(not o['requires']<=completed for o in done):raise ValueError('Completed options must include their completed prerequisites')
    done_groups=[o['group'] for o in done if o['group']]
    if len(done_groups)!=len(set(done_groups)) or any(o['conflicts']&completed for o in done):raise ValueError('Completed options contain a conflict or exclusive route')
    met |= set().union(*(o['goals'] for o in done)) if done else set()
    candidates=[key for key,o in options.items() if o['ready']]
    valid_count=0;cheapest=[];runner_up=[];best=None;cheapest_count=0
    target_count=0;target_best=None;target_cheapest=[];target_cheapest_count=0
    def result_key(v):return (Decimal(v['cash_outlay']),len(v['selected']),v['selected'])
    counts={'budget':0,'system_budget':0,'dependencies_or_conflicts':0,'shared_resources':0,'goals':0}
    goalset=set(goals)
    for bits in itertools.product((False,True),repeat=len(candidates)):
        selected={key for key,take in zip(candidates,bits) if take}
        chosen=[options[key] for key in topology if key in selected]
        effective=selected|completed
        groups=[o['group'] for o in chosen+done if o['group']]
        if len(groups)!=len(set(groups)) or any(not o['requires']<=effective or o['conflicts']&effective for o in chosen+done):
            counts['dependencies_or_conflicts']+=1;continue
        covered=met|set().union(*(o['goals'] for o in chosen)) if chosen else met
        if covered!=goalset:counts['goals']+=1;continue
        used={r:sum((o['consumes'].get(r,Decimal(0)) for o in chosen),Decimal(0)) for r in stock}
        if any(used[r]>stock[r] for r in stock):counts['shared_resources']+=1;continue
        cost_by_system={}
        for o in chosen:cost_by_system[o['system']]=cost_by_system.get(o['system'],Decimal(0))+o['cash']
        cost=sum((o['cash'] for o in chosen),Decimal(0))
        category_gaps={system:d.fmt(max(Decimal(0),cost_by_system.get(system,Decimal(0))-cap)) for system,cap in system_caps.items()}
        target_record={'selected':[key for key in topology if key in selected],'cash_outlay':d.fmt(cost),
          'cash_by_system':{r:d.fmt(v) for r,v in cost_by_system.items()},'global_cash_shortfall':d.fmt(max(Decimal(0),cost-available)),
          'system_budget_shortfalls':category_gaps,'scope':'满足所列目标/资格/依赖/库存，尚未据预算筛选；不是当前可购方案'}
        target_count+=1
        if target_best is None or cost<target_best:target_best=cost;target_cheapest=[target_record];target_cheapest_count=1
        elif cost==target_best:target_cheapest_count+=1;target_cheapest=sorted(target_cheapest+[target_record],key=result_key)[:10]
        if any(Decimal(v)>0 for v in category_gaps.values()):counts['system_budget']+=1;continue
        if cost>available:counts['budget']+=1;continue
        opp=None if any(o['opportunity'] is None for o in chosen) else sum((o['opportunity'] for o in chosen),Decimal(0))
        candidate={'selected':[key for key in topology if key in selected],'cash_outlay':d.fmt(cost),
                      'economic_cost':None if opp is None else d.fmt(cost+opp),
                      'remaining_after_reserve':d.fmt(available-cost),'resources_used':{r:d.fmt(v) for r,v in used.items()},
                      'resources_left':{r:d.fmt(stock[r]-used[r]) for r in stock},
                   'cash_by_system':{r:d.fmt(v) for r,v in cost_by_system.items()},
                   'system_budget_remaining':{r:d.fmt(cap-cost_by_system.get(r,Decimal(0))) for r,cap in system_caps.items()}}
        valid_count+=1
        if best is None or cost<best:
            runner_up=sorted(cheapest+runner_up,key=result_key)[:10]
            best=cost;cheapest=[candidate];cheapest_count=1
        elif cost==best:
            cheapest_count+=1;cheapest=sorted(cheapest+[candidate],key=result_key)[:10]
        else:runner_up=sorted(runner_up+[candidate],key=result_key)[:10]
    status='goals_already_met' if not goalset-met else ('conditional_feasible' if quote_conditions else 'known_feasible') if valid_count else 'no_demonstrated_feasible_plan'
    conclusion='已知现状已经满足所列目标，保留现状无需新增花费' if status=='goals_already_met' else ('按录入金额、资格与目标效果的条件计算，所列候选最少新增现金为'+d.fmt(best)+ctx['currency'] if valid_count else '当前已确认的候选中没有同时达标且预算内的完整方案')
    if review:conclusion+='；仍有待核实候选，不能宣称全局最省或全局无解'
    projects=[]
    for key,o in options.items():
        projects.append({'id':key,'label':o['label'],'system':o['system'],'goals':sorted(o['goals']),
                         'cash_outlay':d.fmt(o['cash']),'opportunity_cost':d.fmt(o['opportunity']),
                         'cost_lines':o['cost_lines'],'owned_materials':o['owned_materials'],
                         'effect_basis':o['effect_basis'],'ready_for_comparison':o['ready']})
    if 'completed_options' in data:
        for project in projects:project['completed']=project['id'] in completed
    result={'calculator':'whole_budget_portfolio','title':data['title'],'status':status,'conclusion':conclusion,
            'context':data['context'],'budget':d.fmt(budget),'protected_reserve':d.fmt(reserve),'spendable':d.fmt(available),
            'system_budgets':{r:d.fmt(v) for r,v in system_caps.items()},'systems_without_specific_cap':uncapped_systems,'goals':list(goals.values()),'keep_current':{'cash_outlay':'0','met':sorted(met),'missing':sorted(goalset-met)},
            'lowest_cash_plans':cheapest,'lowest_cash_plan_count':cheapest_count,'truncated':cheapest_count>10,
            'other_feasible_plans':runner_up,
            'target_plans_before_money_constraints':target_cheapest,'target_plan_count_before_money_constraints':target_count,
            'minimum_target_cash_before_money_constraints':d.fmt(target_best),'minimum_target_plan_count':target_cheapest_count,
            'target_plan_diagnostics_truncated':target_cheapest_count>10,
            'known_feasible_count':valid_count,'quote_conditions':quote_conditions,'review_before_inclusion':review,'projects':projects,
            'enumerated':2**len(candidates),'filtered_counts':counts,
            'recommendation_changes_when':['当前预算或预留金变化','同区同目标报价变化或过期','旧装备出售尚未到账','现有资源、资格或目标事实被修正','发现未列入的更便宜或更符合目标的候选'],
            'limits':['目标与效果依据由宿主和用户明确确认，不根据门派、权重或宝石原始属性推断实战达标',
                      '只优化所列独立整项项目的新增现金；库存机会成本另报，不代表经济成本最优',
                      'consumes检查共享库存/可操作时间，禁止同一库存重复抵扣；项目不能在规划中创造新资源',
                      '成本按采购前现金填写，不能抵扣未到账卖旧收入；不同货币不能混在一份计划',
                      '依赖按顺序显示，不模拟价格随时间变化、收益、概率或隐藏机制']}
    if 'completed_options' in data:result['completed_options']=[key for key in topology if key in completed]
    return result


def text_report(result, resource_units=None):
    """Render existing results only; balances describe a plan, never execution."""
    currency = result['context']['currency']
    money = lambda value: '未知' if value is None else str(value) + currency
    units = resource_units or {}
    byid = {p['id']: p for p in result['projects']}
    goals = {g['id']: g['target'] for g in result['goals']}
    caps = result['system_budgets']
    out = [result['title'], result['conclusion'],
           '预算 ' + money(result['budget']) + '；预留 ' + money(result['protected_reserve'])
           + '；本次可动用 ' + money(result['spendable']),
           '保留现状：新增0' + currency + '；未达目标 '
           + ('、'.join(goals[k] for k in result['keep_current']['missing']) or '无')]
    if result['keep_current']['met']:
        out.append('已确认达成：' + '、'.join(goals[k] for k in result['keep_current']['met']))
    if result.get('completed_options'):
        out.append('已完成项目（不再计费或耗用库存）：' + '、'.join(byid[key]['label'] for key in result['completed_options']))
        out.append('预算与共享库存按本次录入的当前余额使用，不会自动扣除历史支出或消耗')
    out.append('列出 ' + str(len(result['lowest_cash_plans'])) + '/' + str(result['lowest_cash_plan_count'])
               + ' 个同价最低方案；已知可行方案共 ' + str(result['known_feasible_count']))
    if caps:
        out.append('分类预算不可互挪：' + '；'.join(k + '≤' + money(caps[k]) for k in sorted(caps)))
    if caps and result['systems_without_specific_cap']:
        out.append('这些分类未设独立上限，但仍受总预算与预留约束：' + '、'.join(result['systems_without_specific_cap']))
    def category_lines(plan, diagnostic=False):
        for system in sorted(set(plan['cash_by_system']) | set(caps)):
            spend = money(plan['cash_by_system'].get(system, '0'))
            line = '  分类 ' + system + '：计划支出 ' + spend
            if system in caps:
                line += '；上限 ' + money(caps[system])
                if diagnostic:
                    line += '；分类缺口' + money(plan['system_budget_shortfalls'][system])
                else:
                    line += '；计划后分类余额 ' + money(plan['system_budget_remaining'][system])
            else:
                line += '；未设独立上限，仍受总预算与预留约束'
            out.append(line)
    def cost_lines(project):
        for row in project['cost_lines']:
            suffix = '；报价未知，不能按0' if row['status'] == 'unknown_quote' else '；报价过期' if row['status'] == 'stale_quote' else ''
            out.append('    采购/费用：' + row['label'] + ' × ' + row['quantity']
                       + '；小计 ' + money(row['subtotal']) + suffix)
        for row in project['owned_materials']:
            suffix = '；报价过期，当前机会成本保持未知' if row['status'] == 'stale_quote' else ''
            out.append('    库存机会成本（不是新增现金）：' + row['label'] + ' × ' + row['quantity']
                       + '；录入小计 ' + money(row['subtotal']) + suffix)
    for i, plan in enumerate(result['lowest_cash_plans'], 1):
        out.append('方案 ' + str(i) + '：现金 ' + money(plan['cash_outlay'])
                   + '；预留后余款 ' + money(plan['remaining_after_reserve'])
                   + '；经济成本 ' + money(plan['economic_cost']))
        category_lines(plan)
        if not plan['selected']:
            out.append('  无需新增项目，保留现状')
        for n, key in enumerate(plan['selected'], 1):
            project = byid[key]
            out.append('  ' + str(n) + '. ' + project['label'] + '（新增现金 ' + money(project['cash_outlay']) + '）')
            cost_lines(project)
        if plan['resources_used']:
            out.append('  共享资源计划（尚未消耗；仅在此方案实际完成后才是预计余额）：')
            for resource in sorted(plan['resources_used']):
                unit = units.get(resource, '')
                out.append('    ' + resource + '：计划用 ' + plan['resources_used'][resource] + unit
                           + '；预计剩余 ' + plan['resources_left'][resource] + unit)
        else:
            out.append('  本方案未列共享资源消耗')
    if not result['lowest_cash_plans'] and result['target_plans_before_money_constraints']:
        out.append('目标已能达到但资金条件尚不成立，最低现金组合如下（不是可立即执行的推荐，尚未扣款或耗用库存）：')
        for plan in result['target_plans_before_money_constraints']:
            out.append('  ' + ' + '.join(byid[k]['label'] for k in plan['selected']) + '：现金' + money(plan['cash_outlay'])
                       + '；全局现金缺口' + money(plan['global_cash_shortfall']))
            category_lines(plan, diagnostic=True)
        if result['target_plan_diagnostics_truncated']:
            out.append('  仅列出' + str(len(result['target_plans_before_money_constraints'])) + '/'
                       + str(result['minimum_target_plan_count']) + '个同价目标组合')
    if not result['lowest_cash_plans'] and not result['target_plans_before_money_constraints']:
        out.append('尚无通过目标、资格、依赖和共享库存检查的完整组合；没有可执行方案，未扣款或耗用库存')
        reasons = {'dependencies_or_conflicts': '前置/互斥不满足', 'shared_resources': '共享资源不足', 'goals': '目标未全满足'}
        for key, label in reasons.items():
            if result['filtered_counts'][key]:
                out.append('  ' + label + '：排除 ' + str(result['filtered_counts'][key]) + ' 个组合')
    if result['quote_conditions']:
        out.append('报价条件：' + '；'.join(byid[x['id']]['label'] + '：' + ','.join(x['kinds'])
                   + '（' + x['meaning'] + '）' for x in result['quote_conditions']))
    reasons = {'eligibility_unknown': '资格未确认', 'eligibility_ineligible': '资格不成立',
               'unknown_cash_cost': '新增现金缺少报价', 'stale_quote': '采购报价过期'}
    for review in result['review_before_inclusion']:
        project = byid[review['id']]
        out.append('待核实候选 ' + project['label'] + '：' + '、'.join(reasons.get(k, k) for k in review['reasons']))
        cost_lines(project)
    out.append('需要重算的变化：' + '；'.join(result['recommendation_changes_when']))
    out.extend('边界：' + x for x in result['limits'])
    return '\n'.join(out) + '\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input');parser.add_argument('--format',choices=('json','text'),default='json');parser.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        result=plan(d.read_input(args.input));out=text_report(result) if args.format=='text' else json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as stream:stream.write(out)
        else:sys.stdout.write(out)
    except (ValueError,OSError,TypeError,RecursionError) as error:parser.error(str(error))
    return 0

if __name__=='__main__':raise SystemExit(main())
