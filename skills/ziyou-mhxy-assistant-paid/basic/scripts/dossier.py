#!/usr/bin/env python3
"""Recompile one bounded, versioned decision dossier; never execute dossier text.

The dialogue host maintains the dossier. Players do not have to author JSON.
Only this module's fixed local calculators run; references cannot load files,
URLs, Python attributes, imports, or expressions. Saved results are never reused.
"""
from __future__ import annotations
import argparse
import copy
from decimal import Decimal
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import sys
try:
    from . import calculate, decisions as d, evidence, mechanics, plans, portfolio, resources, routes
except ImportError:
    import decisions as d
    import calculate, evidence, mechanics, plans, portfolio, resources, routes

SCHEMA = 'mhxy-dossier/v1'
COMPILED_SCHEMA = 'mhxy-dossier-compiled/v1'
COMPILER_VERSION = '1.2.3'
MAX_BYTES = 1_000_000
MAX_STEPS = 32
MAX_NODES = 30000
MAX_DEPTH = 40


def _equipment_optimize(value):
    """Adapt only documented numeric fields to the legacy Decimal interface.

    Dossier sources retain exact strings and never JSON floats. Numeric-looking
    names, source excerpts, IDs and dates remain text; no generic tree coercion.
    The equipment calculator still validates every field and its own bounds.
    """
    data = copy.deepcopy(value)
    def numeric(v):
        if isinstance(v, str):
            if len(v) > 32 or not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?', v):
                raise ValueError('Equipment numeric text must be an exact ordinary decimal with at most 6 places')
            return Decimal(v)
        return v
    def scalars(obj, names):
        if isinstance(obj, dict):
            for name in names:
                if name in obj: obj[name] = numeric(obj[name])
    def mapping(obj, name):
        if isinstance(obj, dict) and isinstance(obj.get(name), dict):
            obj[name] = {key: numeric(v) for key, v in obj[name].items()}
    scalars(data, ('budget', 'top_n'))
    mapping(data, 'weights'); mapping(data.get('baseline'), 'stats')
    for option in data.get('options', []) if isinstance(data.get('options'), list) else []:
        scalars(option, ('price', 'fees'))
        mapping(option, 'deltas'); mapping(option, 'measured_stats')
    scalars(data.get('character'), ('level',))
    scalars(data.get('constraints'), ('max_changes',))
    for key in ('min_stats', 'max_stats'): mapping(data.get('constraints'), key)
    for key in ('budget_scenarios', 'weight_scenarios'):
        for scenario in data.get(key, []) if isinstance(data.get(key), list) else []:
            scalars(scenario, ('budget',)); mapping(scenario, 'weights')
    return calculate.calculate(data)


EQUIPMENT_INPUT_LIMITS = [
    '装备比较的currency必须与档案一致；人物server如填写也须一致，不自动换汇或重标区服。',
    '装备旧接口的source是自由文字，没有结构化报价日期；档案as_of只是比较日期，max_age_days不自动核验这些报价。购买前须逐项确认原报价日期、来源、挂牌/成交性质和全部费用。',
    '只比较同状态完整人物面板或相对同部位的净变化；相加模型不验证穿戴资格、套装联动、实战收益或目标效果。',
    '本步骤预算独立，未自动扣除联合计划预留或其他项目，不自动生成portfolio项目或扣库存；完整预算须由宿主明确接入并复核。',
]

# The names below are data labels, not import strings. No dynamic loading.
CALCULATORS = {
    'equipment.optimize': _equipment_optimize,
    'resources.cultivation': resources.cultivation,
    'resources.gems': resources.gems,
    'plans.gem_upgrade': plans.gem_upgrade,
    'plans.training_mix': plans.training_mix,
    'portfolio': portfolio.plan,
    'routes.gold_pill': routes.cultivation_items,
    'routes.pet_fruit': routes.pet_cultivation,
    'routes.cap_route': routes.cap_route,
    'routes.gem_eligibility': routes.gem_feasibility,
    'routes.star_gem': routes.star_gems,
    'mechanics.scene_leveling': mechanics.scene_leveling,
    'mechanics.repair_guidance': mechanics.repair_guidance,
    'mechanics.xiuyedian_guidance': mechanics.xiuyedian_guidance,
    'mechanics.gem_operations': mechanics.gem_operations,
    'mechanics.focus': mechanics.focus,
    'mechanics.guild_skill': mechanics.guild_skill,
    'mechanics.pet_stage': mechanics.pet_stage,
    'mechanics.pet_repair': mechanics.pet_repair,
    'mechanics.cage_eligibility': mechanics.cage_eligibility,
    'decisions.upgrade_compare': d.compare_upgrade,
    'decisions.comparables': d.comparables,
    'decisions.gem_premium': d.gem_premium,
    'decisions.ledger': d.ledger,
    'decisions.target_gaps': d.target_gaps,
    'decisions.income_scenario': d.income_scenario,
}
CONTEXT_KINDS = {'plans.gem_upgrade', 'plans.training_mix', 'portfolio',
                 'mechanics.guild_skill', 'mechanics.pet_stage',
                 'decisions.upgrade_compare', 'decisions.comparables', 'decisions.gem_premium'}
RULESET_KINDS = {k for k in CALCULATORS if k.startswith('mechanics.')}
ID_PATTERN = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
LIMITS = [
    '来源绑定只验证结构、类型和同一事实值，不证明原文语义、对象、单位或日期真实；宿主须复核。',
    '所有价格为手工资料；本档案没有联网核价、成交或游戏操作。',
    '只重算列出的步骤和目标；未知不当作0，过期和条件资料不变成当前保证。',
    '原始规则限制仍在每步结果中；日期固定为档案核价日，重开不会自动改为今天。',
]


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def _bounded(value, max_nodes=MAX_NODES):
    count = 0
    def walk(v, depth):
        nonlocal count
        count += 1
        if count > max_nodes or depth > MAX_DEPTH:
            raise ValueError('Dossier exceeds bounded depth/node limits')
        if isinstance(v, dict):
            for k, child in v.items():
                if not isinstance(k, str) or len(k) > 500 or '\x00' in k:
                    raise ValueError('Invalid object key')
                walk(child, depth + 1)
        elif isinstance(v, list):
            for child in v: walk(child, depth + 1)
        elif v is None or isinstance(v, bool): pass
        elif isinstance(v, int):
            if abs(v) > 9007199254740991: raise ValueError('Large numbers must use decimal strings')
        elif isinstance(v, str):
            if len(v) > 20000 or '\x00' in v: raise ValueError('Text exceeds bounded string limit')
        else:
            raise ValueError('Use integers or exact decimal strings, never JSON floats')
    walk(value, 0)


def _measure(value):
    """Count an existing bounded tree without materializing another JSON string."""
    if isinstance(value, dict):
        rows = [_measure(v) for v in value.values()]
        return (1 + sum(r[0] for r in rows),
                2 + max(0, len(rows) - 1) + sum(len(json.dumps(k, ensure_ascii=False).encode('utf-8')) + 1 for k in value)
                + sum(r[1] for r in rows), 1 + max((r[2] for r in rows), default=-1))
    if isinstance(value, list):
        rows = [_measure(v) for v in value]
        return 1 + sum(r[0] for r in rows), 2 + max(0, len(rows) - 1) + sum(r[1] for r in rows), 1 + max((r[2] for r in rows), default=-1)
    return 1, len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')), 0


def _price_conditions(value, context, step_id, path=''):
    conditions = []
    if isinstance(value, dict):
        standard = {'amount', 'currency', 'server', 'observed_on', 'source', 'kind'} <= set(value)
        route = {'unitPrice', 'currency', 'server', 'date', 'source', 'kind'} <= set(value)
        if standard or route:
            observed = value['observed_on' if standard else 'date']
            age = (d.day(context['as_of'], 'as_of') - d.day(observed, 'quote date')).days
            stale = age > context['max_age_days']
            if stale or value['kind'] in ('sold', 'estimate'):
                conditions.append({'step_id': step_id, 'path': path, 'kind': value['kind'],
                                   'observed_on': observed, 'stale': stale,
                                   'meaning': '过期报价/规则依据，不能当作当前可购' if stale else '历史成交/估算或规则算术，仅支持条件计算，不证明当前成交'})
        for key in sorted(value): conditions.extend(_price_conditions(value[key], context, step_id, path + '/' + _escape(key)))
    elif isinstance(value, list):
        for i, v in enumerate(value): conditions.extend(_price_conditions(v, context, step_id, path + '/' + str(i)))
    return conditions


