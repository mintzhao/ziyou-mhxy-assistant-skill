#!/usr/bin/env python3
"""End-to-end, offline purchase decisions from verified resource rules and manual quotes.

This module joins eligibility, exact incremental bills, cash, opportunity cost,
and conditional alternatives. It does not estimate market prices or combat value.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import sys
try:
    from . import decisions as d, resources, routes
except ImportError:
    import decisions as d
    import resources
    import routes


def integer(value, label, lower=0, upper=100000):
    return resources._integer(value, label, lower, upper)


def pc_context(value):
    ctx=d.context(value)
    if value.get('ruleset', 'pc_time') not in ('pc_time','电脑版时间服','梦幻西游电脑版时间服'):
        raise ValueError('Only MHXY PC time-server rules are supported; do not apply to mobile/free/classic variants')
    return ctx


def price_ceiling(numerator, quantity=Decimal(1)):
    if numerator is None or quantity<=0:return None
    exact=Fraction(numerator)/Fraction(quantity)
    scaled=(exact*1000000).numerator//(exact*1000000).denominator
    decimal=min(Decimal('1000000000000'),Decimal(scaled)/Decimal(1000000))
    return {'exact_limit':str(exact),'max_nonnegative_quote_at_6dp':None if exact<0 else d.fmt(decimal),
            'nonnegative_quote_possible':exact>=0,'meaning':'该临界线在其他已填价格/费用/目标条件不变时成立；可填单价按六位小数向下取整，并限制在接口单价上限1万亿，避免超预算'}


def _comparison_views(comparison):
    """Attach per-conclusion dependencies; retain original arithmetic and quotes.

    A stale resale estimate or owned-stock value cannot invalidate upfront cash.
    Numeric conditional order is never an execution/market availability claim.
    """
    own = comparison['self_upgrade']; replacement = comparison['replacement']
    cash_lines = own['lines'] + replacement['purchase_fee_lines']
    buy = replacement['purchase_quote']; sale = replacement['resale_quote']
    net_lines = cash_lines + replacement['resale_fee_lines']
    economic_lines = net_lines + own['owned_materials']
    qualified = (comparison['eligibility_confirmed']
                 and comparison['target_equivalence']['status'] == 'confirmed')

    def view(left, right, lines, quotes, resale_dependent=False):
        quotes = [q for q in quotes if q is not None]
        stale = any(line['status'] == 'stale_quote' for line in lines) or any(q['stale'] for q in quotes)
        missing = left is None or right is None
        conditional = (any(line.get('kind') in ('sold', 'estimate') for line in lines)
                       or any(q['kind'] in ('sold', 'estimate') for q in quotes))
        # Conditional means attributed arithmetic, not a current purchasable offer.
        status = ('eligibility_unconfirmed' if not qualified else 'missing' if missing
                  else 'stale' if stale else 'conditional' if conditional or (resale_dependent and replacement['resale_status'] != 'settled') else 'ready')
        ordering = 'unknown'
        if qualified and not missing and not stale:
            a, b = Decimal(left), Decimal(right)
            ordering = 'tie' if a == b else 'self_upgrade' if a < b else 'replacement'
        return {'self_upgrade_cost': left, 'replacement_cost': right,
                'status': status, 'ordering': ordering, 'has_stale_quotes': stale,
                'missing_values': missing, 'eligibility_confirmed': qualified,
                'has_historical_or_estimated_quotes': conditional}

    return {'upfront_cash': view(own['cash_outlay'], replacement['upfront_cash_required'], cash_lines, [buy]),
            'net_cash': view(own['cash_outlay'], replacement['net_cost_if_resale_occurs'], net_lines, [buy, sale], True),
            'economic_cost': view(own['economic_cost'], replacement['net_cost_if_resale_occurs'], economic_lines, [buy, sale], True)}


def _view_summary(view, objective):
    label = '立即新增现金' if objective == 'upfront_cash' else '卖旧后条件经济成本'
    if view['ordering'] == 'unknown':
        reason = {'eligibility_unconfirmed': '资格或同目标未确认', 'missing': '缺少相关金额',
                  'stale': '相关报价过期'}.get(view['status'], '条件不足')
        return label + '尚不能排序：' + reason
    a = view['self_upgrade_cost']; b = view['replacement_cost']
    prefix = '自升' + a + '两，成品' + b + '两'
    order = {'self_upgrade': '自升较低', 'replacement': '成品较低', 'tie': '两条路线相同'}[view['ordering']]
    if view['ordering'] != 'tie': order += '（少' + d.fmt(abs(Decimal(a) - Decimal(b))) + '两）'
    condition = '（仅在录入卖旧净回款实现时）' if objective == 'economic_cost' else ''
    return label + '：' + prefix + '；' + order + condition


@d.exact_calculation
def gem_upgrade(data):
    d.fields(data, ('context', 'equipment', 'grade_quotes', 'owned_stones', 'fees'),
             ('budget', 'replacement', 'sunk_cost', 'decision_objective'))
    objective = data.get('decision_objective', 'unspecified')
    if 'decision_objective' in data and (not isinstance(objective, str) or objective not in ('upfront_cash', 'economic_cost')):
        raise ValueError('decision_objective must be upfront_cash/economic_cost when provided')
    ctx = pc_context(data['context'])
    if ctx['currency'] != '两': raise ValueError('Gem plans use 两; no implicit currency conversion')
    check = routes.gem_feasibility(data['equipment'])
    budget = None if data.get('budget') is None else d.num(data['budget'], 'budget')
    if not isinstance(data['grade_quotes'], dict) or not isinstance(data['owned_stones'], dict):
        raise ValueError('grade_quotes and owned_stones must be grade-keyed objects')
    quotes = {}; stock = {}
    for key, value in data['grade_quotes'].items():
        g = integer(key, 'grade', 1, 20)
        if str(g) != key: raise ValueError('Grades must use canonical integer keys')
        if value is not None: d.quote(value, ctx, 'grade ' + key)
        quotes[g] = value
    for key, value in data['owned_stones'].items():
        g = integer(key, 'owned grade', 1, 20)
        if str(g) != key: raise ValueError('Grades must use canonical integer keys')
        d.fields(value, ('quantity', 'opportunity_quote'))
        count = integer(value['quantity'], 'owned quantity', 0, 100000)
        if value['opportunity_quote'] is not None: d.quote(value['opportunity_quote'], ctx, 'owned opportunity quote')
        stock[g] = (count, value['opportunity_quote'])
    fees = d.rows(data['fees'], 'fees')
    for row in fees: d.money_line(row, ctx, 'fee')
    # A quoted zero is not confirmed zero when based only on history/estimation.
    # Scope this guard to remaining own-route fees, not an unused alternative.
    conditional_fees = [r['label'] for r in fees if r['quote'] is not None and r['quote']['kind'] in ('sold', 'estimate')]
    purchases = []; owned = []; bill = []
    for grade_text in check['requiredGrades']:
        g = int(grade_text); use_stock = stock.get(g, (0, None))[0] > 0
        q = stock[g][1] if use_stock else quotes.get(g)
        row = {'label': str(g) + '级宝石', 'quantity': '1', 'quote': q}
        (owned if use_stock else purchases).append(row)
        bill.append({'grade': str(g), 'required': '1', 'from_stock': '1' if use_stock else '0',
                     'to_buy': '0' if use_stock else '1', 'quote': q,
                     'cost_meaning': '库存可变现机会成本' if use_stock else '新增采购现金'})
    simple = resources.gems({k:data['equipment'][k] for k in ('gemType','currentForge','targetForge')})
    total_cash = d.line_total([d.money_line(r, ctx, 'purchase') for r in purchases + fees])
    opportunity = d.line_total([d.money_line(r, ctx, 'owned stone') for r in owned])
    economic = None if total_cash is None or opportunity is None else total_cash + opportunity
    stale = [r['label'] for r in purchases + fees if r['quote'] is not None and d.quote(r['quote'], ctx, r['label'])['stale']]
    owned_stale = [r['label'] for r in owned if r['quote'] is not None and d.quote(r['quote'], ctx, r['label'])['stale']]
    if owned_stale: opportunity=None; economic=None
    comparison = None; timing=None; alternative = data.get('replacement')
    if alternative is not None:
        d.fields(alternative, ('purchase', 'fees', 'old_item_resale', 'eligibility', 'equivalence'), ('resale_timing',))
        d.fields(alternative['equivalence'], ('status', 'basis'))
        if alternative['equivalence']['status'] not in ('confirmed', 'unknown', 'different_target'):
            raise ValueError('equivalence status must be confirmed/unknown/different_target')
        d.text(alternative['equivalence']['basis'], 'equivalence basis')
        compare = {'context': data['context'], 'self_upgrade': {'purchases': purchases, 'owned_materials': owned, 'fees': fees,
                   'eligible': 'confirmed' if check['status'] == 'eligible' else 'ineligible'},
                   'replacement': {'purchase': alternative['purchase'], 'fees': alternative['fees'], 'old_item_resale': alternative['old_item_resale'], 'eligible': alternative['eligibility']}}
        if 'sunk_cost' in data: compare['sunk_cost'] = data['sunk_cost']
        comparison = d.compare_upgrade(compare)
        comparison['target_equivalence'] = alternative['equivalence']
        comparison['decision_views'] = _comparison_views(comparison)
        if alternative.get('resale_timing') is not None:
            timing=alternative['resale_timing'];d.fields(timing,('not_before','keep_until_replacement','basis'))
            d.text(timing['basis'],'resale timing basis')
            if not isinstance(timing['keep_until_replacement'],bool):raise ValueError('keep_until_replacement must be boolean')
            when=None if timing['not_before'] is None else d.day(timing['not_before'],'resale not_before')
            if comparison['replacement']['resale_status']=='settled' and when is not None and when>ctx['asof']:raise ValueError('Settled sale contradicts future/keep-until-replacement sale restriction')
            timing=dict(timing,unlocked_as_of=None if when is None else when<=ctx['asof'])
            comparison['resale_timing']=timing
    blockers = list(check['reasons'])
    missing = [r['label'] for r in purchases + fees if r['quote'] is None]
    if missing: blockers.append('缺少新增采购报价：' + '、'.join(missing))
    if stale: blockers.append('现金采购报价超过设定有效期：' + '、'.join(stale))
    if owned_stale: blockers.append('库存机会价值报价过期，只影响经济成本比较，不影响已知采购现金：'+'、'.join(owned_stale))
    self_ok = check['status'] == 'eligible' and total_cash is not None and not stale
    self_afford = None if budget is None or total_cash is None else total_cash <= budget
    recommendation = '条件不足，保留原装备；先补会改变决定的项目'
    if check['status'] == 'ineligible': recommendation = '不要按这条路线采购，目标锻数或宝石资格不成立'
    elif self_ok:
        recommendation = '可按逐级采购清单核价；资源规则已通过，预算尚未提供' if budget is None else '可按逐级采购清单自升；这只说明资源和预算可行'
        if self_afford is False: recommendation = '当前预算不足；先降低目标或等待预算，不把旧装挂牌价当现钱'
    replacement_afford = None
    if comparison:
        gross = comparison['replacement']['upfront_cash_required']
        replacement_afford = None if gross is None or budget is None else Decimal(gross) <= budget
        views = comparison['decision_views']
        if alternative['equivalence']['status'] != 'confirmed': blockers.append('成品尚未确认达到同一目标，不能只按价格二选一')
        elif not comparison['eligibility_confirmed']: blockers.append('成品或自升资格尚未确认')
        else:
            cash_summary = _view_summary(views['upfront_cash'], 'upfront_cash')
            economic_summary = _view_summary(views['economic_cost'], 'economic_cost')
            if objective == 'upfront_cash': recommendation = '按最低立即新增现金比较：' + cash_summary
            elif objective == 'economic_cost': recommendation = '按经济成本比较：' + economic_summary
            else: recommendation = '未指定成本优先级；' + cash_summary + '；' + economic_summary
            if views['upfront_cash']['ordering'] == 'unknown':
                blockers.append(cash_summary)
            if views['economic_cost']['ordering'] == 'unknown':
                blockers.append(economic_summary + '；不阻断不依赖这些资料的立即现金结论')
            if replacement_afford is False:
                recommendation += '；但当前现金不足以先买成品，应等旧装成交或放弃该方案'
            if self_afford is False:
                recommendation += '；自升本次现金预算仍不够，先缩小目标'
    conditional_quotes=[r['label'] for r in purchases+fees if r['quote'] is not None and r['quote']['kind'] in ('sold','estimate')]
    if comparison:
        conditional_quotes += [name for name,q in [('成品',comparison['replacement']['purchase_quote'])] if q is not None and q['kind'] in ('sold','estimate')]
        conditional_quotes += ['成品购入费用：'+r['label'] for r in comparison['replacement']['purchase_fee_lines'] if r.get('kind') in ('sold','estimate')]
        # Future resale fees do not determine upfront procurement cash. Their
        # conditions remain in comparison.decision_views and the original lines.
    if conditional_quotes:
        blockers.append('含历史成交/估算报价，不能据此认定当前可成交：'+'、'.join(conditional_quotes))
        recommendation = '只作条件成本比较：含历史或估算价格，采购前先核实当前可买报价；' + recommendation.replace('可按逐级采购清单自升；这只说明资源和预算可行','录入金额在预算内，不证明现在可成交')
    if self_afford is False: blockers.append('自升新增现金超过本次预算')
    if replacement_afford is False: blockers.append('成品先买现金超过本次预算，未成交卖价不能抵扣')
    if self_afford is False and replacement_afford is False: recommendation += '；两条路线当前都缺现金，先等成交回款或降低目标'
    if timing and timing['unlocked_as_of'] is False:
        blockers.append('旧物在'+timing['not_before']+'之前不能卖；未来回款仍是条件，不能抵本次先买现金')
        if not timing['keep_until_replacement']:
            recommendation=recommendation.replace('应等旧装成交或放弃该方案','只能在'+timing['not_before']+'解限并实际成交后重新比较，或放弃该方案')
            recommendation=recommendation.replace('先等成交回款或降低目标','只能在'+timing['not_before']+'解限并实际成交后重算，或降低目标')
    if timing and timing['keep_until_replacement']:
        blockers.append('必须先取得替换物再卖旧物；不能先卖旧来弥补购入现金缺口')
        recommendation=recommendation.replace('应等旧装成交或放弃该方案','需压价或增加自有现金，不能先卖旧筹款')
        recommendation=recommendation.replace('先等成交回款或降低目标','需压价、降低目标或增加自有现金，不能先卖旧筹款')
        if replacement_afford is False:
            recommendation+='；先换后卖限制生效，不能靠这笔未来卖旧款启动替换'
            if self_afford is True and self_ok and not conditional_quotes:recommendation+='；按本次已录入条件，自升现金够，当前可保留自升路线'

    goal_status = 'remaining_work'
    next_action = '仅核对本轮目标所依赖的缺项或变动报价；按已列采购清单执行前确认，不自动采购'
    if comparison is not None:
        selected_view = comparison['decision_views'].get(objective)
        if selected_view is not None and selected_view['ordering'] != 'unknown':
            next_action = ('本轮成本比较已可给出；仅在相关报价、费用、资格或目标变化时重算，不自动采购'
                           if selected_view['status'] == 'ready' else
                           '本轮可作条件金额比较；采购前核实所选路线的当前可买报价，不自动采购')
            if objective == 'economic_cost' and comparison['decision_views']['upfront_cash']['status'] == 'ready':
                next_action = '采用已列经济成本条件；实际成交或到账后更新，不将条件回款当作先买现金，不自动采购'
        elif objective == 'unspecified':
            next_action = '按已列现金与经济口径选择；只补所选口径依赖的缺项，不自动采购'
    if not bill:
        if check['status'] != 'eligible':
            next_action = '先解决已列资格或目标冲突；没有新增锻数，不应继续逐级询价'
        elif alternative is not None and alternative['equivalence']['status'] != 'confirmed':
            goal_status = 'forge_met_target_unresolved'
            recommendation = '本件已达目标锻数；成品同目标尚未确认，不能据此认定整个替换目标已完成'
            next_action = '核对已列同目标差异；本件无新增宝石需求，费用仍按下列记录保留'
        elif total_cash == 0 and not stale and not conditional_fees:
            goal_status = 'completed'
            recommendation = '目标已达成，新增现金0两；无需为本目标询价或采购'
            next_action = '保留已确认现状；本目标无需新增动作，其他未完成目标仍独立核算'
        else:
            goal_status = 'forge_met_fees_remaining'
            recommendation = ('本件已达目标锻数；仍有已录入费用' + ('待核实' if total_cash is None else d.fmt(total_cash) + '两')
                              + '，不能把剩余费用当作0')
            if conditional_fees:
                recommendation = ('本件已达目标锻数；剩余费用仅有历史/估算记录，条件金额'
                                  + ('未知' if total_cash is None else d.fmt(total_cash) + '两')
                                  + '，仍需核实，不能确认费用为0')
            if stale: recommendation += '；费用报价过期，仅保留条件金额'
            if self_afford is False: recommendation += '；当前预算不足'
            next_action = '仅处理已列剩余费用或其缺项；无新增宝石需求，不必逐级询价'

    amounts=[d.money_line(r,ctx,'purchase') for r in purchases+fees]
    unknown=[(r,c) for r,c in zip(purchases+fees,amounts) if c['subtotal'] is None]
    one_unknown=None
    if len(unknown)==1:
        row,_=unknown[0];qty=d.num(row['quantity'],'unknown quote quantity');known=sum((Decimal(c['subtotal']) for c in amounts if c['subtotal'] is not None),Decimal(0))
        gross=None if comparison is None or comparison['replacement']['upfront_cash_required'] is None else Decimal(comparison['replacement']['upfront_cash_required'])
        net=None if comparison is None or comparison['replacement']['net_cost_if_resale_occurs'] is None else Decimal(comparison['replacement']['net_cost_if_resale_occurs'])
        one_unknown={'label':row['label'],'quantity':d.fmt(qty),'known_other_cash':d.fmt(known),'currency':ctx['currency'],
          'within_budget':price_ceiling(None if budget is None else budget-known,qty),
          'same_upfront_cash_as_replacement':price_ceiling(None if gross is None else gross-known,qty),
          'same_net_cash_if_resale_occurs':price_ceiling(None if net is None else net-known,qty),
          'same_economic_cost_if_resale_occurs':price_ceiling(None if net is None or opportunity is None else net-known-opportunity,qty),
          'limits':'只是一个未知单价的条件临界线；不填补现价，不解除资格/报价/卖旧时间限制'}
    replacement_limit=None
    if comparison is not None and budget is not None:
        f=d.line_total(comparison['replacement']['purchase_fee_lines'])
        replacement_limit=price_ceiling(None if f is None else budget-f)
    return {'calculator':'gem_upgrade_plan', 'scope':'梦幻西游电脑版时间服，单件普通宝石逐级升级与同目标成品比较',
            'recommendation':recommendation, 'decision_objective':objective, 'goal_status':goal_status, 'eligibility':check, 'bill':bill,
            'self_upgrade':{'cash_outlay':d.fmt(total_cash),'owned_material_opportunity_cost':d.fmt(opportunity),
                            'economic_cost':d.fmt(economic),'cash_within_budget':self_afford,'cash_remaining':d.fmt(budget-total_cash) if budget is not None and total_cash is not None else None},
            'budget':d.fmt(budget), 'currency':'两', 'replacement_upfront_within_budget':replacement_afford,
            'comparison':comparison,'resale_timing':timing,'replacement_purchase_affordability_ceiling':replacement_limit,'single_unknown_quote_thresholds':one_unknown, 'blockers':list(dict.fromkeys(blockers)),
            'resource_check':simple, 'next_action':next_action,
            'limits':['一段各需一颗对应级别，库存只抵同级同类宝石，不擅自拆合或折现',
                      '材料下限不当作预计合成成本；此采购清单使用对应等级成品石报价',
                      '最终面板、套装差异、修理失败与实战效果另核；不会自动认为两件物品等效',
                      '费用空列表表示用户明确确认无额外费用；不确定时填一行quote=null以保持未知']}


@d.exact_calculation
def training_mix(data):
    """Find the exact cheapest mixed route, or return a genuinely ordinary route.

    With no XP needed or an explicit max_items=0, the four item-specific fields
    are unused: they may be absent, null, or contain values that are ignored.
    The ordinary_only/no_upgrade_needed status identifies this branch. Context,
    cultivation, unknown top-level fields, and every explicit max_items are
    still validated when supplied. Ordinary/no-op routes may omit unrelated market
    context entirely; active mixed routes require context and all item fields.
    """
    item_fields=('item_xp','item_xp_evidence','item_quote','mixing_eligibility')
    d.fields(data, ('cultivation',), item_fields+('max_items','context'))
    # Ordinary fixed-rule arithmetic has no market quote or account server.
    # Omit context rather than manufacture a server; provided context remains strict.
    ctx=pc_context(data['context']) if 'context' in data else None
    if ctx is not None and ctx['currency']!='两': raise ValueError('Training uses 两')
    # Existing verified ordinary calculator is the single source of XP and prices.
    normal=resources.cultivation(data['cultivation'])
    if data['cultivation'].get('type') not in ('attack','spell','defense','anti_spell'):raise ValueError('Mixed item routes support only the four human cultivation types')
    routes._range(data['cultivation'])
    needed=int(normal['requiredXp'])
    explicit_maximum=integer(data['max_items'],'max_items',0,100000) if 'max_items' in data else None
    if needed==0 or explicit_maximum==0:
        return {'calculator':'training_mix','status':'no_upgrade_needed' if needed==0 else 'ordinary_only',
                'recommendation':'目标已达到，无需采购或点修' if needed==0 else '本次道具可用上限为0，只有普通路线；无需道具报价',
                'ordinary':normal,'best_mix':{'items':'0','ordinary_purchases':normal['purchases'],'cost_liang':normal['costLiang'],
                             'ordinary_materials':normal['materialsConsumed'],'surplus_xp':normal['surplusXp'],'saving_vs_all_ordinary':'0'},
                'limits':['普通路线仍须满足角色、帮派和开放资格；无需升级时不产生新增花费']}
    d.fields(data, ('context','cultivation')+item_fields, ('max_items',))
    xp=routes._fraction(data['item_xp'], 'item_xp', True)
    d.text(data['item_xp_evidence'], 'item XP evidence')
    eligibility=data['mixing_eligibility']
    if eligibility not in ('confirmed','unknown','ineligible'):raise ValueError('Invalid mixing eligibility')
    q=None if data['item_quote'] is None else d.quote(data['item_quote'],ctx,'item quote')
    maximum=routes._ceil(Fraction(needed)/xp)
    maximum=min(maximum,integer(maximum,'max_items',0,100000) if explicit_maximum is None else explicit_maximum)
    per_click=20000 if data['cultivation']['type'] in ('defense','anti_spell') else 30000
    if q is None:
        return {'calculator':'training_mix','status':'missing_quote','ordinary':normal,'recommendation':'先用普通路线确定预算上限；缺道具报价时不能确定混合最省方案','missing':['item_quote']}
    best=None; tied=0
    for count in range(maximum+1):
        remaining=max(Fraction(0),Fraction(needed)-count*xp)
        clicks=routes._ceil(remaining/10)
        cost=Decimal(count)*q['amount']+clicks*per_click
        surplus=count*xp+clicks*10-needed
        candidate=(cost,surplus,count,clicks)
        if best is None or candidate[:1]<best[:1]: best=candidate;tied=1
        elif candidate[0]==best[0]:
            tied+=1
            if candidate[1:]<best[1:]:best=candidate
    cost,surplus,count,clicks=best
    qualified=eligibility=='confirmed' and not q['stale']
    return {'calculator':'training_mix','status':'conditional_calculated' if qualified else 'eligibility_or_quote_unresolved',
            'recommendation':'在道具经验、报价、可混用与可用次数均成立时，下列组合现金最少' if qualified else '这是条件算术，先确认道具/普通修炼资格或更新报价',
            'ordinary':normal,'best_mix':{'items':str(count),'ordinary_purchases':str(clicks),'cost_liang':d.fmt(cost),
                       'ordinary_materials':str(clicks*5),'surplus_xp':str(surplus),'saving_vs_all_ordinary':d.fmt(Decimal(normal['costLiang'])-cost)},
            'item_quote':d.quote_output(q),'item_xp':str(xp),'item_xp_evidence':data['item_xp_evidence'],
            'mixing_eligibility':eligibility,'max_items':str(maximum),'price_tied_counts':str(tied),
            'method':'枚举0至所需全道具颗数/用户可用上限，每种用普通10XP购次补足，精确十进制比较',
            'limits':['每颗XP与混用资格由用户确认，不从品质推断；普通购次资格仍须满足',
                      '先把普通修炼做在前，再用道具覆盖剩余需求，仅在两者均可使用时成立',
                      '不包含时间成本、帮派等候、道具每日限量或封顶余量可保留性；max_items可录入用户确认的当期上限',
                      '所有价格为手工数据；最小成本不保证当前可以买到足够数量']}

OPERATIONS={'gem_upgrade':gem_upgrade,'training_mix':training_mix}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input');parser.add_argument('--kind',choices=tuple(OPERATIONS),required=True);parser.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        result=OPERATIONS[args.kind](d.read_input(args.input));out=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as stream:stream.write(out)
        else:sys.stdout.write(out)
    except (ValueError,OSError,TypeError,RecursionError) as error:parser.error(str(error))
    return 0

if __name__=='__main__':raise SystemExit(main())
