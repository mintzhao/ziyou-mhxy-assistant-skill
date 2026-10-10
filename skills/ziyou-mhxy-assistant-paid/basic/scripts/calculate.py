#!/usr/bin/env python3
"""Offline user-defined preference comparison. Python 3.9+, standard library only."""
import argparse
import itertools
import json
import re
import sys
import stat
import csv
import html
import io
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

MAX_BYTES = 1_000_000
MAX_OPTIONS = 64
MAX_METRICS = 12
MAX_SLOTS = 12
MAX_COMBINATIONS = 10_000
MAX_PARETO_CHECKS = 2_000_000
MAX_PARETO_RETURN = 100
MAX_NUMBER = Decimal('1000000000000')
IDENTIFIER = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
DISCLAIMER = [
    '本结果仅比较你录入的数据、目标与取舍；高级模式使用用户自定义线性偏好，不是游戏真实伤害、收益保证或真实最优配装。',
    '价格、面板增量、指标方向及可选高级权重均由用户提供；未联网核价或验证游戏机制。',
    '按槽位增量可相加；面板上下限仅为你设置的筛选条件，不代表已验证的战斗阈值。套装联动、战斗公式、隐藏属性和未录入限制不在模型内。',
    '零花费基线始终单独展示；免费提升可能使基线不在 Pareto 前沿。'
]


OBJECTIVES = ('weighted', 'min_cost', 'pareto')
OBJECTIVE_LABELS = {'weighted': '高级：按自定义权重比较', 'min_cost': '满足全部条件后花费最少', 'pareto': '不设权重，查看 Pareto 取舍'}
MODELS = {'weighted': 'user_defined_linear_preferences', 'min_cost': 'user_defined_min_cost', 'pareto': 'user_defined_pareto'}
RANKING_RULES = {
    'weighted': '偏好分降序；同分时花费升序、变更件数升序、按槽位排序后的候选 ID 字典序。',
    'min_cost': '满足全部条件后花费升序；同价时变更件数升序、按槽位排序后的候选 ID 字典序。权重不参与排序，同价可能有多个达标方案。',
    'pareto': '不指定唯一最优方案；Pareto 取舍仅按花费升序、变更件数升序、按槽位排序后的候选 ID 字典序展示，展示顺序不代表推荐排名。'
}


class InputError(ValueError):
    pass


def fail(message):
    raise InputError(message)


def fields(obj, required, optional, path):
    if not isinstance(obj, dict):
        fail(f'{path} 必须为对象')
    missing = sorted(set(required) - set(obj))
    extra = sorted(set(obj) - set(required) - set(optional))
    if missing:
        fail(f'{path} 缺少字段: {", ".join(missing)}；未知值不能自动补零')
    if extra:
        fail(f'{path} 含未知字段: {", ".join(extra)}')