def _id(value, label):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(label + ' must be an ASCII identifier (1–64 characters)')
    return value


def _tokens(path):
    if not isinstance(path, str) or len(path) > 500 or (path and not path.startswith('/')):
        raise ValueError('Reference path must be a bounded JSON pointer')
    if not path: return []
    result = []
    for token in path[1:].split('/'):
        if re.search(r'~(?![01])', token): raise ValueError('Invalid JSON pointer escape')
        result.append(token.replace('~1', '/').replace('~0', '~'))
    return result


def pointer(value, path):
    for token in _tokens(path):
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', token) or len(token) > 6:
                raise ValueError('Invalid list reference')
            i = int(token)
            if i >= len(value): raise ValueError('Reference path does not exist: ' + path)
            value = value[i]
        elif isinstance(value, dict) and token in value: value = value[token]
        else: raise ValueError('Reference path does not exist: ' + path)
    return value


def _escape(key):
    return str(key).replace('~', '~0').replace('/', '~1')


def _ref(value):
    if not isinstance(value, dict) or '$ref' not in value: return None
    d.fields(value, ('$ref',), ('unit',))
    if not isinstance(value['$ref'], str): raise ValueError('$ref must be text')
    text = value['$ref']
    prefix, separator, tail = text.partition(':')
    if separator and prefix in ('snapshot', 'context'):
        scope, path, step = prefix, tail, None
    elif prefix == 'step' and ':' in tail:
        scope = prefix; step, path = tail.split(':', 1); _id(step, 'Referenced step')
    else: raise ValueError('Only snapshot:, context:, and step:ID: references are allowed')
    _tokens(path)
    if 'unit' in value: d.text(value['unit'], 'reference unit', 80)
    return scope, step, path


def _walk_refs(value):
    ref = _ref(value)
    if ref is not None:
        yield ref
    elif isinstance(value, dict):
        for k in sorted(value):
            if k.startswith('$'): raise ValueError('Unknown reserved reference operator: ' + k)
            yield from _walk_refs(value[k])
    elif isinstance(value, list):
        for v in value: yield from _walk_refs(v)


def _context(value):
    ctx = d.context(value)
    ruleset = value.get('ruleset', 'pc_time')
    if ruleset != 'pc_time': raise ValueError('Dossier ruleset must be pc_time')
    return {'server': ctx['server'], 'currency': ctx['currency'], 'as_of': value['as_of'],
            'max_age_days': ctx['age'], 'ruleset': ruleset}


def _check_context(value, shared):
    # Missing optional defaults inherit; explicit defaults may not weaken policy.
    d.fields(value, ('server', 'currency', 'as_of'), ('max_age_days', 'ruleset'))
    merged = dict(shared, **value)
    if _context(merged) != shared: raise ValueError('Calculation context differs from shared dossier context')
    return copy.deepcopy(shared)


def _bind_context(value, shared):
    if isinstance(value, list): return [_bind_context(v, shared) for v in value]
    if not isinstance(value, dict): return value
    value = {k: _bind_context(v, shared) for k, v in value.items()}
    for key in ('context', 'cost_context'):
        if key in value and value[key] is not None:
            value[key] = _check_context(value[key], shared)
    for key in ('server', 'currency'):
        if key in value and value[key] != shared[key]:
            raise ValueError('Implicit ' + key + ' mismatch with dossier context')
    if 'ruleset' in value and value['ruleset'] != shared['ruleset']:
        raise ValueError('Implicit ruleset mismatch with dossier context')
    # Route quotes otherwise fall back to datetime.now(). Never do that here.
    if {'unitPrice', 'server', 'date', 'currency', 'source', 'kind'} <= set(value):
        if value.get('asOf', shared['as_of']) != shared['as_of']:
            raise ValueError('Route quote asOf differs from shared as_of')
        if value.get('maxAgeDays', shared['max_age_days']) != shared['max_age_days']:
            raise ValueError('Route quote age policy differs from shared context')
        value['asOf'] = shared['as_of']; value['maxAgeDays'] = shared['max_age_days']
    return value


def _prepare_input(kind, value, shared):
    if not isinstance(value, dict): raise ValueError('Calculator input must resolve to an object')
    value = _bind_context(copy.deepcopy(value), shared)
    if kind == 'equipment.optimize': value.setdefault('currency', shared['currency'])
    if kind in CONTEXT_KINDS: value.setdefault('context', copy.deepcopy(shared))
    if kind == 'mechanics.focus': value.setdefault('cost_context', copy.deepcopy(shared))
    if kind in RULESET_KINDS: value.setdefault('ruleset', shared['ruleset'])
    if kind in ('mechanics.repair_guidance', 'mechanics.pet_repair', 'mechanics.gem_operations', 'mechanics.cage_eligibility'):
        if value.get('as_of', shared['as_of']) != shared['as_of']:
            raise ValueError('Repair or mechanics as_of differs from shared dossier date')
        value.setdefault('as_of', shared['as_of'])
    if kind == 'mechanics.xiuyedian_guidance':
        if mechanics.grounded.timestamp(value.get('as_of'), 'as_of').date().isoformat() != shared['as_of']:
            raise ValueError('Pet exchange timestamp differs from shared dossier UTC date')
    if (kind.startswith(('resources.', 'routes.')) or kind in ('plans.gem_upgrade', 'plans.training_mix')) and shared['currency'] != '两':
        raise ValueError('This calculator has fixed 两 units; use a separate dossier for another currency')
    if kind == 'decisions.ledger' and not set(value.get('budgets', {})) <= {shared['currency']}:
        raise ValueError('Ledger budgets must use the shared dossier currency')
    return value


# Known numeric output contracts. Unlisted outputs remain data, not invented units.
OUTPUT_UNITS = {
    'equipment.optimize': {'/budget': '$currency', '/best/price': '$currency', '/best/remaining_budget': '$currency', '/baseline/price': '$currency'},
    'resources.cultivation': {'/costLiang': '两', '/costPerPurchaseLiang': '两', '/requiredXp': 'XP', '/materialsConsumed': '资材', '/currentLevel': '级', '/targetLevel': '级'},
    'resources.gems': {'/quoteTotalLiang': '两', '/baseUnitsLowerBound': '颗', '/currentForge': '锻', '/targetForge': '锻'},
    'plans.gem_upgrade': {'/self_upgrade/cash_outlay': '两', '/self_upgrade/economic_cost': '两', '/self_upgrade/owned_material_opportunity_cost': '两', '/self_upgrade/cash_remaining': '两'},
    'plans.training_mix': {'/best_mix/cost_liang': '两', '/best_mix/ordinary_materials': '资材', '/best_mix/items': '颗'},
    'mechanics.repair_guidance': {'/restoration_from_matching_preview': '耐久', '/conditional_qiankun_restoration_if_legacy_rule_applies': '耐久', '/restoration_under_verified_cap': '耐久'},
    'mechanics.scene_leveling': {'/target_pet_level': '级', '/current_pet_level': '级', '/character_level': '级'},
    'mechanics.xiuyedian_guidance': {'/target_pet_level': '级', '/current_pet_level': '级', '/character_level': '级', '/preview_assessment/unspent_points_after_this_batch': '修业点'},
    'mechanics.guild_skill': {'/totals/money_liang': '两', '/totals/experience': 'XP', '/totals/materials': '资材', '/totals/contribution_spent': '帮贡'},
    'mechanics.pet_stage': {'/new_pill_cash_liang': '两', '/new_pills_to_buy': '颗', '/natural_sequential_hours': '小时'},
    'routes.pet_fruit': {'/item/costLiang': '两', '/item/itemCount': '颗'},
    'routes.gold_pill': {'/item/costLiang': '两', '/ordinary/costLiang': '两', '/item/itemCount': '颗'},
    'routes.star_gem': {'/directPurchaseCostLiang': '两', '/baseUnitsLowerBound': '颗'},
    'project.cultivation': {'/calculation/costLiang': '两', '/calculation/materialsConsumed': '资材', '/calculation/requiredXp': 'XP'},
    'portfolio': {'/minimum_target_cash_before_money_constraints': '$currency', '/budget': '$currency', '/spendable': '$currency'},
}


