#!/usr/bin/env python3
"""Original offline decision arithmetic. No market lookup or combat prediction.

Prices are manual, attributed observations. Unknown values never become zero.
All monetary output is decimal text. Python 3.9+ standard library only.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import json
import os
import stat
from functools import wraps
from pathlib import Path
import re
import sys

MAX_ROWS = 200
MAX_BYTES = 1_000_000


def text(value, label, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(label + ' must be nonempty text without controls')
    return value


def fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError('Expected an object')
    absent = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if absent or extra:
        raise ValueError('Missing fields: ' + ', '.join(sorted(absent)) + '; unknown fields: ' + ', '.join(sorted(extra)))


def num(value, label, signed=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(label + ' must be an integer or decimal string')
    s = str(value)
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?', s):
        raise ValueError(label + ' requires a plain decimal with up to 6 decimal places')
    n = Decimal(s)
    if not n.is_finite() or abs(n) > Decimal('1000000000000') or (not signed and n < 0):
        raise ValueError(label + ' is outside supported range')
    return n


def fmt(n):
    if n is None:
        return None
    return format(n, 'f').rstrip('0').rstrip('.') if '.' in format(n, 'f') else str(n)


def ratio(n, d):
    if d <= 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        return fmt((n / d).quantize(Decimal('0.000001')))


def rows(value, label, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= MAX_ROWS:
        raise ValueError(label + ' must be a bounded list')
    return value


def day(value, label):
    text(value, label, 10)
    try:
        v = date.fromisoformat(value)
    except ValueError:
        raise ValueError(label + ' must be YYYY-MM-DD')
    if v.isoformat() != value:
        raise ValueError(label + ' must be YYYY-MM-DD')
    return v


def context(data):
    fields(data, ('server', 'currency', 'as_of'), ('max_age_days', 'ruleset'))
    server = text(data['server'], 'server', 100)
    currency = text(data['currency'], 'currency', 40)
    asof = day(data['as_of'], 'as_of')
    age = data.get('max_age_days', 7)
    if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 365:
        raise ValueError('max_age_days must be an integer between 0 and 365')
    if 'ruleset' in data:
        text(data['ruleset'], 'ruleset', 100)
    return dict(server=server, currency=currency, asof=asof, age=age)


def quote(value, ctx, label):
    """A quote is attributed input, never independently verified by this module."""
    fields(value, ('amount', 'currency', 'server', 'observed_on', 'source', 'kind'), ('notes',))
    amount = num(value['amount'], label + '.amount')
    text(value['source'], label + '.source')
    for key in ('currency', 'server'):
        if value[key] != ctx[key]:
            raise ValueError(label + ': mixed ' + key + ' requires a separate scenario, not implicit conversion')
    if value['kind'] not in ('asking', 'sold', 'user_quote', 'estimate'):
        raise ValueError(label + '.kind must be asking/sold/user_quote/estimate')
    observed = day(value['observed_on'], label + '.observed_on')
    if observed > ctx['asof']:
        raise ValueError(label + ': quote date is after as_of')
    if 'notes' in value:
        text(value['notes'], label + '.notes')
    age = (ctx['asof'] - observed).days
    return dict(amount=amount, stale=age > ctx['age'], age_days=age, kind=value['kind'], source=value['source'], currency=value['currency'], server=value['server'], observed_on=value['observed_on'])


def quote_output(value):
    return None if value is None else {k: fmt(v) if isinstance(v, Decimal) else v for k, v in value.items()}


def money_line(value, ctx, label):
    fields(value, ('label', 'quantity', 'quote'))
    text(value['label'], label + '.label')
    qty = num(value['quantity'], label + '.quantity')
    if value['quote'] is None:
        return {'label': value['label'], 'quantity': fmt(qty), 'subtotal': None, 'status': 'unknown_quote'}
    q = quote(value['quote'], ctx, label + '.quote')
    return {'label': value['label'], 'quantity': fmt(qty), 'subtotal': fmt(q['amount'] * qty),
            'status': 'stale_quote' if q['stale'] else 'manual_quote', 'kind': q['kind'], 'source': q['source'], 'age_days': q['age_days'], 'unit_quote': quote_output(q)}


def line_total(lines):
    return None if any(x['subtotal'] is None for x in lines) else sum((Decimal(x['subtotal']) for x in lines), Decimal(0))


def exact_calculation(function):
    @wraps(function)
    def run(*args, **kwargs):
        with localcontext() as ctx:
            ctx.prec = 100
            return function(*args, **kwargs)
    return run


@exact_calculation
def compare_upgrade(data):
    """Compare incremental cash and economic cost; sunk spend is never charged again."""
    fields(data, ('context', 'self_upgrade', 'replacement'), ('sunk_cost',))
    ctx = context(data['context'])
    own = data['self_upgrade']; replacement = data['replacement']
    fields(own, ('purchases', 'fees', 'owned_materials'), ('eligible',))
    fields(replacement, ('purchase', 'fees', 'old_item_resale'), ('eligible',))
    for route in (own, replacement):
        if 'eligible' in route and route['eligible'] not in ('confirmed', 'unknown', 'ineligible'):
            raise ValueError('eligible must be confirmed/unknown/ineligible')
    purchase_lines = [money_line(x, ctx, 'self purchase') for x in rows(own['purchases'], 'self purchases')]
    fee_lines = [money_line(x, ctx, 'self fee') for x in rows(own['fees'], 'self fees')]
    material_lines = [money_line(x, ctx, 'owned opportunity cost') for x in rows(own['owned_materials'], 'owned materials')]
    self_cash = line_total(purchase_lines + fee_lines)
    opportunity = line_total(material_lines)
    self_economic = None if self_cash is None or opportunity is None else self_cash + opportunity
    buy = None if replacement['purchase'] is None else quote(replacement['purchase'], ctx, 'replacement purchase')
    buy_fees = [money_line(x, ctx, 'replacement fee') for x in rows(replacement['fees'], 'replacement fees')]
    fees = line_total(buy_fees)
    gross = None if buy is None or fees is None else buy['amount'] + fees
    sale = replacement['old_item_resale']
    resale = None; resale_status = 'unknown'; sale_fees = []; sale_q = None
    if sale is not None:
        fields(sale, ('quote', 'fees', 'status'))
        if sale['status'] not in ('settled', 'conditional'):
            raise ValueError('resale.status must be settled or conditional')
        sale_q = quote(sale['quote'], ctx, 'resale')
        sale_fees = [money_line(x, ctx, 'resale fee') for x in rows(sale['fees'], 'resale fees')]
        sf = line_total(sale_fees)
        if sf is not None:
            resale = sale_q['amount'] - sf
        resale_status = sale['status']
        if resale_status == 'settled' and sale_q['kind'] != 'sold':
            raise ValueError('settled resale requires kind=sold; asking prices are not proceeds')
    net = None if gross is None or resale is None else gross - resale
    buy_economic = net  # Foregone resale value of the old item is represented by net replacement cost.
    conditions = []
    if any(x['status'] == 'stale_quote' for x in purchase_lines + fee_lines + material_lines + buy_fees + sale_fees):
        conditions.append('Some manual quotes are older than the chosen freshness window')
    if buy and buy['stale']:
        conditions.append('Replacement purchase quote is stale')
    if sale_q is not None and sale_q['stale']:
        conditions.append('Resale quote is stale')
    if resale_status != 'settled':
        conditions.append('Resale is conditional or unknown; do not subtract it from cash needed before sale')
    eligibility = {'self_upgrade': own.get('eligible', 'unknown'), 'replacement': replacement.get('eligible', 'unknown')}
    conditions.append('Compare only routes delivering equivalent user targets; the calculator does not infer combat equivalence')
    if 'sunk_cost' in data and data['sunk_cost'] is not None:
        num(data['sunk_cost'], 'sunk_cost')
    threshold_cash = None if self_cash is None or fees is None or resale is None else self_cash + resale - fees
    threshold_economic = None if self_economic is None or fees is None or resale is None else self_economic + resale - fees
    def ordering(a, b):
        return 'unknown' if a is None or b is None else ('tie' if a == b else ('self_upgrade' if a < b else 'replacement'))
    valid = all(v == 'confirmed' for v in eligibility.values())
    return {'calculator': 'upgrade_compare', 'currency': ctx['currency'], 'server': ctx['server'],
            'self_upgrade': {'cash_outlay': fmt(self_cash), 'owned_material_opportunity_cost': fmt(opportunity), 'economic_cost': fmt(self_economic), 'lines': purchase_lines + fee_lines, 'owned_materials': material_lines},
            'replacement': {'upfront_cash_required': fmt(gross), 'purchase_quote': quote_output(buy), 'purchase_fee_lines': buy_fees, 'net_resale_proceeds': fmt(resale), 'resale_quote': quote_output(sale_q), 'resale_fee_lines': sale_fees, 'resale_status': resale_status, 'net_cost_if_resale_occurs': fmt(net)},
            'cash_cost_comparison_if_resale_occurs': ordering(self_cash, net),
            'economic_cost_comparison_if_resale_occurs': ordering(self_economic, buy_economic),
            'comparable_routes_eligibility': eligibility, 'eligibility_confirmed': valid,
            'comparison_has_stale_quotes': any('stale' in message or 'older' in message for message in conditions),
            'replacement_purchase_break_even_cash': fmt(threshold_cash), 'replacement_purchase_break_even_economic': fmt(threshold_economic),
            'break_even_formula': 'replacement purchase <= self cost + net old-item resale - replacement fees',
            'sunk_cost_excluded': data.get('sunk_cost'), 'conditions': conditions,
            'unknowns': [x['label'] for x in purchase_lines + fee_lines + material_lines + buy_fees + sale_fees if x['subtotal'] is None] + ([] if buy else ['replacement purchase']) + ([] if resale is not None else ['net old-item resale']),
            'provenance': 'manual_user_observations_not_independently_verified'}


@exact_calculation
def comparables(data):
    """Strict matching descriptive samples; never manufacture a market appraisal."""
    fields(data, ('context', 'category', 'subject', 'comparables'), ('subject_quote', 'match_fields'))
    ctx = context(data['context'])
    subject = data['subject']
    if not isinstance(subject, dict) or not subject:
        raise ValueError('subject must contain explicit account/equipment features')
    for k, v in subject.items():
        text(k, 'feature', 80)
        if v is not None and (not isinstance(v, (str, int)) or isinstance(v, bool)):
            raise ValueError('features must be text or integers, not null/bool')
    required_features = {
        'account': ['ruleset', 'level', 'school', 'human_cultivation', 'pet_cultivation', 'skills', 'included_assets'],
        'equipment': ['ruleset', 'level', 'slot', 'base_stats', 'special_effects', 'set', 'repair_failures', 'gem_types', 'forge'],
        'accessory': ['ruleset', 'level', 'slot', 'base_stats', 'affixes', 'repair_failures', 'forge'],
    }
    if data['category'] not in required_features:
        raise ValueError('category must be account/equipment/accessory')
    extra_keys = rows(data.get('match_fields', []), 'match_fields')
    if any(not isinstance(k, str) for k in extra_keys) or len(set(extra_keys)) != len(extra_keys):
        raise ValueError('match_fields must contain unique feature names')
    keys = list(dict.fromkeys(required_features[data['category']] + extra_keys))
    missing_subject = [k for k in keys if k not in subject or subject[k] is None or (isinstance(subject[k], str) and not subject[k].strip())]
    if missing_subject:
        return {'calculator': 'comparables', 'status': 'subject_features_incomplete', 'missing_subject_features': missing_subject, 'market_value': None, 'matched': [], 'excluded': [], 'groups': {}, 'warnings': ['先补全用于筛选的底子；不能拿三修挂牌类推七修成交价']}
    matched = []; excluded = []; groups = {'asking': [], 'sold': [], 'user_quote': [], 'estimate': []}; ids = set()
    for item in rows(data['comparables'], 'comparables'):
        fields(item, ('id', 'features', 'quote'), ('notes',))
        ident = text(item['id'], 'id', 100)
        if ident in ids:
            raise ValueError('Duplicate comparable id')
        ids.add(ident)
        if not isinstance(item['features'], dict):
            raise ValueError('features must be an object')
        reasons = []
        for k in keys:
            if k not in item['features'] or item['features'][k] is None or (isinstance(item['features'][k], str) and not item['features'][k].strip()):
                reasons.append('missing:' + k)
            elif item['features'][k] != subject[k] or type(item['features'][k]) is not type(subject[k]):
                reasons.append('mismatch:' + k)
        # Cross-server/currency is excluded, not silently mixed.
        if not isinstance(item['quote'], dict):
            raise ValueError('Each comparable requires an attributed quote')
        q0 = item['quote']
        if q0.get('server') != ctx['server']:
            reasons.append('mismatch:server')
        if q0.get('currency') != ctx['currency']:
            reasons.append('mismatch:currency')
        if reasons:
            excluded.append({'id': ident, 'reasons': reasons}); continue
        q = quote(q0, ctx, 'comparable ' + ident)
        if q['stale']:
            excluded.append({'id': ident, 'reasons': ['stale_quote']}); continue
        match = {'id': ident, 'amount': fmt(q['amount']), 'kind': q['kind'], 'source': q['source'], 'age_days': q['age_days'], 'unit_quote': quote_output(q)}
        matched.append(match); groups[q['kind']].append(q['amount'])
    summary = {}
    target = None
    if data.get('subject_quote') is not None:
        target = quote(data['subject_quote'], ctx, 'subject_quote')
    for k, values in groups.items():
        ordered = sorted(values); n = len(ordered)
        median = None if n == 0 else ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        summary[k] = {'count': n, 'minimum': fmt(ordered[0]) if n else None, 'median': fmt(median), 'maximum': fmt(ordered[-1]) if n else None,
                      'subject_minus_sample_median': fmt(target['amount'] - median) if target and median is not None else None}
    return {'calculator': 'comparables', 'matched': matched, 'excluded': excluded, 'groups': summary,
            'subject_quote_stale': target['stale'] if target else None, 'matched_on': keys,
            'unchecked_subject_features': [k for k in subject if k not in keys],
            'market_value': None, 'status': 'descriptive_samples_only' if matched else 'no_comparable_evidence',
            'warnings': ['挂牌不是成交；各类型报价分开，样本范围不是估值置信区间', '只按指定字段严格筛选；未提供、未匹配的底子、属性、装备宝宝和条件仍可能影响可比性', '养成投入和宝石成本不能自动当作二手残值或保值保证'],
            'provenance': 'manual_user_observations_not_independently_verified'}


@exact_calculation
def gem_premium(data):
    """Observed paired price differences, not a universal gemstone resale discount."""
    fields(data, ('context', 'category', 'pairs'))
    ctx = context(data['context'])
    keys = {
        'equipment': ['ruleset', 'level', 'slot', 'base_stats', 'special_effects', 'set', 'repair_failures', 'gem_types'],
        'accessory': ['ruleset', 'level', 'slot', 'base_stats', 'affixes', 'repair_failures'],
    }
    if data['category'] not in keys:
        raise ValueError('gem_premium category must be equipment/accessory')
    accepted = []; excluded = []; ids = set()
    for pair in rows(data['pairs'], 'pairs'):
        fields(pair, ('id', 'lower', 'higher'), ('incremental_material_cost',))
        ident = text(pair['id'], 'id', 80)
        if ident in ids: raise ValueError('Duplicate pair id')
        ids.add(ident)
        for side in ('lower', 'higher'):
            fields(pair[side], ('features', 'quote'))
            if not isinstance(pair[side]['features'], dict): raise ValueError('features must be an object')
        lower, higher = pair['lower']['features'], pair['higher']['features']
        reasons = []
        paired_keys = sorted(set(keys[data['category']]) | ((set(lower) | set(higher)) - {'forge'}))
        for key in paired_keys:
            if key not in lower or key not in higher or any(side[key] is None or isinstance(side[key], bool) or not isinstance(side[key], (str, int)) or (isinstance(side[key], str) and not side[key].strip()) for side in (lower, higher)):
                reasons.append('missing:' + key)
            elif type(lower[key]) is not type(higher[key]) or lower[key] != higher[key]:
                reasons.append('mismatch:' + key)
        for side in (lower, higher):
            if isinstance(side.get('forge'), bool) or not isinstance(side.get('forge'), int) or not 0 <= side['forge'] <= 20:
                raise ValueError('Each paired item needs a forge integer in 0..20')
        if higher['forge'] <= lower['forge']: raise ValueError('higher forge must exceed lower forge')
        quotes = []
        for side in ('lower', 'higher'):
            q = quote(pair[side]['quote'], ctx, side + ' quote'); quotes.append(q)
            if q['stale']: reasons.append('stale:' + side)
        if quotes[0]['kind'] != quotes[1]['kind']: reasons.append('mismatch:quote_kind')
        if reasons:
            excluded.append({'id': ident, 'reasons': reasons}); continue
        difference = quotes[1]['amount'] - quotes[0]['amount']
        cost = None if pair.get('incremental_material_cost') is None else quote(pair['incremental_material_cost'], ctx, 'incremental material cost')
        accepted.append({'id': ident, 'lower_forge': lower['forge'], 'higher_forge': higher['forge'],
                         'observed_price_difference': fmt(difference), 'quote_kind': quotes[0]['kind'],
                         'difference_to_incremental_material_cost_ratio': ratio(difference, cost['amount']) if cost else None,
                         'material_cost_stale': cost['stale'] if cost else None,
                         'matched_on': paired_keys, 'sources': [q['source'] for q in quotes]})
    return {'calculator':'gem_premium', 'accepted_pairs':accepted, 'excluded_pairs':excluded,
            'universal_discount':None, 'warning':'这是同底子不同段数报价的观察价差，不证明价差全由宝石造成；挂牌与成交不得混对，历史造价不等于二手残值。材料比率是样本算术，不能推广为统一折扣。'}


@exact_calculation
def ledger(data):
    """Multi-system totals, scoped completeness, and non-additive currencies/resources."""
    fields(data, ('lines',), ('budgets', 'scope'))
    budgets = data.get('budgets', {})
    if not isinstance(budgets, dict):
        raise ValueError('budgets must map currencies to amounts')
    budget = {text(k, 'currency', 40): num(v, 'budget') for k, v in budgets.items()}
    ids = set(); clean = []; totals = {}; unknown = []
    for line in rows(data['lines'], 'lines'):
        fields(line, ('id', 'system', 'label', 'currency', 'amount', 'status', 'source'), ('requires', 'resources', 'notes'))
        ident = text(line['id'], 'id', 80)
        if ident in ids:
            raise ValueError('Duplicate ledger id')
        ids.add(ident)
        for k in ('system', 'label', 'currency', 'source'):
            text(line[k], k)
        if line['status'] not in ('required', 'optional', 'owned', 'excluded'):
            raise ValueError('ledger status must be required/optional/owned/excluded')
        cost = None if line['amount'] is None else num(line['amount'], 'amount')
        if line['status'] == 'owned' and cost not in (None, Decimal(0)):
            raise ValueError('owned line must not re-charge sunk acquisition cost; future fees need separate required line')
        req = line.get('requires', [])
        rows(req, 'requires')
        if len(set(req)) != len(req) or ident in req:
            raise ValueError('invalid prerequisites')
        resources = line.get('resources', {})
        if not isinstance(resources, dict):
            raise ValueError('resources must be a mapping')
        resource_out = {text(k, 'resource'): fmt(num(v, 'resource quantity')) if v is not None else None for k, v in resources.items()}
        item = dict(line); item.update(amount=fmt(cost), requires=req, resources=resource_out)
        clean.append(item)
        c = line['currency']; t = totals.setdefault(c, {'known_required': Decimal(0), 'known_optional': Decimal(0), 'unknown_required': [], 'unknown_optional': []})
        if line['status'] in ('required', 'optional'):
            if cost is None:
                t['unknown_' + line['status']].append(ident); unknown.append(ident)
            else:
                t['known_' + line['status']] += cost
    graph = {x['id']: x['requires'] for x in clean}
    for ident, parents in graph.items():
        if any(p not in graph for p in parents):
            raise ValueError('unknown prerequisite for ' + ident)
    visited = set(); active = set(); order = []
    def visit(k):
        if k in active:
            raise ValueError('cyclic ledger prerequisites')
        if k in visited:
            return
        active.add(k)
        for p in graph[k]: visit(p)
        active.remove(k); visited.add(k); order.append(k)
    for k in graph: visit(k)
    byid = {x['id']: x for x in clean}
    blockers = [{'id': x['id'], 'excluded_prerequisite': p} for x in clean if x['status'] == 'required' for p in x['requires'] if byid[p]['status'] in ('optional', 'excluded')]
    summary = {}
    for c, t in totals.items():
        complete = not t['unknown_required']
        summary[c] = {k: fmt(v) if isinstance(v, Decimal) else v for k, v in t.items()}
        summary[c].update(required_total=fmt(t['known_required']) if complete else None,
                          required_budget_remaining=fmt(budget[c] - t['known_required']) if complete and c in budget else None,
                          known_required_exceeds_budget=(t['known_required'] > budget[c]) if c in budget else None)
    return {'calculator': 'multi_system_ledger', 'scope': data.get('scope', '仅已列项目；不代表全部养号成本'), 'lines': clean,
            'by_currency': summary, 'unknown_cost_lines': unknown, 'prerequisite_order': order, 'prerequisite_blockers': blockers,
            'complete_within_listed_required_scope': not any(t['unknown_required'] for t in totals.values()) and not blockers,
            'warning': '不同货币不相加；未列系统、未知费用、额外前置、维护和未定机会成本不会自动补零'}


@exact_calculation
def target_gaps(data):
    """Measure user-set target gaps and route missing evidence without build rankings."""
    fields(data, ('profile', 'current', 'targets'), ('prerequisites', 'measurement_state'))
    profile = data['profile']; fields(profile, (), ('school', 'level', 'activity', 'pain', 'server', 'ruleset', 'budget'))
    current = data['current']; targets = data['targets']
    if not isinstance(current, dict) or not isinstance(targets, dict):
        raise ValueError('current and targets must be objects')
    gaps = []
    for k, target in targets.items():
        text(k, 'metric', 80); fields(target, ('value', 'direction', 'basis'))
        value = num(target['value'], k + ' target', True)
        if target['direction'] not in ('at_least', 'at_most'):
            raise ValueError('target direction must be at_least/at_most')
        text(target['basis'], 'target basis')
        old = current.get(k); have = None if old is None else num(old, k + ' current', True)
        delta = None if have is None else max(Decimal(0), value-have if target['direction']=='at_least' else have-value)
        gaps.append({'metric': k, 'current': fmt(have), 'target': fmt(value), 'direction': target['direction'], 'gap': fmt(delta), 'met': None if delta is None else delta == 0, 'basis': target['basis']})
    prerequisites = []
    for p in rows(data.get('prerequisites', []), 'prerequisites'):
        fields(p, ('label', 'status', 'source'))
        if p['status'] not in ('met', 'unmet', 'unknown'):
            raise ValueError('prerequisite status must be met/unmet/unknown')
        text(p['label'], 'prerequisite label'); text(p['source'], 'prerequisite source')
        prerequisites.append(p)
    questions = []
    for k, prompt in [('activity','主要玩普通任务、难度任务还是PK？'), ('pain','现在最困扰的是出手、生存、输出还是操作/时间成本？'), ('budget','这次最多愿意新增花多少钱，用什么货币？')]:
        if not profile.get(k): questions.append({'field': k, 'question': prompt})
    if not data.get('measurement_state') and current:
        questions.append({'field':'measurement_state','question':'这些面板是否同一状态，包含临时符、阵法等吗？'})
    return {'calculator': 'target_gaps', 'gaps': gaps, 'prerequisites': prerequisites, 'next_questions': questions[:2],
            'other_missing_context': [x['field'] for x in questions[2:]],
            'unmet_prerequisites': [x['label'] for x in prerequisites if x['status']=='unmet'],
            'unknown_prerequisites': [x['label'] for x in prerequisites if x['status']=='unknown'],
            'ranking': None, 'conditional_next_step': '先用当前具体痛点选目标，再比较能达到该目标的增量花费；没有目标时展示费用与各项变化，不强造权重或门派排名',
            'warning': '目标仅为用户指定或具名来源参考；不自动视为官方战斗达标线。没有可靠公式时不换算物爆率、真实伤害或生存率'}


@exact_calculation
def income_scenario(data):
    """User-recorded or explicitly hypothetical income, never a promised game yield."""
    fields(data, ('currency', 'initial_outlay', 'monthly_revenue', 'monthly_costs', 'monthly_hours', 'basis'), ('target_monthly_net', 'resale_scenarios'))
    text(data['currency'], 'currency', 40); text(data['basis'], 'basis')
    initial = num(data['initial_outlay'], 'initial_outlay'); revenue = num(data['monthly_revenue'], 'monthly_revenue')
    hours = num(data['monthly_hours'], 'monthly_hours')
    if hours == 0:
        raise ValueError('monthly_hours must be positive')
    costs = []
    for x in rows(data['monthly_costs'], 'monthly_costs'):
        fields(x, ('label','amount')); text(x['label'], 'cost label'); costs.append(num(x['amount'], 'cost'))
    monthly = revenue - sum(costs, Decimal(0))
    target = None if data.get('target_monthly_net') is None else num(data['target_monthly_net'], 'target_monthly_net')
    resale_scenarios = []
    for x in rows(data.get('resale_scenarios', []), 'resale_scenarios'):
        fields(x, ('label','net_resale','after_months')); text(x['label'], 'resale label')
        resale = num(x['net_resale'], 'net_resale'); months = num(x['after_months'], 'after_months')
        resale_scenarios.append({'label': x['label'], 'net_resale': fmt(resale), 'after_months': fmt(months), 'cumulative_cash_result_if_assumptions_hold': fmt(monthly*months + resale-initial)})
    return {'calculator':'income_scenario', 'currency':data['currency'], 'basis':data['basis'], 'monthly_net_before_labor_and_unlisted_costs':fmt(monthly),
            'net_per_hour_before_labor':ratio(monthly,hours), 'cash_payback_months_excluding_resale':ratio(initial,monthly),
            'hours_for_target_at_same_observed_rate':ratio(target*hours,monthly) if target is not None else None,
            'resale_scenarios':resale_scenarios,
            'warnings':['收入必须来自用户账单或明确假设，不用历史回帖保证收入、投资额、保值或回本', '同一货币、同一观察期；点卡、维修、消耗、交易费等未列项及劳动机会成本会高估净收益', '目标工时按相同净时薪线性外推，不代表增加工时仍有相同收益；负利润没有有限回本期']}


OPERATIONS = {'upgrade_compare': compare_upgrade, 'comparables': comparables, 'gem_premium': gem_premium, 'ledger': ledger, 'target_gaps': target_gaps, 'income_scenario': income_scenario}


def _pairs(items):
    out = {}
    for k,v in items:
        if k in out: raise ValueError('Duplicate JSON key: ' + k)
        out[k]=v
    return out


def read_input(filename):
    path = Path(filename)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Input must be a regular UTF-8 JSON file up to 1 MB, not a symlink')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('Input must be a bounded regular file')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES: raise ValueError('Input too large')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs, parse_float=Decimal,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON is forbidden')))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('--kind',choices=tuple(OPERATIONS),required=True); parser.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        result=OPERATIONS[args.kind](read_input(args.input)); output=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as f: f.write(output)
        else: sys.stdout.write(output)
    except (ValueError, OSError, InvalidOperation, RecursionError, TypeError) as e:
        parser.error(str(e))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