def string(value, path, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail(f'{path} 必须为 1–{limit} 字符的非空字符串')
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        fail(f'{path} 不允许控制字符或无效 Unicode 代理码点')
    return value


def identifier(value, path):
    string(value, path, 64)
    if not IDENTIFIER.fullmatch(value):
        fail(f'{path} 需小写字母开头，仅允许小写字母、数字、下划线与连字符')
    return value


def number(value, path, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        fail(f'{path} 必须为 JSON 数值（不能是字符串、null 或布尔值）')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        fail(f'{path} 数值无效')
    if not result.is_finite():
        fail(f'{path} 必须是有限数值')
    if result.copy_abs() > MAX_NUMBER:
        fail(f'{path} 绝对值不能超过 10^12')
    if result.as_tuple().exponent > 999999:
        fail(f'{path} 数值指数超出安全范围')
    if result.as_tuple().exponent < -6:
        fail(f'{path} 最多保留 6 位小数')
    if nonnegative and result < 0:
        fail(f'{path} 不能为负数')
    return result


def exact_keys(obj, ids, path):
    fields(obj, ids, [], path)
    return {k: number(obj[k], f'{path}.{k}') for k in ids}


EVIDENCE = ('user_confirmed', 'unverified', 'synthetic')


def enum(value, allowed, path):
    if value not in allowed:
        fail(f'{path} 仅允许 {" / ".join(allowed)}')
    return value


def id_list(value, path, allowed, cap=64):
    if not isinstance(value, list) or len(value) > cap:
        fail(f'{path} 必须为最多 {cap} 项的数组')
    result = []
    for item in value:
        identifier(item, path)
        if item not in allowed:
            fail(f'{path} 含未知 ID/槽位: {item}')
        if item in result:
            fail(f'{path} 含重复 ID/槽位: {item}')
        result.append(item)
    return result


def weights_for(value, ids, path):
    weights = exact_keys(value, ids, path)
    if any(x < 0 for x in weights.values()) or not any(x > 0 for x in weights.values()):
        fail(f'{path} 必须全部非负，且至少一个权重大于零')
    return weights


def validate(data):
    fields(data, ['schema_version', 'budget', 'currency', 'metrics', 'baseline', 'options'],
           ['objective', 'weights', 'title', 'notes', 'top_n', 'character', 'constraints', 'budget_scenarios',
            'weight_scenarios', 'manual_plans', 'checklist'], 'input')
    if data['schema_version'] != '1.0':
        fail('schema_version 必须为字符串 "1.0"')
    budget = number(data['budget'], 'budget', True)
    currency = string(data['currency'], 'currency', 40)
    title = string(data.get('title', '手工录入方案比较'), 'title')
    if 'notes' in data:
        string(data['notes'], 'notes', 4000)
    metrics = data['metrics']
    if not isinstance(metrics, list) or not 1 <= len(metrics) <= MAX_METRICS:
        fail(f'metrics 需包含 1–{MAX_METRICS} 个指标')
    ids, clean_metrics = [], []
    for i, metric in enumerate(metrics):
        path = f'metrics[{i}]'
        fields(metric, ['id', 'name', 'unit', 'direction'], [], path)
        mid = identifier(metric['id'], path + '.id')
        if mid in ids:
            fail(f'重复指标 ID: {mid}')
        ids.append(mid)
        string(metric['name'], path + '.name')
        string(metric['unit'], path + '.unit', 40)
        enum(metric['direction'], ('maximize', 'minimize'), path + '.direction')
        clean_metrics.append(dict(metric))
    objective = enum(data.get('objective', 'weighted' if 'weights' in data else 'pareto'), OBJECTIVES, 'objective')
    if objective == 'weighted' and 'weights' not in data:
        fail('objective=weighted 需要完整 weights；不想设置权重可选 min_cost 或 pareto')
    weights = weights_for(data['weights'], ids, 'weights') if 'weights' in data else None
    fields(data['baseline'], ['label', 'stats'], ['equipment', 'evidence'], 'baseline')
    label = string(data['baseline']['label'], 'baseline.label')
    stats = exact_keys(data['baseline']['stats'], ids, 'baseline.stats')
    equipment = data['baseline'].get('equipment', {})
    if not isinstance(equipment, dict) or len(equipment) > MAX_SLOTS:
        fail('baseline.equipment 必须为最多 12 个槽位的对象')
    for slot, name in equipment.items():
        identifier(slot, 'baseline.equipment 槽位')
        string(name, 'baseline.equipment.' + slot)
    baseline_evidence = enum(data['baseline'].get('evidence', 'unverified'), EVIDENCE, 'baseline.evidence')
    options = data['options']
    if not isinstance(options, list) or len(options) > MAX_OPTIONS:
        fail(f'options 必须是数组，最多 {MAX_OPTIONS} 项；允许空数组')
    seen, slots, clean_options = set(), {}, []
    for i, option in enumerate(options):
        path = f'options[{i}]'
        fields(option, ['id', 'name', 'slot', 'price'],
               ['deltas', 'measured_stats', 'fees', 'owned', 'evidence', 'source', 'notes'], path)
        oid = identifier(option['id'], path + '.id')
        if oid in seen:
            fail(f'重复候选 ID: {oid}')
        seen.add(oid)
        slot = identifier(option['slot'], path + '.slot')
        name = string(option['name'], path + '.name')
        quoted_price = number(option['price'], path + '.price', True)
        fees = number(option.get('fees', 0), path + '.fees', True)
        owned = option.get('owned', False)
        if not isinstance(owned, bool):
            fail(path + '.owned 必须为布尔值')
        if owned and quoted_price != 0:
            fail(path + ' 已拥有候选的 price 必须为 0；仍需支付的费用填写 fees')
        if ('deltas' in option) == ('measured_stats' in option):
            fail(path + ' 必须且只能填写 deltas 或 measured_stats；未知值不能自动补零')
        if 'deltas' in option:
            delta = exact_keys(option['deltas'], ids, path + '.deltas')
        else:
            measured = exact_keys(option['measured_stats'], ids, path + '.measured_stats')
            delta = {mid: measured[mid] - stats[mid] for mid in ids}
        evidence = enum(option.get('evidence', 'unverified'), EVIDENCE, path + '.evidence')
        for key in ('notes', 'source'):
            if key in option:
                string(option[key], path + '.' + key, 4000 if key == 'notes' else 1000)
        clean = {'id': oid, 'name': name, 'slot': slot, 'price': quoted_price + fees,
                 'quoted_price': quoted_price, 'fees': fees, 'deltas': delta,
                 'owned': owned, 'evidence': evidence, 'source': option.get('source', ''), 'notes': option.get('notes', ''),
                 'replaces': equipment.get(slot, '当前槽位装备')}
        clean_options.append(clean)
        slots.setdefault(slot, []).append(clean)
    all_slots = set(slots) | set(equipment)
    if len(all_slots) > MAX_SLOTS:
        fail(f'槽位最多 {MAX_SLOTS} 个')
    combinations = 1
    for choices in slots.values():
        combinations *= len(choices) + 1
    if combinations > MAX_COMBINATIONS:
        fail(f'组合数 {combinations} 超过上限 {MAX_COMBINATIONS}；请减少候选/槽位后重试，不会返回部分最优结果')
    top_n = number(data.get('top_n', 10), 'top_n', True)
    if not 1 <= top_n <= 50 or top_n != top_n.to_integral_value():
        fail('top_n 必须为 1–50 的整数')
    character = data.get('character', {})
    fields(character, [], ['level', 'school', 'server', 'purpose'], 'character')
    character = dict(character)
    for key, value in character.items():
        if key == 'level':
            level = number(value, 'character.level', True)
            if not 1 <= level <= 200 or level != level.to_integral_value():
                fail('character.level 必须为 1–200 的整数；仅为备注，不验证装备使用资格')
            character[key] = fmt(level)
        else:
            string(value, 'character.' + key)
    rules = data.get('constraints', {})
    fields(rules, [], ['min_stats', 'max_stats', 'locked_slots', 'required_options',
                       'excluded_options', 'conflicts', 'max_changes'], 'constraints')
    constraints = {}
    for key in ('min_stats', 'max_stats'):
        values = rules.get(key, {})
        fields(values, [], ids, 'constraints.' + key)
        constraints[key] = {mid: number(value, f'constraints.{key}.{mid}') for mid, value in values.items()}
    for mid in ids:
        if mid in constraints['min_stats'] and mid in constraints['max_stats'] and constraints['min_stats'][mid] > constraints['max_stats'][mid]:
            fail(f'constraints 指标 {mid} 的下限不能高于上限')
    for key, allowed in [('locked_slots', all_slots), ('required_options', seen), ('excluded_options', seen)]:
        constraints[key] = id_list(rules.get(key, []), 'constraints.' + key, allowed)
    by_id = {o['id']: o for o in clean_options}
    required = constraints['required_options']
    required_slots = [by_id[oid]['slot'] for oid in required]
    if len(set(required_slots)) != len(required_slots):
        fail('required_options 不能同时要求同一槽位的两个候选')
    if set(required) & set(constraints['excluded_options']):
        fail('同一候选不能同时必选与排除')
    if set(required_slots) & set(constraints['locked_slots']):
        fail('已锁定保留当前装备的槽位不能必选替换候选')
    conflicts = rules.get('conflicts', [])
    if not isinstance(conflicts, list) or len(conflicts) > 128:
        fail('constraints.conflicts 必须为最多 128 对的数组')
    constraints['conflicts'] = []
    for i, pair in enumerate(conflicts):
        pair = id_list(pair, f'constraints.conflicts[{i}]', seen, 2)
        if len(pair) != 2:
            fail('每个 conflicts 项必须恰好包含两个不同候选 ID')
        pair = sorted(pair)
        if pair in constraints['conflicts']:
            fail('constraints.conflicts 含重复冲突对')
        if set(pair) <= set(required):
            fail('两个必选候选互相冲突')
        constraints['conflicts'].append(pair)
    max_changes = number(rules.get('max_changes', 12), 'constraints.max_changes', True)
    if max_changes > 12 or max_changes != max_changes.to_integral_value():
        fail('constraints.max_changes 必须为 0–12 的整数')
    constraints['max_changes'] = int(max_changes)
    if len(required) > max_changes:
        fail('必选候选数超过 max_changes')
    scenarios = {}
    for key, field in [('budget_scenarios', 'budget'), ('weight_scenarios', 'weights'), ('manual_plans', 'option_ids')]:
        entries = data.get(key, [])
        cap = 2 if key == 'manual_plans' else 8
        if not isinstance(entries, list) or len(entries) > cap:
            fail(f'{key} 必须为最多 {cap} 项的数组')
        clean_entries, labels = [], set()
        for i, entry in enumerate(entries):
            path = f'{key}[{i}]'
            fields(entry, ['label', field], [], path)
            name = string(entry['label'], path + '.label')
            if name in labels:
                fail(key + ' 标签不能重复')
            labels.add(name)
            if field == 'budget':
                value = number(entry[field], path + '.' + field, True)
            elif field == 'weights':
                value = weights_for(entry[field], ids, path + '.' + field)
            else:
                value = id_list(entry[field], path + '.' + field, seen, 12)
                if len({by_id[oid]['slot'] for oid in value}) != len(value):
                    fail(path + ' 不能选择同一槽位的多个候选')
            clean_entries.append({'label': name, field: value})
        scenarios[key] = clean_entries
    checklist = data.get('checklist', [])
    if not isinstance(checklist, list) or len(checklist) > 20:
        fail('checklist 必须为最多 20 项的数组')
    for i, check in enumerate(checklist):
        path = f'checklist[{i}]'
        fields(check, ['item', 'status'], ['note'], path)
        string(check['item'], path + '.item')
        enum(check['status'], ('confirmed', 'unverified', 'not_applicable'), path + '.status')
        if 'note' in check:
            string(check['note'], path + '.note', 1000)
    return {'title': title, 'notes': data.get('notes', ''), 'budget': budget, 'currency': currency, 'metrics': clean_metrics,
            'ids': ids, 'weights': weights, 'objective': objective, 'stats': stats, 'baseline_label': label,
            'baseline_evidence': baseline_evidence, 'equipment': equipment,
            'slots': slots, 'options': clean_options, 'by_id': by_id, 'combinations': combinations,
            'top_n': int(top_n), 'character': character, 'constraints': constraints,
            'checklist': checklist, **scenarios}


def diagnose(data):
    issues = []
    if isinstance(data, dict):
        mids = [m.get('id') for m in data.get('metrics', [])[:12] if isinstance(m, dict) and isinstance(m.get('id'), str)] if isinstance(data.get('metrics'), list) else []
        def numeric_issue(value, path, nonnegative=False):
            try:
                number(value, path, nonnegative)
            except InputError as exc:
                issues.append({'path': path, 'message': str(exc)})
        numeric_issue(data.get('budget'), 'budget', True)
        for key in (('weights',) if 'weights' in data or data.get('objective') == 'weighted' else ()):
            values = data.get(key) if isinstance(data.get(key), dict) else {}
            for mid in mids:
                numeric_issue(values.get(mid), key + '.' + mid, True)
        baseline = data.get('baseline') if isinstance(data.get('baseline'), dict) else {}
        values = baseline.get('stats') if isinstance(baseline.get('stats'), dict) else {}
        for mid in mids:
            numeric_issue(values.get(mid), 'baseline.stats.' + mid)
        options = data.get('options') if isinstance(data.get('options'), list) else []
        for i, option in enumerate(options[:64]):
            if not isinstance(option, dict):
                continue
            numeric_issue(option.get('price'), f'options[{i}].price', True)
            if 'fees' in option:
                numeric_issue(option['fees'], f'options[{i}].fees', True)
            key = 'measured_stats' if 'measured_stats' in option else 'deltas'
            values = option.get(key) if isinstance(option.get(key), dict) else {}
            for mid in mids:
                numeric_issue(values.get(mid), f'options[{i}].{key}.{mid}')
        rules = data.get('constraints') if isinstance(data.get('constraints'), dict) else {}
        for key in ('min_stats', 'max_stats'):
            values = rules.get(key)
            if isinstance(values, dict):
                for mid, value in values.items():
                    numeric_issue(value, f'constraints.{key}.{mid}')
        if 'max_changes' in rules:
            numeric_issue(rules['max_changes'], 'constraints.max_changes', True)
        for key in ('budget_scenarios', 'weight_scenarios'):
            scenarios = data.get(key) if isinstance(data.get(key), list) else []
            for i, scenario in enumerate(scenarios[:8]):
                if not isinstance(scenario, dict):
                    continue
                if key == 'budget_scenarios':
                    numeric_issue(scenario.get('budget'), f'{key}[{i}].budget', True)
                else:
                    values = scenario.get('weights') if isinstance(scenario.get('weights'), dict) else {}
                    for mid in mids:
                        numeric_issue(values.get(mid), f'{key}[{i}].weights.{mid}', True)
        if 'top_n' in data:
            numeric_issue(data['top_n'], 'top_n', True)
        if isinstance(data.get('character'), dict) and 'level' in data['character']:
            numeric_issue(data['character']['level'], 'character.level', True)
    try:
        with localcontext() as ctx:
            ctx.prec = 60
            validate(data)
    except (InputError, InvalidOperation, OverflowError, RecursionError) as exc:
        if not any(issue['message'] == str(exc) for issue in issues):
            issues.append({'path': 'input', 'message': str(exc)})
    return {'ready': not issues, 'issues': issues}


def rank_key(combo):
    return (-combo['score'] if combo['score'] is not None else Decimal(0), combo['price'], len(combo['selection']), tuple(x['id'] for x in combo['selection']))


def fmt(value):
    if value == 0:
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def decimal_tree(value):
    if isinstance(value, Decimal):
        return fmt(value)
    if isinstance(value, dict):
        return {key: decimal_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decimal_tree(item) for item in value]
    return value


def public(combo):
    keys = ('selection', 'price', 'remaining_budget', 'deltas', 'final_stats', 'score',
            'is_baseline', 'feasible', 'violations', 'drawbacks')
    result = decimal_tree({key: combo[key] for key in keys})
    if 'equivalent_count' in combo:
        result['equivalent_count'] = combo['equivalent_count']
    return result


def violations(combo, cfg, budget=None):
    budget = cfg['budget'] if budget is None else budget
    rules, messages = cfg['constraints'], []
    selected = {item['id'] for item in combo['selection']}
    selected_slots = {item['slot'] for item in combo['selection']}
    if combo['price'] > budget:
        messages.append(f'超出预算 {fmt(combo["price"] - budget)} {cfg["currency"]}')
    for slot in rules['locked_slots']:
        if slot in selected_slots:
            messages.append(f'锁定槽位 {slot} 必须保留当前装备')
    for oid in rules['required_options']:
        if oid not in selected:
            messages.append(f'未包含必选候选 {oid}')
    for oid in rules['excluded_options']:
        if oid in selected:
            messages.append(f'包含已排除候选 {oid}')
    for a, b in rules['conflicts']:
        if a in selected and b in selected:
            messages.append(f'候选 {a} 与 {b} 不能同时选择')
    if len(selected) > rules['max_changes']:
        messages.append(f'变更件数超过 {rules["max_changes"]} 件限制')
    for mid, target in rules['min_stats'].items():
        actual = combo['final_stats'][mid]
        if actual < target:
            messages.append(f'{mid} 距下限 {fmt(target)} 还差 {fmt(target - actual)}')
    for mid, target in rules['max_stats'].items():
        actual = combo['final_stats'][mid]
        if actual > target:
            messages.append(f'{mid} 超过上限 {fmt(target)} 共 {fmt(actual - target)}')
    return messages


def make_combo(selected, cfg, budget=None, weights=None):
    budget = cfg['budget'] if budget is None else budget
    weights = (cfg['weights'] if cfg['objective'] == 'weighted' else None) if weights is None else weights
    selected = sorted(selected, key=lambda item: (item['slot'], item['id']))
    price = sum((item['price'] for item in selected), Decimal(0))
    deltas = {mid: sum((item['deltas'][mid] for item in selected), Decimal(0)) for mid in cfg['ids']}
    signs = cfg['signs']
    selection = [{**{key: item[key] for key in ('id', 'name', 'slot', 'quoted_price', 'fees', 'owned', 'evidence', 'source', 'notes', 'replaces')}, 'total_cost': item['price']} for item in selected]
    combo = {'selection': selection, 'price': price, 'remaining_budget': budget - price,
             'deltas': deltas, 'final_stats': {mid: cfg['stats'][mid] + deltas[mid] for mid in cfg['ids']},
             'score': sum((weights[mid] * signs[mid] * deltas[mid] for mid in cfg['ids']), Decimal(0)) if weights is not None else None,
             'is_baseline': not selected,
             'drawbacks': [mid for mid in cfg['ids'] if deltas[mid] * signs[mid] < 0]}
    combo['violations'] = violations(combo, cfg, budget)
    combo['feasible'] = not combo['violations']
    return combo


def dominates(a, b, ids, signs):
    if a['price'] > b['price']:
        return False
    strict = a['price'] < b['price']
    for mid in ids:
        av, bv = a['deltas'][mid] * signs[mid], b['deltas'][mid] * signs[mid]
        if av < bv:
            return False
        strict = strict or av > bv
    return strict


def pareto_frontier(feasible, ids, signs):
    distinct = {}
    for combo in feasible:
        key = (combo['price'],) + tuple(combo['deltas'][mid] for mid in ids)
        if key not in distinct:
            distinct[key] = dict(combo, equivalent_count=1)
        else:
            distinct[key]['equivalent_count'] += 1
    frontier, checks = [], 0
    for candidate in distinct.values():
        remove, rejected = [], False
        for index, current in enumerate(frontier):
            checks += 1
            if checks > MAX_PARETO_CHECKS:
                fail(f'Pareto 比较超过 {MAX_PARETO_CHECKS} 次安全上限；请减少候选或指标。未输出不完整结果')
            if dominates(current, candidate, ids, signs):
                rejected = True
                break
            if dominates(candidate, current, ids, signs):
                remove.append(index)
        if not rejected:
            for index in reversed(remove):
                del frontier[index]
            frontier.append(candidate)
    frontier.sort(key=rank_key)
    return frontier, len(distinct), checks


def calculate(data):
    with localcontext() as ctx:
        ctx.prec = 60
        cfg = validate(data)
        ids = cfg['ids']
        signs = cfg['signs'] = {m['id']: (1 if m['direction'] == 'maximize' else -1) for m in cfg['metrics']}
        groups = [[None] + sorted(cfg['slots'][slot], key=lambda item: item['id']) for slot in sorted(cfg['slots'])]
        all_combos, feasible = [], []
        within_budget = 0
        for choices in itertools.product(*groups):
            selected = [item for item in choices if item is not None]
            combo = make_combo(selected, cfg)
            all_combos.append(combo)
            if combo['price'] <= cfg['budget']:
                within_budget += 1
            if combo['feasible']:
                feasible.append(combo)
        baseline = all_combos[0]  # Every first per-slot choice is keep current.
        feasible.sort(key=rank_key)
        frontier, distinct_count, checks = pareto_frontier(feasible, ids, signs)
        baseline_out = public(baseline)
        baseline_out['label'] = cfg['baseline_label']
        baseline_out['evidence'] = cfg['baseline_evidence']
        baseline_out['equipment'] = cfg['equipment']
        baseline_key = (baseline['price'],) + tuple(baseline['deltas'][mid] for mid in ids)
        baseline_out['on_pareto'] = baseline['feasible'] and any((p['price'],) + tuple(p['deltas'][mid] for mid in ids) == baseline_key for p in frontier)
        budget_scenarios, weight_scenarios = [], []
        for scenario in cfg['budget_scenarios']:
            budget = scenario['budget']
            rows = []
            for combo in all_combos:
                if not violations(combo, cfg, budget):
                    rows.append(dict(combo, remaining_budget=budget - combo['price'], violations=[], feasible=True))
            rows.sort(key=rank_key)
            result = {'label': scenario['label'], 'budget': fmt(budget), 'objective': cfg['objective'],
                      'best': public(rows[0]) if rows and cfg['objective'] != 'pareto' else None,
                      'feasible_count': len(rows)}
            if cfg['objective'] == 'pareto':
                scenario_frontier, _, _ = pareto_frontier(rows, ids, signs)
                result.update(pareto=[public(row) for row in scenario_frontier[:MAX_PARETO_RETURN]],
                              pareto_total=len(scenario_frontier), pareto_shown=min(len(scenario_frontier), MAX_PARETO_RETURN),
                              pareto_truncated=len(scenario_frontier) > MAX_PARETO_RETURN)
            budget_scenarios.append(result)
        for scenario in cfg['weight_scenarios']:
            weights = scenario['weights']
            rows = [dict(combo, score=sum((weights[mid] * signs[mid] * combo['deltas'][mid] for mid in ids), Decimal(0))) for combo in feasible]
            rows.sort(key=rank_key)
            weight_scenarios.append({'label': scenario['label'], 'objective': 'weighted', 'weights': decimal_tree(weights),
                                     'best': public(rows[0]) if rows else None, 'feasible_count': len(rows)})
        manual_plans = [{'label': plan['label'], 'plan': public(make_combo([cfg['by_id'][oid] for oid in plan['option_ids']], cfg))} for plan in cfg['manual_plans']]
        counts = {key: sum(option['evidence'] == key for option in cfg['options']) for key in EVIDENCE}
        diagnostics = []
        if not feasible:
            diagnostics.append({'kind': 'no_feasible_plan', 'message': '没有同时满足预算和全部已录入限制的方案。零花费基线仍作为参考；请检查目标差距、必选项和预算，不要把无解当成推荐购买。'})
        if not baseline['feasible']:
            diagnostics.append({'kind': 'baseline_constraints', 'message': '当前零变更基线未满足这些条件：' + '；'.join(baseline['violations'])})
        if counts['unverified'] or cfg['baseline_evidence'] == 'unverified':
            diagnostics.append({'kind': 'unverified_data', 'message': '存在未核实的面板或候选数据。数学结果仅在录入成立时有效，不能作为已核价或实测证明。'})
        if counts['synthetic'] or cfg['baseline_evidence'] == 'synthetic':
            diagnostics.append({'kind': 'synthetic_data', 'message': '本次含纯合成演示数据，不得据此购买或推断游戏机制。'})
        if cfg['objective'] == 'pareto':
            diagnostics.append({'kind': 'pareto_choice', 'message': RANKING_RULES['pareto']})
        if cfg['objective'] == 'min_cost' and not cfg['constraints']['min_stats'] and not cfg['constraints']['max_stats']:
            diagnostics.append({'kind': 'no_panel_targets', 'message': '未设置面板目标，只按已录入限制找最低花费；当前方案可行时通常无需购买。可在最终面板门槛填写需要达到的值。'})
        chosen_label = '最低花费达标方案' if cfg['objective'] == 'min_cost' else '最高偏好分方案'
        if cfg['objective'] != 'pareto' and feasible and feasible[0]['price'] == cfg['budget'] and cfg['budget'] > 0:
            diagnostics.append({'kind': 'budget', 'message': chosen_label + '已用满预算；购买前重新核实全部必要费用。预算情景只用于比较，不构成加预算建议。'})
        if cfg['objective'] != 'pareto' and feasible and feasible[0]['drawbacks']:
            diagnostics.append({'kind': 'tradeoff', 'message': chosen_label + '也有按所选方向变差的指标：' + '、'.join(feasible[0]['drawbacks']) + '。请核对可接受程度。'})
        if feasible and cfg['objective'] != 'pareto':
            for bound in ('min_stats', 'max_stats'):
                for mid, target in cfg['constraints'][bound].items():
                    if feasible[0]['final_stats'][mid] == target:
                        diagnostics.append({'kind': 'binding_target', 'message': f'{mid} 恰好达到你设置的{"下限" if bound == "min_stats" else "上限"} {fmt(target)}；任何录入误差或状态变化都可能影响达标。'})
        for check in cfg['checklist']:
            if check['status'] == 'unverified':
                diagnostics.append({'kind': 'checklist', 'message': '待确认：' + check['item']})
        diagnostics.append({'kind': 'model', 'message': '这里只诊断录入数据、预算与自设面板目标；不识别真实战斗短板，也不计算伤害或套装联动。'})
        return {'schema_version': '1.0', 'model': MODELS[cfg['objective']],
                'objective': cfg['objective'], 'objective_description': OBJECTIVE_LABELS[cfg['objective']],
                'status': 'ok' if feasible else 'no_feasible_plan',
                'title': cfg['title'], 'notes': cfg['notes'], 'currency': cfg['currency'], 'budget': fmt(cfg['budget']),
                'metrics': cfg['metrics'], 'weights': decimal_tree(cfg['weights']),
                'character': cfg['character'], 'constraints': decimal_tree(cfg['constraints']),
                'checklist': cfg['checklist'], 'disclaimer': DISCLAIMER,
                'evidence_summary': {'confirmed_options': counts['user_confirmed'], 'unverified_options': counts['unverified'],
                                     'synthetic_options': counts['synthetic'], 'baseline_evidence': cfg['baseline_evidence'],
                                     'notice': '确认状态为用户自行声明；本工具未联网核实。'},
                'diagnostics': diagnostics, 'baseline': baseline_out,
                'best': public(feasible[0]) if feasible and cfg['objective'] != 'pareto' else None,
                'alternatives': [public(combo) for combo in feasible[1:cfg['top_n']]] if cfg['objective'] != 'pareto' else [],
                'pareto': [public(combo) for combo in frontier[:MAX_PARETO_RETURN]],
                'budget_scenarios': budget_scenarios, 'weight_scenarios': weight_scenarios,
                'manual_plans': manual_plans,
                'summary': {'combinations_possible': cfg['combinations'], 'combinations_evaluated': cfg['combinations'],
                            'within_budget': within_budget, 'feasible_count': len(feasible),
                            'rejected_by_constraints': within_budget - len(feasible),
                            'distinct_vectors': distinct_count, 'pareto_total': len(frontier),
                            'pareto_shown': min(len(frontier), MAX_PARETO_RETURN),
                            'pareto_truncated': len(frontier) > MAX_PARETO_RETURN, 'pareto_comparisons': checks},
                'limits': {'max_input_bytes': MAX_BYTES, 'max_combinations': MAX_COMBINATIONS,
                           'max_pareto_checks': MAX_PARETO_CHECKS, 'pareto_return_limit': MAX_PARETO_RETURN},
                'ranking_rule': RANKING_RULES[cfg['objective']],
                'pareto_rule': '花费越低越好，各指标按用户方向比较；至少一维严格更好且其他维不差才支配。相同向量合并并标注 equivalent_count。'}


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            fail(f'JSON 对象含重复键: {key}')
        obj[key] = value
    return obj


def reject_constant(value):
    fail(f'JSON 不允许非有限数值: {value}')


def parse_input(raw):
    if len(raw.encode('utf-8')) > MAX_BYTES:
        fail(f'输入文件超过 {MAX_BYTES} 字节上限')
    depth, in_string, escaped = 0, False, False
    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in '{[':
            depth += 1
            if depth > 32:
                fail('JSON 嵌套超过 32 层安全上限')
        elif character in '}]':
            depth -= 1
    try:
        return json.loads(raw.lstrip('\ufeff'), parse_float=Decimal, parse_int=Decimal,
                          parse_constant=reject_constant, object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError, InvalidOperation) as exc:
        fail(f'无效 UTF-8 JSON: {exc}')


def read_input(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        fail('输入必须为普通文件，不能为目录、设备或命名管道')
    if info.st_size > MAX_BYTES:
        fail(f'输入文件超过 {MAX_BYTES} 字节上限')
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        fail(f'输入文件超过 {MAX_BYTES} 字节上限')
    try:
        return parse_input(raw.decode('utf-8-sig'))
    except UnicodeError as exc:
        fail(f'无效 UTF-8 JSON: {exc}')


def report_rows(report):
    rows = [('零花费当前基线', report['baseline'])]
    if report['best']:
        rows.append(('最低花费达标方案' if report.get('objective') == 'min_cost' else '最高偏好分', report['best']))
    rows += [(f'备选 {i + 1}', row) for i, row in enumerate(report['alternatives'])]
    rows += [(f'Pareto 取舍 {i + 1}', row) for i, row in enumerate(report['pareto'])]
    rows += [(f'手工比较：{row["label"]}', row['plan']) for row in report['manual_plans']]
    for scenario in report['budget_scenarios']:
        label = f'预算情景：{scenario["label"]}（预算 {scenario["budget"]}）'
        if scenario.get('objective') == 'pareto' and scenario['feasible_count']:
            rows += [(label + f'；Pareto 取舍 {i + 1}', row) for i, row in enumerate(scenario['pareto'])]
        else:
            rows.append((label, scenario['best']))
    rows += [(f'权重情景：{row["label"]}（' + '；'.join(f'{mid}={weight}' for mid, weight in row['weights'].items()) + '）', row['best']) for row in report['weight_scenarios']]
    return rows


def report_text(report):
    lines = [report['title'], '手工配装预算比较｜偏好分不是伤害',
             f'预算：{report["budget"]} {report["currency"]}',
             '比较目标：' + report.get('objective_description', OBJECTIVE_LABELS['weighted']),
             report.get('ranking_rule', ''),
             ('高级权重' + ('（主目标不使用）' if report.get('objective', 'weighted') != 'weighted' else '') + '：' + '；'.join(f'{m["name"]}={report["weights"][m["id"]]}' for m in report['metrics'])) if report.get('weights') else '主目标未设置权重；主方案不计算偏好分', '']
    lines += ['角色备注：' + json.dumps(report['character'], ensure_ascii=False),
              '用户设置的限制：' + json.dumps(report['constraints'], ensure_ascii=False),
              '当前装备：' + json.dumps(report['baseline'].get('equipment', {}), ensure_ascii=False),
              '当前面板依据：' + report['baseline'].get('evidence', 'unverified')]
    if report.get('notes'):
        lines.append('用户备注（不自动作为约束）：' + report['notes'])
    lines += report['disclaimer'] + ['']
    for label, row in report_rows(report):
        lines.append('【' + label + '】')
        if row is None:
            lines.extend(['无满足全部条件的方案', ''])
            continue
        lines.append(f'花费 {row["price"]} {report["currency"]}；剩余 {row["remaining_budget"]}' + (f'；偏好分 {row["score"]}' if row['score'] is not None else '；未使用权重评分'))
        lines.append('满足本次限制：' + ('是' if row['feasible'] else '否'))
        for item in row['selection']:
            lines.append(f'- {item["slot"]}：{item["replaces"]} → {item["name"]}；报价 {item["quoted_price"]} + 费用 {item["fees"]} = {item["total_cost"]}；{"已有" if item["owned"] else "待购"}；证据 {item["evidence"]}')
            if item['source']:
                lines.append('  来源记录：' + item['source'])
            if item.get('notes'):
                lines.append('  候选备注（未自动建模）：' + item['notes'])
        if not row['selection']:
            lines.append('保留全部当前装备')
        for metric in report['metrics']:
            mid = metric['id']
            lines.append(f'- {metric["name"]}：{row["final_stats"][mid]} {metric["unit"]}；相对当前 {row["deltas"][mid]}' + ('（按所选方向变差）' if mid in row['drawbacks'] else ''))
        lines.extend('限制未满足：' + message for message in row['violations'])
        lines.append('')
    lines.append('数据与检查')
    lines += [row['message'] for row in report['diagnostics']]
    lines += [f'{check["item"]}：{check["status"]}' + ('；' + check['note'] if 'note' in check else '') for check in report['checklist']]
    for scenario in report['budget_scenarios']:
        if scenario.get('objective') == 'pareto':
            lines.append(f'预算情景 {scenario["label"]}：Pareto 展示 {scenario["pareto_shown"]} / {scenario["pareto_total"]} 个等价向量' + ('（已截断）' if scenario['pareto_truncated'] else ''))
    lines.append(f'可行方案 {report["summary"]["feasible_count"]}；Pareto 前沿 {report["summary"]["pareto_total"]} 个等价向量，JSON 展示 {report["summary"]["pareto_shown"]} 个')
    return '\n'.join(lines) + '\n'


def report_csv(report):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value
    headers = ['类别', '候选', '满足限制', '花费', '货币', '剩余预算', '偏好分']
    for metric in report['metrics']:
        headers.extend([metric['name'] + '最终', metric['name'] + '增量'])
    headers += ['违反限制', '来源与证据', '主权重', '全部限制', '数据边界', '比较目标']
    writer.writerow([safe(value) for value in headers])
    for label, row in report_rows(report):
        if row is None:
            writer.writerow([safe(label), '无可行方案'])
            continue
        cells = [label, ' / '.join(item['name'] for item in row['selection']) or '保留当前',
                 '是' if row['feasible'] else '否', row['price'], report['currency'], row['remaining_budget'], row['score'] if row['score'] is not None else '']
        for metric in report['metrics']:
            cells.extend([row['final_stats'][metric['id']], row['deltas'][metric['id']]])
        cells += ['；'.join(row['violations']), '；'.join(item['name'] + '：' + item['evidence'] + '；' + item['source'] + '；备注：' + item.get('notes', '') for item in row['selection']), json.dumps(report['weights'], ensure_ascii=False), json.dumps(report['constraints'], ensure_ascii=False), '用户手工录入；偏好分不是伤害；确认状态未经工具独立验证', 'weighted' if label.startswith('权重情景：') else report.get('objective', 'weighted')]
        writer.writerow([safe(value) for value in cells])
    if report.get('notes'):
        writer.writerow([safe('用户备注（未自动建模）'), safe(report['notes'])])
    return '\ufeff' + output.getvalue()


def report_html(report):
    body = html.escape(report_text(report))
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>手工配装比较报告</title><style>body{max-width:960px;margin:2rem auto;padding:0 1rem;font:16px/1.7 system-ui;color:#132733;background:#f5f8fa}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}h1{font-size:1.6rem}@media print{body{background:white;margin:0}}</style><h1>手工配装比较报告</h1><pre>' + body + '</pre></html>\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='离线手工装备预算/偏好比较；不是游戏伤害公式。')
    parser.add_argument('input', type=Path, help='UTF-8 输入 JSON')
    parser.add_argument('--output', type=Path, help='输出文件；不覆盖已有文件')
    parser.add_argument('--format', choices=('json', 'text', 'csv', 'html'), default='json', help='默认 JSON；text 为人类可读报告')
    parser.add_argument('--check', action='store_true', help='只检查完整性并列出待填项，不计算')
    args = parser.parse_args(argv)
    try:
        data = read_input(args.input)
        if args.check:
            report = diagnose(data)
            content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            exit_code = 0 if report['ready'] else 2
        else:
            report = calculate(data)
            content = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n') if args.format == 'json' else {'text': report_text, 'csv': report_csv, 'html': report_html}[args.format](report)
            exit_code = 0
        encoded = content.encode('utf-8')
        if args.output:
            with args.output.open('xb') as handle:
                handle.write(encoded)
        else:
            print(content, end='')
        return exit_code
    except (InputError, OSError, UnicodeError, RecursionError, InvalidOperation, OverflowError) as exc:
        message = f'错误: {exc}'
        encoding = getattr(sys.stderr, 'encoding', None) or 'utf-8'
        message = message.encode(encoding, errors='backslashreplace').decode(encoding)
        print(message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