def _expected_unit(path, context):
    last = _tokens(path)[-1] if path else ''
    if last in ('amount', 'price', 'fees', 'budget', 'reserve', 'sunk_cost', 'unitPrice', 'money_liang', 'net_resale', 'target_monthly_net'):
        return context['currency']
    if last in ('currentForge', 'targetForge'): return '锻'
    if last in ('currentProgressXp', 'confirmedItemXp', 'item_xp', 'current_xp', 'expected_xp', 'xp_remaining_to_target'): return 'XP'
    if last in ('current_durability', 'maximum_durability', 'restored_durability'): return '耐久'
    if last == 'owned_points' or path.endswith('/preview_batch/points'): return '修业点'
    if last in ('currentLevel', 'targetLevel', 'equipmentLevel', 'characterLevel', 'current_level', 'target_level', 'current_pet_level', 'target_pet_level', 'pet_level', 'character_level', 'equipment_level', 'material_level', 'ordinary_skill_level'): return '级'
    return None


def _engine_manifest():
    root = Path(__file__).resolve().parents[1]
    names = ['scripts/' + name + '.py' for name in
             ('dossier', 'calculate', 'decisions', 'evidence', 'grounded', 'mechanics', 'plans', 'portfolio', 'resources', 'routes', 'scene_leveling', 'repair_routes')]
    names.extend(('references/rule-sources.json', 'references/grounded-rule-sources.json', 'references/pet-scene-ranges.json', 'references/repair-route-sources.json'))
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def source_dossier(value):
    _bounded(value, MAX_NODES * 8)
    if isinstance(value, dict) and value.get('schema') == COMPILED_SCHEMA:
        d.fields(value, ('schema', 'dossier', 'compilation'))
        # Deliberately ignore the complete saved compilation, including its hashes.
        value = value['dossier']
    _bounded(value)
    if len(canonical_bytes(value)) > MAX_BYTES: raise ValueError('Source dossier exceeds 1 MB')
    return copy.deepcopy(value)


def _validate(data):
    if _measure(data)[1] > MAX_BYTES:
        raise ValueError('Source dossier exceeds 1 MB; split the decision into smaller dossiers')
    d.fields(data, ('schema', 'id', 'revision', 'parent_sha256', 'title', 'context', 'sources', 'facts', 'snapshot', 'steps'))
    if data['schema'] != SCHEMA: raise ValueError('Unsupported dossier schema')
    _id(data['id'], 'Dossier id'); d.text(data['title'], 'title', 200)
    if type(data['revision']) is not int or not 1 <= data['revision'] <= 1000000:
        raise ValueError('revision must be a positive bounded integer')
    parent = data['parent_sha256']
    if (data['revision'] == 1 and parent is not None) or (data['revision'] > 1 and (not isinstance(parent, str) or not re.fullmatch(r'[0-9a-f]{64}', parent))):
        raise ValueError('Revision 1 has null parent; later revisions require parent_sha256')
    context = _context(data['context'])
    facts = {}; basic = []
    for f in d.rows(data['facts'], 'facts'):
        d.fields(f, ('id', 'label', 'scope', 'status', 'value', 'evidence', 'unit'), ('assumption',))
        _id(f['id'], 'Fact id'); d.text(f['unit'], 'fact unit', 80)
        if f['id'] in facts: raise ValueError('Duplicate fact id')
        facts[f['id']] = f
        basic.append({k: v for k, v in f.items() if k != 'unit'})
    ledger = evidence.validate_ledger({'sources': data['sources'], 'facts': basic})
    snapshot_units = {}; bindings = []; used = set()
    def snapshot(v, path):
        if isinstance(v, dict) and '$fact' in v:
            d.fields(v, ('$fact',), ('unit',))
            fid = _id(v['$fact'], 'Fact reference')
            if fid not in facts: raise ValueError('Unknown snapshot fact: ' + fid)
            f = facts[fid]; used.add(fid)
            if 'unit' in v and v['unit'] != f['unit']: raise ValueError('Snapshot fact unit mismatch')
            snapshot_units[path] = f['unit']
            bindings.append({'path': path, 'fact_id': fid, 'unit': f['unit'], 'status': f['status']})
            return f['value']
        if isinstance(v, dict):
            if any(k.startswith('$') for k in v): raise ValueError('Snapshot permits only $fact references')
            return {k: snapshot(v[k], path + '/' + _escape(k)) for k in sorted(v)}
        if isinstance(v, list): return [snapshot(x, path + '/' + str(i)) for i, x in enumerate(v)]
        return v
    resolved = snapshot(data['snapshot'], '')
    if not isinstance(resolved, dict): raise ValueError('snapshot must be an object')
    steps = {}
    if not isinstance(data['steps'], list) or not 1 <= len(data['steps']) <= MAX_STEPS:
        raise ValueError('Dossier needs 1–32 declared steps')
    for s in data['steps']:
        d.fields(s, ('id', 'kind', 'input'))
        ident = _id(s['id'], 'Step id')
        if ident in steps: raise ValueError('Duplicate step id')
        if not isinstance(s['kind'], str): raise ValueError('Calculator kind must be text')
        if s['kind'] not in CALCULATORS and s['kind'] not in ('project.gem_upgrade', 'project.cultivation'):
            raise ValueError('Calculator kind is not allowlisted: ' + str(s['kind']))
        steps[ident] = s
    dependencies = {}
    for ident, s in steps.items():
        refs = list(_walk_refs(s['input']))
        deps = {other for scope, other, path in refs if scope == 'step'}
        if not deps <= set(steps): raise ValueError('Missing referenced calculation step')
        # Structural references to source data are checked even if a later step blocks.
        for scope, _, path in refs:
            if scope in ('snapshot', 'context'): pointer(resolved if scope == 'snapshot' else context, path)
        dependencies[ident] = deps
    order = []; visited = set(); active = set()
    def visit(ident):
        if ident in active: raise ValueError('Cyclic calculation references')
        if ident in visited: return
        active.add(ident)
        for dep in sorted(dependencies[ident]): visit(dep)
        active.remove(ident); visited.add(ident); order.append(ident)
    for ident in sorted(steps): visit(ident)
    return context, facts, ledger, resolved, snapshot_units, bindings, sorted(set(facts) - used), steps, dependencies, order


def _project_metadata(p):
    d.fields(p, ('id', 'label', 'system', 'goals', 'eligibility', 'effect_basis', 'requires', 'conflicts'), ('route_group',))
    if p['eligibility'] not in ('confirmed', 'unknown', 'ineligible'): raise ValueError('Invalid project eligibility')
    for key in ('id', 'label', 'system', 'effect_basis'): d.text(p[key], key)
    for key in ('goals', 'requires', 'conflicts'): portfolio.identifiers(p[key], key)
    return copy.deepcopy(p)


def _cultivation_project(data, context):
    """Ordinary cultivation only: preserve fixed-rule cash, resources and evidence."""
    d.fields(data, ('calculation', 'project', 'material_resource'))
    resource_id = d.text(data['material_resource'], 'guild material resource id', 80)
    option = _project_metadata(data['project'])
    raw = _prepare_input('resources.cultivation', data['calculation'], context)
    result = resources.cultivation(raw)
    amount = result['costLiang']; materials = result['materialsConsumed']
    checked = result['checkedDate']
    if checked > context['as_of']:
        raise ValueError('Rule-check date is after dossier as_of; historical rule availability is not verified')
    quote = {'amount': amount, 'currency': '两', 'server': context['server'],
             'observed_on': context['as_of'], 'kind': 'estimate',
             'source': '规则算术 resources.cultivation；日期是档案估算编制日，不是市场询价或新规则核验；规则核验日' + checked + '；' + ', '.join(c['url'] for c in result['citations'])}
    option.update(costs=[] if amount == '0' else [{'label': '普通修炼规则金钱消耗（条件算术）', 'quantity': '1', 'quote': quote}],
                  consumes={} if materials == '0' else {resource_id: materials},
                  owned_materials=[] if materials == '0' else [{'label': '帮派资材机会成本未估', 'quantity': materials, 'quote': None}])
    return {'calculation': result, 'option': option, 'resource_units': {resource_id: '资材'},
            'cost_basis': {'kind': 'computed_rule_cost', 'rule_checked_on': checked, 'prepared_as_of': context['as_of'],
                           'citations': result['citations'], 'market_quote': False,
                           'portfolio_encoding': 'estimate; observed_on is the dossier estimate-preparation date, not a market observation or fresh rule verification'},
            'cost_provenance': 'Cash and guild-material consumption recomputed from current level, XP progress and target in this revision',
            'limits': ['仅普通帮派修炼，不套用快速/道具/降修等其他路线；角色、帮龄、帮贡门槛与开放资格另核',
                       '资材是独立资源消耗，不是两；帮贡门槛不计作消费；未估资材机会成本时经济成本保持未知',
                       'portfolio兼容行标estimate；日期仅是本档案估算编制日；原规则核验日与第一方依据保留，不冒充新规则核验或市场询价',
                       'material_resource必须标识同一帮派/时点可用资材；已达目标必须来自用户事实，不由上次推荐自动推断']}


def _gem_project(data, context):
    """A fixed adapter, not a user-defined formula or scalar cost copy."""
    d.fields(data, ('calculation', 'project', 'stock_resources'))
    p = _project_metadata(data['project'])
    if not isinstance(data['stock_resources'], dict): raise ValueError('stock_resources must map grades to shared resource ids')
    if len(set(data['stock_resources'].values())) != len(data['stock_resources']):
        raise ValueError('Distinct gem grades need distinct shared resource ids')
    for grade, rid in data['stock_resources'].items():
        if not re.fullmatch(r'[1-9]|1[0-9]|20', grade): raise ValueError('Invalid shared gem grade')
        d.text(rid, 'shared stock resource id', 80)
    raw = _prepare_input('plans.gem_upgrade', data['calculation'], context)
    result = plans.gem_upgrade(raw)
    option = copy.deepcopy(p); option.update(costs=copy.deepcopy(raw['fees']), owned_materials=[], consumes={})
    for row in result['bill']:
        line = {'label': row['grade'] + '级宝石', 'quantity': '1', 'quote': copy.deepcopy(row['quote'])}
        if row['from_stock'] == '1':
            grade = row['grade']
            if grade not in data['stock_resources']: raise ValueError('Every used gem stock grade needs a shared resource id')
            option['consumes'][data['stock_resources'][grade]] = '1'
            option['owned_materials'].append(line)
        else: option['costs'].append(line)
    if result['eligibility']['status'] != 'eligible': option['eligibility'] = 'ineligible'
    # Validate metadata/cash using the same portfolio contract, without making up goals.
    for key in ('id', 'label', 'system', 'effect_basis'): d.text(option[key], key)
    for key in ('goals', 'requires', 'conflicts'): portfolio.identifiers(option[key], key)
    return {'calculation': result, 'option': option,
            'resource_units': {rid: '颗' for rid in data['stock_resources'].values()},
            'cost_provenance': 'Costs, opportunity lines and inventory consumption regenerated from this revision’s gem bill; no stored project total is read',
            'limits': ['项目目标效果、其他资格及费用完整性由用户/宿主确认；适配器不推断战斗达标',
                       '共享库存id必须对应同一种、同等级的实物；记录库存时须与snapshot中同一事实引用绑定']}


def compile_dossier(value):
    data = source_dossier(value)
    context, facts, ledger, snapshot, snapshot_units, bindings, unused, steps, dependencies, order = _validate(data)
    results = {}; receipts = {}; rows = []; size_cache = {}
    initial = _measure({'dossier': data, 'snapshot': snapshot, 'ledger': ledger, 'bindings': bindings})
    aggregate = {'nodes': initial[0], 'bytes': initial[1]}
    def aggregate_charge(nodes, size):
        if aggregate['nodes'] + nodes > MAX_NODES * 8 or aggregate['bytes'] + size > MAX_BYTES * 8:
            raise ValueError('Expanded compilation exceeds aggregate node/byte budget')
        aggregate['nodes'] += nodes; aggregate['bytes'] += size
    for ident in order:
        step = steps[ident]; refs_used = []; fact_ids = set(); units = {}; bound_facts = {}
        blocked = [dep for dep in sorted(dependencies[ident]) if receipts[dep]['status'] == 'blocked']
        expanded = {'nodes': 0, 'bytes': 0}
        def charge(nodes, size, depth, dest):
            if expanded['nodes'] + nodes > MAX_NODES or expanded['bytes'] + size > MAX_BYTES or depth + len(_tokens(dest)) > MAX_DEPTH:
                raise ValueError('Reference expansion exceeds input node/byte/depth budget before copying')
            aggregate_charge(nodes, size)
            expanded['nodes'] += nodes; expanded['bytes'] += size
        def resolve(v, dest=''):
            ref = _ref(v)
            if ref is not None:
                scope, dep, path = ref
                source = snapshot if scope == 'snapshot' else context if scope == 'context' else results[dep]
                selected = pointer(source, path)
                cache_key = (scope, dep, path)
                if cache_key not in size_cache: size_cache[cache_key] = _measure(selected)
                charge(*size_cache[cache_key], dest)
                got = copy.deepcopy(selected); unit = None
                if scope == 'snapshot':
                    for b in bindings:
                        if b['path'] == path or b['path'].startswith(path + '/'):
                            fact_ids.add(b['fact_id'])
                            units[dest + b['path'][len(path):]] = b['unit']
                            bound_facts[dest + b['path'][len(path):]] = b['fact_id']
                    unit = snapshot_units.get(path)
                elif scope == 'step':
                    fact_ids.update(receipts[dep]['fact_ids'])
                    for out_path, known_unit in OUTPUT_UNITS.get(steps[dep]['kind'], {}).items():
                        if known_unit == '$currency': known_unit = context['currency']
                        if out_path == path or out_path.startswith(path + '/'):
                            units[dest + out_path[len(path):]] = known_unit
                    unit = units.get(dest)
                elif path == '/currency': unit = '币种'
                if 'unit' in v and v['unit'] != unit:
                    raise ValueError('Reference unit assertion cannot be verified or mismatches: ' + v['$ref'])
                if scope == 'step' and not isinstance(got, (dict, list)):
                    expected = _expected_unit(dest, context)
                    if expected is not None and unit != expected:
                        raise ValueError('Numeric output reference needs a known matching unit contract at ' + dest)
                    if (_tokens(dest) and _tokens(dest)[-1] in ('amount', 'price', 'unitPrice')) or re.search(r'(?:^|/)quotes/[0-9]+$', dest):
                        raise ValueError('Do not wrap computed totals as fresh quotes; use a fixed project adapter or retain original cost lines')
                refs_used.append({'reference': v['$ref'], 'destination': dest, 'sha256': digest(got), 'unit': unit})
                return got
            if isinstance(v, dict):
                overhead = 2 + max(0, len(v) - 1) + sum(len(json.dumps(k, ensure_ascii=False).encode('utf-8')) + 1 for k in v)
                charge(1, overhead, 0, dest)
                return {k: resolve(v[k], dest + '/' + _escape(k)) for k in sorted(v)}
            if isinstance(v, list):
                charge(1, 2 + max(0, len(v) - 1), 0, dest)
                return [resolve(x, dest + '/' + str(i)) for i, x in enumerate(v)]
            charge(*_measure(v), dest)
            return v
        receipt = {'id': ident, 'kind': step['kind'], 'depends_on': sorted(dependencies[ident]),
                   'status': 'blocked' if blocked else 'compiled', 'fact_ids': [], 'references': [],
                   'resolved_input': None, 'input_sha256': None, 'result': None, 'result_sha256': None,
                   'conditions': [], 'price_conditions': [], 'blockers': []}
        if blocked:
            for dep in blocked: fact_ids.update(receipts[dep]['fact_ids'])
            receipt['blockers'] = ['Upstream step is blocked: ' + dep for dep in blocked]
        else:
            resolved = resolve(step['input'])
            for path, unit in units.items():
                expected = _expected_unit(path, context)
                if expected is not None and unit != expected:
                    raise ValueError('Reference unit mismatch at ' + ident + path + ': ' + unit + ' vs ' + expected)
            resolved = _prepare_input(step['kind'], resolved, context)
            if step['kind'] == 'portfolio':
                pool_facts = {}
                for rid in resolved.get('available_resources', {}):
                    fid = bound_facts.get('/available_resources/' + _escape(rid))
                    if fid is not None:
                        if fid in pool_facts and pool_facts[fid] != rid:
                            raise ValueError('Same stock fact funds multiple resource pools; reuse one resource id: ' + fid)
                        pool_facts[fid] = rid
                resource_units = {}
                for dep in sorted(dependencies[ident]):
                    for rid, unit in results[dep].get('resource_units', {}).items():
                        if rid in resource_units and resource_units[rid] != unit:
                            raise ValueError('Shared resource id has incompatible units: ' + rid)
                        resource_units[rid] = unit
                        supplied = units.get('/available_resources/' + _escape(rid))
                        if supplied is not None and supplied != unit:
                            raise ValueError('Shared resource stock unit mismatch: ' + rid)
            _bounded(resolved)
            prepared_size = _measure(resolved)
            aggregate_charge(max(0, prepared_size[0] - expanded['nodes']), max(0, prepared_size[1] - expanded['bytes']))
            receipt['resolved_input'] = resolved; receipt['input_sha256'] = digest({'context': context, 'parameters': resolved})
            try:
                if step['kind'] == 'project.gem_upgrade': result = _gem_project(resolved, context)
                elif step['kind'] == 'project.cultivation': result = _cultivation_project(resolved, context)
                else: result = CALCULATORS[step['kind']](resolved)
            except (ValueError, TypeError) as error:
                if not any(facts[f]['status'] in ('unknown', 'conflicting') for f in fact_ids):
                    raise ValueError('Step ' + ident + ': ' + str(error)) from None
                receipt['status'] = 'blocked'
                receipt['blockers'] = ['Unresolved facts prevent this calculation: ' + str(error)]
            else:
                _bounded(result, MAX_NODES * 2)
                result_size = _measure(result); aggregate_charge(result_size[0], result_size[1])
                receipt['price_conditions'] = _price_conditions(resolved, context, ident)
                if step['kind'] == 'equipment.optimize':
                    receipt['input_limits'] = list(EQUIPMENT_INPUT_LIMITS)
                if step['kind'] == 'project.cultivation':
                    receipt['price_conditions'].extend(_price_conditions(result['option'], context, ident, '/generated_option'))
                results[ident] = result; receipt['result'] = result; receipt['result_sha256'] = digest(result)
        receipt['fact_ids'] = sorted(fact_ids); receipt['references'] = refs_used
        receipt['conditions'] = [{'fact_id': f, 'status': facts[f]['status'], 'assumption': facts[f].get('assumption')}
                                 for f in sorted(fact_ids) if facts[f]['status'] != 'confirmed']
        inherited = [condition for dep in sorted(dependencies[ident]) for condition in receipts[dep]['price_conditions']]
        receipt['price_conditions'] = list({digest(condition): condition for condition in inherited + receipt['price_conditions']}.values())
        receipt['source_ids'] = sorted({e['source_id'] for f in fact_ids for e in facts[f]['evidence']})
        overhead = _measure({k: v for k, v in receipt.items() if k not in ('resolved_input', 'result')})
        aggregate_charge(overhead[0], overhead[1])
        receipts[ident] = receipt; rows.append(receipt)
    status = 'blocked' if any(r['status'] == 'blocked' for r in rows) else 'conditional' if any(r['conditions'] or r['price_conditions'] or r.get('input_limits') for r in rows) else 'compiled'
    result = {'schema': COMPILED_SCHEMA, 'dossier': data, 'compilation': {
        'compiler_version': COMPILER_VERSION, 'status': status, 'context': context,
        'input_sha256': digest(data), 'snapshot_sha256': digest(snapshot),
        'engine_files_sha256': _engine_manifest(), 'execution_order': order,
        'resolved_snapshot': snapshot, 'snapshot_bindings': bindings,
        'unused_fact_ids': unused, 'evidence': ledger, 'steps': rows,
        'warnings': LIMITS + ['非$fact的snapshot常量和步骤常量没有事实绑定；宿主必须复核，不能把复制的数值当成自动同步字段。']}}
    _bounded(result, MAX_NODES * 8)
    if len(json_text(result).encode('utf-8')) > MAX_BYTES * 8:
        raise ValueError('Compiled bundle exceeds 8 MB; split the decision into smaller dossiers')
    return result


def revise(value, *, facts=(), sources=(), snapshot=None, context=None, steps=None):
    """Pure revision helper. Upsert explicit facts; append sources; keep old input.

    The host records the user's new evidence with each changed fact. This helper
    cannot determine whether the source text actually means the stated value.
    """
    old = source_dossier(value); _validate(old)
    new = copy.deepcopy(old)
    updates = {}
    for fact in facts:
        if not isinstance(fact, dict) or 'id' not in fact: raise ValueError('Changed fact must be a complete fact object')
        fid = _id(fact['id'], 'Changed fact id')
        if fid in updates: raise ValueError('Duplicate fact update')
        updates[fid] = copy.deepcopy(fact)
        if len(updates) > d.MAX_ROWS: raise ValueError('Too many fact updates')
    existing = {f['id'] for f in old['facts']}
    new['facts'] = [updates.get(f['id'], f) for f in new['facts']]
    new['facts'].extend(f for fid, f in updates.items() if fid not in existing)
    new['sources'].extend(copy.deepcopy(list(sources)))
    if snapshot is not None: new['snapshot'] = copy.deepcopy(snapshot)
    if context is not None: new['context'] = copy.deepcopy(context)
    if steps is not None: new['steps'] = copy.deepcopy(steps)
    new['revision'] += 1; new['parent_sha256'] = digest(old)
    _bounded(new); _validate(new)
    return new


def _report_money(value, currency):
    return '未知' if value is None else str(value) + currency


def _report_linked_portfolios(row, steps):
    """Only a recorded whole-option reference establishes this budget handoff."""
    reference = 'step:' + row['id'] + ':/option'
    return [p['id'] for p in steps if p['kind'] == 'portfolio'
            and row['id'] in p['depends_on']
            and any(r['reference'] == reference and re.fullmatch(r'/options/[0-9]+', r['destination'])
                    for r in p['references'])]


def _report_price_limit(label, limit, currency):
    if limit is None:
        return label + '：未知，所需预算、费用或成本资料尚不完整'
    line = label + '：精确临界单价 ' + limit['exact_limit'] + currency
    if limit['nonnegative_quote_possible']:
        line += '；可填单价≤' + _report_money(limit['max_nonnegative_quote_at_6dp'], currency)
        line += '（按六位小数向下取整，且不超过接口单价上限）'
    else:
        line += '；临界价为负，不存在满足此条件的非负报价，降到0也不够'
    return line


def _report_gem(result, raw, currency, linked):
    money = lambda value: _report_money(value, currency)
    resource = result['resource_check']; eligibility = result['eligibility']
    states = {'eligible': '通过', 'ineligible': '不成立', 'unknown': '未知'}
    out = ['  ' + resource['gemName'] + '：' + resource['currentForge'] + '→' + resource['targetForge'] + '段；镶嵌规则 '
           + states.get(eligibility['status'], eligibility['status'])]
    out.extend('  资格条件：' + reason for reason in eligibility['reasons'])
    if 'characterLevelEligible' in eligibility:
        wearing = {True: '达到已核穿戴等级门槛', False: '未达穿戴等级门槛', None: '人物等级未给，穿戴等级资格未知'}
        out.append('  人物等级 ' + (eligibility['characterLevel'] or '未知')
                   + '；最低穿戴等级 ' + eligibility['minimumCharacterLevel']
                   + '；' + wearing[eligibility['characterLevelEligible']])
    if eligibility.get('wearingScope'):
        out.append('  穿戴条件：' + eligibility['wearingScope'])
    if not result['bill']:
        out.append('  逐级宝石清单为空：新增需求0颗、计划用库存0颗、待买0颗；本目标无新增锻数')
    else:
        out.append('  逐级宝石清单（计划数量，尚未采购或耗用库存）：')
        for bill in result['bill']:
            owned = raw.get('owned_stones', {}).get(bill['grade'], {}).get('quantity', 0)
            quote = bill['quote']
            out.append('    ' + bill['grade'] + '级' + resource['gemName'] + '：需要' + bill['required'] + '颗'
                       + '；库存现有' + str(owned) + '颗；计划用库存' + bill['from_stock'] + '颗；待买' + bill['to_buy'] + '颗'
                       + '；' + bill['cost_meaning'] + '单价 ' + money(None if quote is None else quote['amount']))
    for fee in raw.get('fees', []):
        out.append('  自升额外费用：' + fee['label'] + ' × ' + str(fee['quantity']) + '；单价 '
                   + money(None if fee['quote'] is None else fee['quote']['amount']))
    if result['budget'] is None:
        if linked:
            out.append('  预算口径：本步骤仅核项目成本；总预算、预留与分类上限由下游联合计划 '
                       + '、'.join(linked) + ' 核对。是否入选及组合现金是否够用，以该计划结果为准；未给本项目另行分配预算')
        else:
            out.append('  本步骤预算尚未提供；不能确认自升或先买成品的现金是否够用')
    else:
        afford = {True: '够用（仅金额检查）', False: '不足', None: '未知，成本尚不完整'}
        out.append('  本步骤预算 ' + money(result['budget']) + '；自升现金 ' + afford[result['self_upgrade']['cash_within_budget']]
                   + '；自升后预算余额 ' + money(result['self_upgrade']['cash_remaining']) + '（负数表示缺口）')
        if linked:
            out.append('  此为单项目预算检查；联合计划 ' + '、'.join(linked) + ' 还需检查预留、其他项目和分类上限')
        if result['comparison'] is not None:
            out.append('  成品先买现金相对本步骤预算：' + afford[result['replacement_upfront_within_budget']])
    if result['comparison'] is not None:
        if linked:
            out.append('  下游整项引用接入的是自升项目；此成品比较不会因该引用自动成为联合计划候选')
        out.append('  ' + _report_price_limit('成品购价的先买可负担上限（仅本步骤预算，扣除购入费用，不抵未到账卖旧款）',
                                             result['replacement_purchase_affordability_ceiling'], currency))
        if result['budget'] is not None and linked:
            out.append('  此购价上限未扣联合计划的预留，也未计其他项目或分类上限；不能据此认定整套方案可执行')
        if result['budget'] is None and linked:
            out.append('  上述单项目购价上限未单独计算；不能把联合计划总预算直接当成成品可用额度')
    unknown = result['single_unknown_quote_thresholds']
    if unknown is not None:
        out.append('  单项缺价：' + unknown['label'] + ' × ' + unknown['quantity']
                   + '；其余已知新增现金 ' + money(unknown['known_other_cash']))
        labels = [('within_budget', '使自升新增现金不超过本步骤预算'),
                  ('same_upfront_cash_as_replacement', '使自升新增现金不超过成品先买现金'),
                  ('same_net_cash_if_resale_occurs', '使自升新增现金不超过卖旧后成品条件净成本'),
                  ('same_economic_cost_if_resale_occurs', '使自升经济成本不超过卖旧后成品条件净成本')]
        for key, label in labels:
            out.append('    ' + _report_price_limit(label, unknown[key], currency))
        out.append('  临界线边界：' + unknown['limits'])
    out.append('  下一步：' + result['next_action'])
    return out


def _report_comparison(comparison, currency):
    money = lambda value: _report_money(value, currency)
    replacement = comparison['replacement']
    status = {'settled': '已成交到账', 'conditional': '条件卖出，尚未到账', 'unknown': '未知'}
    out = ['  替换先买现金 ' + money(replacement.get('upfront_cash_required'))
           + '；按录入卖旧净回款计算的条件净成本 ' + money(replacement.get('net_cost_if_resale_occurs')),
           '  卖旧净回款 ' + money(replacement.get('net_resale_proceeds'))
           + '；回款状态 ' + status.get(replacement.get('resale_status'), '未知')]
    if replacement.get('resale_status') != 'settled':
        out.append('  旧物尚未成交到账或回款未确认，不能用这笔卖旧款抵扣先买现金')
    quote = replacement.get('purchase_quote')
    out.append('  成品录入购价 ' + money(None if quote is None else quote['amount']) + '；先买现金另含购入费用')
    for key, label in [('purchase_fee_lines', '成品购入费用'), ('resale_fee_lines', '卖旧费用')]:
        for fee in replacement.get(key, []):
            out.append('  ' + label + '：' + fee['label'] + ' × ' + fee['quantity'] + '；小计 ' + money(fee['subtotal']))
    for key, label in [('replacement_purchase_break_even_cash', '卖旧后净现金与自升现金持平的成品购价'),
                       ('replacement_purchase_break_even_economic', '卖旧后经济成本与自升经济成本持平的成品购价')]:
        value = comparison.get(key)
        line = '  ' + label + '：' + money(value)
        if value is None:
            line += '；资料不足，不能确定改选价格'
        elif str(value).startswith('-'):
            line += '；临界价为负，不存在使替换成本不高于自升的非负购价'
        else:
            line += '；低于该价替换更低，等于持平，高于该价自升更低'
        out.append(line)
    out.append('  以上改选临界线仅在同一目标、资格、其余报价/费用不变且录入净回款实现时成立；不是先买现金上限，不解除过期报价或出售时间限制')
    eligibility = comparison.get('comparable_routes_eligibility', {})
    states = {'confirmed': '已确认', 'unknown': '未知', 'ineligible': '不成立', 'different_target': '目标不同'}
    if eligibility:
        out.append('  路线资格：自升 ' + states.get(eligibility.get('self_upgrade'), '未知')
                   + '；成品 ' + states.get(eligibility.get('replacement'), '未知'))
    equivalence = comparison.get('target_equivalence')
    if equivalence:
        out.append('  同目标核对：' + states.get(equivalence['status'], equivalence['status']) + '；' + equivalence['basis'])
    out.append('  两条路线需先确认达到用户同一目标；本计算不推断战斗等效')
    views = comparison.get('decision_views')
    if views:
        labels = {'upfront_cash': '立即现金比较', 'net_cash': '卖旧后净支出比较', 'economic_cost': '经济成本比较'}
        states = {'ready': '相关资料有效', 'conditional': '只作录入价格下的条件比较',
                  'stale': '相关报价过期，不能作为当前排序', 'missing': '所需金额缺失，不能排序',
                  'eligibility_unconfirmed': '资格或同目标未确认，不能排序'}
        for key, view in views.items():
            out.append('  ' + labels[key] + '：' + states[view['status']])
        if comparison.get('comparison_has_stale_quotes'):
            out.append('  过期影响仅限依赖该报价的结论；不依赖旧估值的有效立即现金比较仍可成立。以上保留金额和临界线可供条件复算，不把旧估值作为现价')
    elif comparison.get('comparison_has_stale_quotes'):
        out.append('  比较含过期报价，相关数字仅供条件复算；应逐结论核对所依赖的报价，不能据整体标记阻断独立现金结论')
    timing = comparison.get('resale_timing')
    if timing:
        out.append('  卖旧时间：最早 ' + (timing['not_before'] or '未知')
                   + '；' + ('须先取得替换物再卖旧物，不能先卖旧筹款' if timing['keep_until_replacement'] else '未设置先换后卖要求')
                   + '；依据：' + timing['basis'])
        out.append('  到解限日不代表已经卖出或到账，仍须实际成交后重算')
    return out


def _report_training_mix(result, raw):
    """Expose the existing exact mixed-route result without recomputing it."""
    ordinary = result['ordinary']
    out = ['  ' + ordinary['typeLabel'] + '：' + ordinary['currentLevel'] + '→' + ordinary['targetLevel']
           + '级；本级已有经验 ' + ordinary['currentProgressXp'] + 'XP；已确认上限 ' + ordinary['confirmedCap'] + '级',
           '  剩余经验需求 ' + ordinary['requiredXp'] + 'XP',
           '  全普通路线参照：' + ordinary['purchases'] + '次（每次10XP、' + ordinary['costPerPurchaseLiang']
           + '两）；新增现金 ' + ordinary['costLiang'] + '两；资材 ' + ordinary['materialsConsumed']
           + '；购入经验 ' + ordinary['purchasedXp'] + 'XP；算术余量 ' + ordinary['surplusXp'] + 'XP']
    mixed = result.get('best_mix')
    if mixed is not None:
        out.extend(['  本次组合：道具 ' + mixed['items'] + '颗 + 普通修炼 ' + mixed['ordinary_purchases'] + '次',
                    '  组合新增现金 ' + mixed['cost_liang'] + '两；普通部分资材 ' + mixed['ordinary_materials']
                    + '；组合算术余量 ' + mixed['surplus_xp'] + 'XP',
                    '  相比全普通路线少花 ' + mixed['saving_vs_all_ordinary'] + '两（只比录入现金成本）'])
    else:
        out.append('  道具报价缺失：组合数量、混合总价和节省额未知；全普通参照不是混合最省方案')
    status = result['status']
    if status == 'no_upgrade_needed':
        out.append('  当前目标已达到，新增需求为0；无需道具经验、报价或混用资格，不产生新采购或库存扣减')
    elif status == 'ordinary_only':
        out.append('  本次道具可用上限为0，只比较普通路线；无需道具经验或报价，不作混用资格判断')
    else:
        # Missing-price results omit these fields, but the active route has
        # already validated them before returning missing_quote.
        xp = result.get('item_xp', str(raw['item_xp']))
        evidence_text = result.get('item_xp_evidence', raw['item_xp_evidence'])
        eligibility = result.get('mixing_eligibility', raw['mixing_eligibility'])
        labels = {'confirmed': '用户确认可混用', 'unknown': '尚未确认', 'ineligible': '不满足混用资格'}
        out.append('  每颗道具经验 ' + xp + 'XP；依据：' + evidence_text + '；不从道具品质推断经验')
        out.append('  混用资格：' + labels[eligibility] + '；仍须同时满足普通修炼和道具的实际使用条件')
        if eligibility != 'confirmed':
            out.append('  资格未成立的混合组合仅供条件算术，不能按该组合采购或执行')
        if 'max_items' in result:
            out.append('  本轮枚举道具数上限 ' + result['max_items'] + '颗；同现金成本的道具颗数组合 '
                       + result['price_tied_counts'] + '种，已显示按原算法择出的组合')
        if 'max_items' in raw:
            out.append('  用户录入当期可用道具上限 ' + str(raw['max_items']) + '颗，仍须核对游戏内当期限制')
        else:
            out.append('  未录入当期可用道具上限；数学需求上限不证明实际库存、市场可购数量或每日可用次数')
        quote = result.get('item_quote')
        if quote is not None:
            out.append('  道具单价 ' + quote['amount'] + quote['currency'] + '；区服 ' + quote['server']
                       + '；原报价日期 ' + quote['observed_on'] + '；类型 ' + quote['kind'] + '；来源：' + quote['source'])
            if quote['stale']:
                out.append('  道具报价已过期，须更新真实报价后重算；旧日期不会因生成报告而刷新')
        if 'method' in result: out.append('  比较方法：' + result['method'])
    out.append('  普通路线资格（实际点修时核对）：人物等级≥' + ordinary['requiredCharacterLevel']
               + '；累计帮贡>' + ordinary['requiredContributionExclusive'] + '；入帮天数>'
               + ordinary['requiredGuildMembershipDaysExclusive'] + '；仍须本帮开放对应修炼，帮贡门槛不是消费')
    out.extend('  普通规则边界：' + note for note in ordinary.get('explanations', []))
    for citation in ordinary.get('citations', []):
        out.append('  普通规则来源：' + citation['title'] + ' ' + citation['url']
                   + '；包内原核验日 ' + citation['checkedDate'] + '（不是本轮重新核验或道具经验依据）')
    return out


def _report_grounded(result):
    """Expose actual guidance and unresolved questions in a saved readable dossier."""
    show = lambda value: '未知' if value is None else str(value)
    out = []
    calculator = result['calculator']
    if calculator in ('repair_guidance','pet_equipment_repair'):
        out.append('  修理分类：' + result['equipment_kind'] + '；方法：' + result['method'])
        out.append('  版本：时间服；规则快照 ' + result['rule_snapshot_date'] + '；资料核验 ' + result['knowledge_checked_date'])
        for route in result.get('method_choices',[]):
            out.append('  可选方法：' + route['label'] + '；状态：' + route['status'])
            out.extend('    要求：' + x for x in route['requirements'])
            out.extend('    手动步骤：' + x for x in route['steps'])
            out.append('    费用：' + route['cost'])
            out.extend('    边界：' + x for x in route['limitations'])
        if result.get('restoration_under_verified_cap') is not None:
            out.append('  按已核上限的条件恢复算术：' + result['restoration_under_verified_cap'] + '；不是已经修复')
        workflow = result.get('ordinary_repair_workflow')
        if workflow is not None:
            out.append('  非帮派普通修理地点：' + workflow['location'] + '；所需技能：' + show(workflow['required_skill']) + '；最低等级：' + show(result['ordinary_repair_skill_minimum']))
            labels = {'blocked_by_three_failures':'累计失败3次，停止此普通修理方法', 'self_repair_skill_too_low':'自身技能不足，停止自行普通修理', 'known_prerequisites_met_not_success_guaranteed':'已核技能/失败门槛满足，仍可能失败', 'check_missing_prerequisites':'还有条件待核，先看下方问题'}
            out.append('  自行普通修理条件状态：' + labels[workflow['status']])
            out.extend('  步骤：' + x for x in workflow['steps'])
            out.append('  备选边界：' + workflow['alternative_boundary'])
        blocked = result['blocked_by_three_failures']
        out.append('  三失败这一项：' + ('明确阻止本方法' if blocked is True else '本项不阻止，其他资格仍需核对' if blocked is False else '未明确确认，不能判定可用或被禁'))
        out.append('  已核名义恢复：' + show(result['nominal_durability_restored']) + '；同物品同材料同状态的当前预览：' + show(result['restoration_from_matching_preview']))
        if result['conditional_qiankun_restoration_if_legacy_rule_applies'] is not None:
            out.append('  仅在旧乾坤石规则适用时的恢复算术：' + result['conditional_qiankun_restoration_if_legacy_rule_applies'] + '；不是已发生修复')
        if result['observed_preview'] is not None:
            p = result['observed_preview']
            out.append('  预览原观察日 ' + p['observed_on'] + '；用户来源：' + p['source'] + '；与本次状态匹配：' + str(p['state_matches']))
        out.extend('  已知：' + fact for fact in result['facts'])
        if result['unknowns']: out.append('  未核项：' + '、'.join(result['unknowns']))
        out.extend('  来源冲突，先核对：' + x for x in result['source_conflicts'])
    elif calculator == 'pet_scene_leveling':
        out.append('  宝宝当前等级 ' + result['current_pet_level'] + '；目标等级 ' + result['target_pet_level'] + '；人物等级 ' + show(result['character_level']))
        for row in result['requested_scene_checks']:
            band = lambda values: '–'.join(str(v) for v in values)
            verdicts = {'player_band_does_not_match_input':'玩家等级不符合此行', 'outside_listed_pet_xp_range':'宝宝不在表列获经验区间', 'within_listed_full_xp_range':'宝宝在表列满经验区间', 'within_listed_xp_range_below_full':'宝宝可在表列范围获经验，但非满经验区间'}
            out.append('  ' + row['scene'] + '：玩家等级 ' + band(row['player_level_range']) + '；宝宝获经验 ' + band(row['xp_pet_level_range']) + '；满经验 ' + band(row['full_xp_pet_level_range']) + '；核对 ' + verdicts[row['verdict']])
        out.append('  当前满经验区间候选：' + '、'.join(x['scene'] for x in result['current_full_xp_options']))
        out.append('  仅表列等级覆盖示例（不代表最快/最省/场景准入）：')
        for segment in result['level_coverage_example']:
            out.append('    宝宝' + '–'.join(str(v) for v in segment['pet_level_segment']) + '级：' + segment['scene'])
        if result['conditional_full_xp_options']:
            out.append('  其他玩家档位条件候选：' + '、'.join(x['scene'] + '（玩家' + '–'.join(str(v) for v in x['player_level_range']) + '）' for x in result['conditional_full_xp_options']) + '；组队适用方式未核，不自动按队长等级选档')
        if result['uncovered_pet_level_ranges']:
            out.append('  表列覆盖缺口：' + str(result['uncovered_pet_level_ranges']))
        out.append('  目标实际可达、最优路线、总时长、总费用：未知')
        out.extend('  办法：' + x for x in result['guidance'])
        out.extend('  边界：' + x for x in result['limits'])
    elif calculator == 'xiuyedian_guidance':
        labels = {'blocked_under_24_hours':'尚不足24小时', '24_hour_gate_passed':'24小时这项已通过；不代表全部资格通过',
                  'unknown':'取得方法或时刻未确认', 'historical_rule_unconfirmed':'历史时点规则未确认',
                  'named_acquisition_restriction_not_established_for_other_methods':'该取得方法不在已核三种情形内，仍需客户端确认'}
        out.append('  召唤兽 ' + show(result['pet_id']) + '；当前等级 ' + show(result['current_pet_level']) + '；目标等级 ' + result['target_pet_level'])
        out.append('  修业点取得时间门槛：' + labels[result['acquisition_gate']])
        if result['earliest_time_from_supplied_acquisition'] is not None:
            out.append('  按输入时刻计算最早时间：' + result['earliest_time_from_supplied_acquisition'])
        p = result['preview_assessment']
        if p is not None:
            out.append('  单批预览：' + str(p['points']) + '点，显示' + str(p['expected_xp']) + 'XP；原观察时刻 ' + p['observed_at'] + '；用户来源：' + p['source'])
            if p['status'] == 'conditional_single_batch':
                out.append('  仅这一已观察批次通过条件核对；若实际执行，点数算术余量' + p['unspent_points_after_this_batch'] + '，尚未写成实际余额')
            else:
                out.append('  不按此旧预览确认消耗：' + '、'.join(p['blockers']))
        out.append('  最优开始等级、总点数、总现金：未知；不从单批预览外推')
        out.extend('  办法：' + fact for fact in result['guidance'])
    elif calculator == 'ordinary_gem_operations':
        eligible = result['eligibility']
        if eligible is not None:
            out.append('  所填镶嵌资格：' + eligible['status'] + '；新增各级宝石：' + '、'.join(eligible['requiredGrades']))
            out.extend('  不可行原因：' + x for x in eligible['reasons'])
        direct = result['direct_inlay']
        if direct is not None:
            out.append('  直接镶嵌地点：' + direct['location'] + '；材料：' + direct['materials'])
            out.extend('  操作：' + x for x in direct['steps'])
            out.extend('  ' + direct[k] for k in ('failure_answer', 'skill_answer'))
        synthesis = result['synthesis']
        if synthesis is not None:
            out.extend('  自行合成：' + text for text in synthesis['guidance'])
    out.extend('  下一问：' + question for question in result['next_questions'])
    for citation in result['citations']:
        out.append('  规则来源：' + citation['url'] + '；页面日期 ' + show(citation['published_on'])
                   + '；生效/测试日期 ' + show(citation['effective_on']) + '；全服日期 ' + show(citation.get('all_server_effective_on')) + '；范围 ' + citation['source_scope']
                   + '；包内核验日 ' + citation['checked_date'])
    return out


def text_report(compiled):
    c = compiled['compilation']; data = compiled['dossier']; ctx = c['context']
    lines = [data['title'] + ' · v' + str(data['revision']),
             '核价日 ' + ctx['as_of'] + ' | ' + ctx['server'] + ' | ' + ctx['currency'],
             '编译状态：' + c['status'] + '；全部声明步骤重新执行，未复用缓存',
             '输入 SHA-256：' + c['input_sha256']]
    conditions = {}
    money = lambda value: _report_money(value, ctx['currency'])
    for row in c['steps']:
        for condition in row['conditions']: conditions[condition['fact_id']] = condition
        lines.append('\n' + row['id'] + ' [' + row['kind'] + ']：' + row['status'])
        price_lines = ['  价格条件：' + condition['step_id'] + condition['path'] + '，' + condition['observed_on'] + '，' + condition['kind'] + '；' + condition['meaning']
                       for condition in row['price_conditions']]
        defer_prices = row['kind'] in ('plans.gem_upgrade', 'project.gem_upgrade') and row['result'] is not None
        if not defer_prices: lines.extend(price_lines)
        if row['blockers']: lines.extend('  待确认：' + x for x in row['blockers'])
        lines.extend('  输入边界：' + x for x in row.get('input_limits', []))
        r = row['result']
        if r is None: continue
        if row['kind'] == 'equipment.optimize':
            lines.append(calculate.report_text(r).strip())
        elif row['kind'] == 'portfolio':
            units = {rid: unit for dep in c['steps'] if dep['id'] in row['depends_on'] and dep['result']
                     for rid, unit in dep['result'].get('resource_units', {}).items()}
            lines.append(portfolio.text_report(r, resource_units=units).strip())
        else:
            raw = row['resolved_input']; linked = _report_linked_portfolios(row, c['steps'])
            if row['kind'].startswith('project.'):
                if 'cost_basis' in r:
                    basis = r['cost_basis']
                    lines.append('  固定规则估算：原规则核验日 ' + basis['rule_checked_on'] + '；估算编制日 ' + basis['prepared_as_of'] + '，不代表市场报价或本轮规则重新核验')
                lines.extend('  条件：' + x for x in r.get('limits', []))
                r = r['calculation']; raw = raw['calculation']
            headline = str(r.get('recommendation', r.get('conclusion', r.get('status', '已重新计算；详细资源/单位见完整结果'))))
            if linked and r.get('calculator') == 'gem_upgrade_plan' and r['budget'] is None:
                headline = headline.replace('预算尚未提供', '本步骤只核成本，预算见下游联合计划 ' + '、'.join(linked))
            if r.get('calculator') in ('repair_guidance', 'pet_equipment_repair', 'pet_scene_leveling', 'xiuyedian_guidance', 'ordinary_gem_operations'):
                lines.extend(_report_grounded(r))
            else:
                lines.append('  ' + headline)
            if defer_prices: lines.extend(price_lines)
            if r.get('calculator') == 'training_mix':
                lines.extend(_report_training_mix(r, raw))
            if 'costLiang' in r and 'materialsConsumed' in r:
                lines.append('  规则现金 ' + r['costLiang'] + '两；计划耗用帮派资材 ' + r['materialsConsumed'] + '资材；剩余需求 ' + r['requiredXp'] + 'XP')
            if r.get('calculator') == 'normal_cultivation':
                lines.append('  ' + r['typeLabel'] + '：' + r['currentLevel'] + '→' + r['targetLevel']
                             + '级；当前本级经验 ' + r['currentProgressXp'] + 'XP')
                lines.append('  普通修炼需购买 ' + r['purchases'] + '次（每次10XP）；购入 ' + r['purchasedXp'] + 'XP；算术余量 ' + r['surplusXp'] + 'XP')
                lines.append('  资格门槛：人物等级≥' + r['requiredCharacterLevel'] + '；累计帮贡>' + r['requiredContributionExclusive']
                             + '；入帮天数>' + r['requiredGuildMembershipDaysExclusive'] + '；仍须本帮开放对应修炼，帮贡门槛不作消费')
            if 'self_upgrade' in r:
                own = r['self_upgrade']
                lines.append('  自升新增现金 ' + money(own['cash_outlay']) + '；库存机会成本 ' + money(own['owned_material_opportunity_cost'])
                             + '；经济成本 ' + money(own['economic_cost']))
            if r.get('calculator') == 'gem_upgrade_plan':
                lines.extend(_report_gem(r, raw, ctx['currency'], linked))
            comparison = r if isinstance(r.get('replacement'), dict) else r.get('comparison')
            if isinstance(comparison, dict) and isinstance(comparison.get('replacement'), dict):
                lines.extend(_report_comparison(comparison, ctx['currency']))
                if r.get('calculator') == 'upgrade_compare':
                    lines.append('  本比较未计算预算可负担性；条件净成本较低不代表先买现金够用')
            lines.extend('  条件：' + str(x) for x in r.get('blockers', []))
            for key in ('quoteWarnings', 'warnings', 'conditions', 'limits', 'limitations', 'eligibilityNotes', 'explanations', 'warning'):
                caution = r.get(key, [])
                if isinstance(caution, str): caution = [caution]
                for message in caution: lines.append('  边界：' + str(message))
    groups = {}
    for fid in sorted(conditions):
        f = next(f for f in data['facts'] if f['id'] == fid)
        key = (f['status'], str(f.get('assumption', '待核实')))
        groups.setdefault(key, []).append(f['label'])
    if groups: lines.append('\n事实条件（适用于所有引用这些事实的结果）：')
    for (status, assumption), labels in groups.items():
        lines.append('  ' + '、'.join(labels) + ' [' + status + ']：' + assumption)
    if c['unused_fact_ids']: lines.append('\n未参与快照的事实：' + ', '.join(c['unused_fact_ids']))
    lines.append('\n使用边界：')
    lines.extend('  ' + x for x in c['warnings'])
    return '\n'.join(lines) + '\n'

def read_input(filename):
    path = Path(filename)
    limit = MAX_BYTES * 8
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Input must be a regular JSON file up to 8 MB, not a symlink')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Input must be a bounded regular file')
        raw = stream.read(limit + 1)
    if len(raw) > limit: raise ValueError('Input too large')
    def reject_number(text):
        raise ValueError('Use exact decimal strings, never JSON floats or nonfinite numbers')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=d._pairs,
                       parse_float=reject_number, parse_constant=reject_number)
    _bounded(value, MAX_NODES * 8)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Host-prepared source dossier or previously compiled bundle')
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    parser.add_argument('--output', help='Exclusively create a new file; never overwrite an old revision')
    args = parser.parse_args(argv)
    try:
        result = compile_dossier(read_input(args.input))
        output = text_report(result) if args.format == 'text' else json_text(result)
        if args.output:
            with Path(args.output).open('x', encoding='utf-8', newline='\n') as stream: stream.write(output)
        else: sys.stdout.write(output)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__': raise SystemExit(main())
