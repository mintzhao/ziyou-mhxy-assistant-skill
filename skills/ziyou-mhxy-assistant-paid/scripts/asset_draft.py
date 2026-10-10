"""Public, offline neutral asset data editor; Python standard library only.

Create, validate, inspect and explicitly edit v1/v2 intake documents. This module
contains no assignment or combination solver, network, file I/O, payment state,
credentials or runtime dependency on the private application. Missing and null
facts stay missing and null. The host chooses all paths and handles bounded I/O.

The pure schema/edit/inspect implementation is behavior-frozen to the private
intake baseline in the accompanying differential tests. Validation helpers below
are small standard-library copies, not imports of the private solver modules.
"""
import copy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
import re

__all__ = ('LEGACY_SCHEMA', 'SCHEMA', 'NOTICE', 'IntakeError', 'checked',
           'content', 'digest', 'create', 'edit', 'inspect')


def _text(value, label, limit=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(label + ' must be nonempty text without controls')
    return value


def _fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError('Expected an object')
    absent = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if absent or extra:
        raise ValueError('Missing fields: ' + ', '.join(sorted(absent)) + '; unknown fields: ' + ', '.join(sorted(extra)))


def _num(value, label, signed=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(label + ' must be an integer or decimal string')
    s = str(value)
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?', s):
        raise ValueError(label + ' requires a plain decimal with up to 6 decimal places')
    n = Decimal(s)
    if not n.is_finite() or abs(n) > Decimal('1000000000000') or (not signed and n < 0):
        raise ValueError(label + ' is outside supported range')
    return n


def _day(value, label):
    _text(value, label, 10)
    try:
        v = date.fromisoformat(value)
    except ValueError:
        raise ValueError(label + ' must be YYYY-MM-DD')
    if v.isoformat() != value:
        raise ValueError(label + ' must be YYYY-MM-DD')
    return v


def _bounded_json(value):
    """Reject non-JSON, cycles, pathological size and floats before copying."""
    count = 0
    size = 0
    def visit(v, depth):
        nonlocal count, size
        count += 1
        if count > 100000 or depth > 20:
            raise ValueError('Input exceeds node/depth bound')
        if isinstance(v, dict):
            for k, item in v.items():
                if not isinstance(k, str): raise ValueError('JSON keys must be strings')
                visit(k, depth + 1); visit(item, depth + 1)
        elif isinstance(v, list):
            for item in v: visit(item, depth + 1)
        elif v is None or isinstance(v, bool): pass
        elif isinstance(v, str):
            size += len(v.encode('utf-8'))
        elif type(v) is int:
            if abs(v) > 10**15: raise ValueError('Integer exceeds input bound')
        else: raise ValueError('Use plain JSON with decimal strings, not floats or Decimal objects')
        if size > 1000000: raise ValueError('Input exceeds byte bound')
    visit(value, 0)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if len(encoded) > 1000000: raise ValueError('Input exceeds byte bound')
    return encoded


def _json_digest(value):
    return hashlib.sha256(_bounded_json(value)).hexdigest()


LEGACY_SCHEMA = 'ziyou-asset-intake/v1'
SCHEMA = 'ziyou-asset-intake/v2'
_MISSING = object()
NOTICE = '免费暂存未补齐的资料；记录编号不是实物身份。未计算、未下单、未调配。'


class IntakeError(ValueError):
    def __init__(self, path, code, message):
        self.issue = dict(path=path, code=code, question=message, category='input_blocker')
        super().__init__(message)


def fail(path, code, message):
    raise IntakeError(path, code, message)


@dataclass(frozen=True)
class Obj:
    fields: dict
    optional: tuple = ()


@dataclass(frozen=True)
class Items:
    item: object
    maximum: int = 200
    keyed: bool = False
    minimum: int = 0


@dataclass(frozen=True)
class Mapping:
    item: object
    maximum: int = 35


QUOTE = Obj(dict(amount='money', currency='text', server='text', observed_on='date',
                 source='text', kind=('asking', 'sold', 'user_quote', 'estimate'), notes='text'), ('notes',))
LINE = Obj(dict(label='text', quantity='money', quote=QUOTE))
FACT = Obj(dict(eligible=('confirmed', 'unknown', 'ineligible'),
                transfer_allowed=('confirmed', 'unknown', 'forbidden'),
                fees=Items(LINE), fees_complete='bool', basis='text'))
SLOT = Obj(dict(id='id', role_id='text', kind=('equipment', 'pet'), need='text', basis='text'))
ASSET = Obj(dict(id='id', physical_id='text', label='text', kind=('equipment', 'pet'),
                 ownership=('owned', 'purchase'), purchase_costs=Items(LINE),
                 purchase_costs_complete='bool', availability=('confirmed', 'unknown', 'unavailable'),
                 basis='text', compatibility=Mapping(FACT)))
RULE = Obj(dict(id='id', user_confirmed='bool', asset_ids=Items('id', 64, minimum=1),
                slot_ids=Items('id', 35, minimum=1), fact=FACT))
CONTEXT = Obj(dict(server='text', currency='text', as_of='date', max_age_days='age',
                   ruleset=('pc_time', '电脑版时间服', '梦幻西游电脑版时间服')), ('max_age_days', 'ruleset'))
INPUT = Obj(dict(schema_version='version', title='text', context=CONTEXT, budget='money',
                 reserve='money', hypothetical='bool', slots=Items(SLOT, 35, True, 1),
                 assets=Items(ASSET, 64, True), force_assignment=Obj(dict(asset_id='id', slot_id='id'))),
            ('force_assignment',))
REQUEST = Obj(dict(input=INPUT, compatibility_rules=Items(RULE, 64, True)))
AMBIGUITY = Obj(dict(id='id', asset_ids=Items('id', 64, minimum=1), basis='text'))
TAG_FACT = Obj(dict(tags=Items('id', 8), tags_complete='bool', user_confirmed='bool', basis='text'))
REQUIREMENT = Obj(dict(id='id', role_id='exact', tag='exact', min_count='count', max_count='count',
                       user_confirmed='bool', basis='text'), ('max_count',))
COMBINATION = Obj(dict(asset_tag_facts=Mapping(TAG_FACT, 64),
                       role_requirements=Items(REQUIREMENT, 12, True, 1), search_node_budget='node_budget'),
                  ('search_node_budget',))
ROOT = Obj(dict(request=REQUEST, ambiguities=Items(AMBIGUITY, 64, True), combination=COMBINATION), ('combination',))


def _validate(value, spec, path):
    """Only syntactic safety here. Omitted/null facts remain exactly as received."""
    if value is None:
        if spec == 'id': fail(path, 'id_required', '请给这条记录一个明确且不重复的资料编号；它不代表实物身份。')
        return
    if isinstance(spec, Obj):
        if not isinstance(value, dict): fail(path, 'object_required', '这里需要对象或 null。')
        if set(value) - set(spec.fields): fail(path + [sorted(set(value) - set(spec.fields))[0]], 'unknown_fields', '存在不支持的字段；不能保存账单、凭据或结果缓存。')
        if 'id' in spec.fields and 'id' not in value: fail(path + ['id'], 'id_required', '请提供稳定资料编号，不能按列表顺序猜对象。')
        for key, item in value.items(): _validate(item, spec.fields[key], path + [key])
    elif isinstance(spec, Items):
        if not isinstance(value, list) or len(value) > spec.maximum: fail(path, 'list_required', '这里需要未超数量上限的列表或 null。')
        ids = set()
        for n, item in enumerate(value):
            at = path + ([{'id': item.get('id')}] if spec.keyed and isinstance(item, dict) else [n])
            if spec.keyed and not isinstance(item, dict): fail(at, 'row_required', '每条记录须有明确资料编号。')
            _validate(item, spec.item, at)
            ident = item['id'] if spec.keyed else item if spec.item == 'id' else None
            if ident is not None:
                if ident in ids: fail(at, 'duplicate_id', '同一列表的资料编号不能重复；重名物品须用不同记录编号并保留身份歧义。')
                ids.add(ident)
    elif isinstance(spec, Mapping):
        if not isinstance(value, dict) or len(value) > spec.maximum: fail(path, 'map_required', '这里需要按准确资料编号索引、未超数量上限的对象。')
        for key, item in value.items():
            _validate(key, 'id', path + [key])
            _validate(item, spec.item, path + [key])
    else:
        try:
            if spec in ('text', 'id', 'exact'): _text(value, 'value', 80 if spec in ('id','exact') else 1000)
            elif spec == 'money': _num(value, 'value')
            elif spec == 'date': _day(value, 'date')
            elif spec == 'bool':
                if type(value) is not bool: raise ValueError()
            elif spec == 'age':
                if type(value) is not int or not 0 <= value <= 365: raise ValueError()
            elif spec == 'count':
                if type(value) is not int or not 0 <= value <= 12: raise ValueError()
            elif spec == 'node_budget':
                if type(value) is not int or not 1 <= value <= 100_000: raise ValueError()
            elif spec == 'version':
                if type(value) is not int or value != 1: raise ValueError()
            elif isinstance(spec, tuple):
                if value not in spec: raise ValueError()
            else: raise ValueError()
        except (ValueError, TypeError):
            fail(path, 'invalid_value', '值的类型或范围不支持；不知道的事实请用 null，不填零或猜测。')


def _hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid digest')


def checked(data):
    _bounded_json(data)
    _fields(data, ('schema', 'revision', 'request', 'ambiguities', 'source', 'history'), ('combination',))
    if data['schema'] not in (LEGACY_SCHEMA, SCHEMA) or type(data['revision']) is not int or not 1 <= data['revision'] <= 100:
        fail([], 'invalid_draft', '资料版本不支持。')
    if data['schema'] == LEGACY_SCHEMA and 'combination' in data: fail([], 'invalid_draft', '旧资料格式不能夹带组合字段。')
    _text(data['source'], 'source', 2000)
    if not isinstance(data['request'], dict) or not isinstance(data['ambiguities'], list):
        fail([], 'invalid_draft', 'request 须为对象，ambiguities 须为列表。')
    _validate(content(data), ROOT, [])
    history = data['history']
    if not isinstance(history, list) or len(history) != data['revision'] - 1: raise ValueError('Invalid history')
    for rev, row in enumerate(history, 2):
        _fields(row, ('revision', 'source', 'previous_content_sha256', 'changes'), ('previous_schema',))
        if 'previous_schema' in row and row['previous_schema'] != LEGACY_SCHEMA: raise ValueError('Invalid migration schema')
        if type(row['revision']) is not int or row['revision'] != rev: raise ValueError('Invalid history revision')
        _text(row['source'], 'source', 2000); _hash(row['previous_content_sha256'])
        if not isinstance(row['changes'], list) or not 1 <= len(row['changes']) <= (100 if data['schema'] == LEGACY_SCHEMA else 10000): raise ValueError('Invalid changes')
        for change in row['changes']:
            _fields(change, ('path', 'before_present', 'before', 'after_present', 'after'))
            spec = _path_spec(change['path'])
            for stage in ('before', 'after'):
                if type(change[stage + '_present']) is not bool: raise ValueError('Invalid change presence')
                if change[stage + '_present']: _validate(change[stage], spec, change['path'])
                elif change[stage] is not None: raise ValueError('Invalid absent change')
    return copy.deepcopy(data)


def content(data):
    return {key: data[key] for key in ('request', 'ambiguities', 'combination') if key in data}


def digest(data):
    return _json_digest(content(data))


def create(request, source, ambiguities=None, combination=_MISSING):
    data = dict(schema=SCHEMA, revision=1, request=request,
                ambiguities=[] if ambiguities is None else ambiguities, source=source, history=[])
    if combination is not _MISSING: data['combination'] = copy.deepcopy(combination)
    return checked(data)


def _path_spec(path):
    if not isinstance(path, list) or not 1 <= len(path) <= 16: fail([], 'invalid_path', '请使用字段路径和稳定资料编号定位修改。')
    spec = ROOT
    for token in path:
        if isinstance(spec, Obj) and isinstance(token, str) and token in spec.fields:
            spec = spec.fields[token]
        elif isinstance(spec, Mapping) and isinstance(token, str):
            _validate(token, 'id', path); spec = spec.item
        elif isinstance(spec, Items) and spec.keyed and isinstance(token, dict) and set(token) == {'id'}:
            _validate(token['id'], 'id', path); spec = spec.item
        else: fail(path, 'invalid_path', '路径不存在或使用了列表序号；请用 {"id":"资料编号"} 精确定位。')
    return spec


def _locate(root, path):
    current = root
    for token in path[:-1]:
        if isinstance(token, dict):
            if not isinstance(current, list): fail(path, 'missing_parent', '先明确补齐上级字段，再修改其中资料。')
            matches = [row for row in current if row.get('id') == token['id']]
            if len(matches) != 1: fail(path, 'unknown_id', '找不到唯一资料编号；不要用昵称或顺序代替。')
            current = matches[0]
        else:
            if not isinstance(current, dict) or token not in current or current[token] is None:
                fail(path, 'missing_parent', '先明确补齐上级字段，再修改其中资料。')
            current = current[token]
    token = path[-1]
    if isinstance(token, dict):
        if not isinstance(current, list): fail(path, 'missing_parent', '这里不是资料列表。')
        for n, row in enumerate(current):
            if row['id'] == token['id']: return current, n, True
        return current, len(current), False
    if not isinstance(current, dict): fail(path, 'missing_parent', '这里不是字段对象。')
    return current, token, token in current


def edit(data, expected_revision, expected_content_sha256, operations, source):
    data = checked(data)
    if type(expected_revision) is not int or expected_revision != data['revision'] or expected_content_sha256 != digest(data):
        fail([], 'stale_edit', '资料版本已变化，请重开当前文件后再定位修改。')
    _text(source, 'source', 2000)
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100: fail([], 'invalid_operations', '每轮需要 1–100 个明确修改。')
    old_data = copy.deepcopy(data)
    old_hash = digest(data); old_input = copy.deepcopy(data['request'].get('input') or {})
    root = content(data); changes = []; seen = []
    for op in operations:
        _fields(op, ('op', 'path'), ('value',))
        path = op['path']; spec = _path_spec(path)
        # Reject overlapping changes rather than depending on operation order.
        if any(path[:len(p)] == p or p[:len(path)] == path for p in seen): fail(path, 'overlapping_edits', '同轮修改路径重叠，请分两轮明确修改。')
        seen.append(path)
        if (len(path) == 1 and path != ['combination']) or path[-1] == 'id': fail(path, 'immutable_id', '不能替换整个资料容器或修改稳定编号。')
        row_target = isinstance(path[-1], dict)
        if op['op'] not in ('set', 'add', 'remove'): fail(path, 'invalid_operation', '仅支持 set、add 或 remove。')
        if row_target and op['op'] == 'set': fail(path, 'replace_row', '修改已有记录时，请精确到要修改的字段。')
        if op['op'] == 'add' and not row_target: fail(path, 'invalid_add', 'add 只用于带稳定编号的新记录。')
        parent, key, present = _locate(root, path)
        before = copy.deepcopy(parent[key]) if present else None
        if isinstance(spec, Items) and spec.keyed and before:
            fail(path, 'replace_collection', '请按稳定编号逐条添加、移除或修改资料，不能替换整个列表。')
        if isinstance(spec, (Obj, Mapping)) and not row_target and before:
            fail(path, 'replace_object', '已有事实请精确到字段修改，不能整体替换或删除。')
        if op['op'] == 'remove':
            if not present or 'value' in op: fail(path, 'invalid_remove', '只能移除已存在的明确字段或记录。')
            del parent[key]; after = None; after_present = False
        else:
            if 'value' not in op: fail(path, 'missing_value', '请明确提供 value；未知用 null。')
            after = copy.deepcopy(op['value']); _validate(after, spec, path); after_present = True
            if op['op'] == 'add':
                if present or not isinstance(after, dict) or after.get('id') != path[-1]['id']:
                    fail(path, 'invalid_add', '新增编号必须与路径一致且尚未存在。')
                parent.append(after)
            else: parent[key] = after
        changes.append(dict(path=path, before_present=present, before=before,
                            after_present=after_present, after=copy.deepcopy(after)))
    if 'combination' not in root: data.pop('combination', None)
    data.update(root)
    new_input = data['request'].get('input') or {}
    old_date = (old_input.get('context') or {}).get('as_of')
    new_date = (new_input.get('context') or {}).get('as_of')
    if new_date is not None and new_date != old_date:
        previous_ids = {a['id'] for a in old_input.get('assets') or []}
        for asset in new_input.get('assets') or []:
            path = ['request','input','assets',{'id':asset['id']},'availability']
            if asset['id'] in previous_ids and asset.get('availability') in ('confirmed','unavailable') and path not in seen:
                fail(path, 'availability_reconfirmation_required', '修改核实日期不能续期旧库存事实；请逐件明确核实可用性，或明确改为 unknown。')
    _invalidate_confirmations(old_data, data, changes, seen)
    data['revision'] += 1
    row = dict(revision=data['revision'], source=source, previous_content_sha256=old_hash, changes=changes)
    if data['schema'] == LEGACY_SCHEMA: row['previous_schema'] = LEGACY_SCHEMA
    data['schema'] = SCHEMA
    data['history'].append(row)
    return checked(data)


def _invalidate_confirmations(old, data, changes, seen):
    """Conservative invalidation is a recorded fact edit, never fresh confirmation.

    Explicit same-transaction assertions can reconfirm affected fields. Initial
    identification of a previously unknown observed record does not replace that
    record's baseline facts; it still invalidates any prematurely confirmed tags.
    """
    def explicit(path):
        # Existing nonempty parents cannot be replaced; ancestors here initialize new facts only.
        return any(path[:len(p)] == p for p in seen)
    def reset(path, value):
        if explicit(path): return
        parent, key, present = _locate(content(data), path)
        if not present or parent[key] is None or parent[key] == value: return
        before = copy.deepcopy(parent[key]); parent[key] = copy.deepcopy(value)
        changes.append(dict(path=path, before_present=True, before=before, after_present=True, after=value))
    def changed(a, b, keys):
        return any(a.get(k, _MISSING) != b.get(k, _MISSING) for k in keys)
    def rows(inp, key): return {row['id']: row for row in inp.get(key) or []}
    before = old['request'].get('input') or {}; after = data['request'].get('input') or {}
    old_assets, assets = rows(before, 'assets'), rows(after, 'assets')
    old_slots, slots = rows(before, 'slots'), rows(after, 'slots')
    old_combo = old.get('combination') or {}; combo = data.get('combination') or {}
    old_tags, tags = old_combo.get('asset_tag_facts') or {}, combo.get('asset_tag_facts') or {}
    old_reqs, reqs = rows(old_combo, 'role_requirements'), rows(combo, 'role_requirements')
    global_change = changed(before.get('context') or {}, after.get('context') or {}, ('server','currency','ruleset'))
    impacted_assets = {aid for aid, a in assets.items() if aid in old_assets and (
        changed(old_assets[aid], a, ('kind','ownership','basis','label')) or
        (old_assets[aid].get('physical_id') is not None and changed(old_assets[aid], a, ('physical_id',))))}
    impacted_assets.update(set(old_assets) ^ set(assets))
    tag_identity_changes = {aid for aid, a in assets.items() if aid in old_assets and
        changed(old_assets[aid], a, ('physical_id','kind','ownership','basis','label'))}
    tag_identity_changes.update(set(old_assets) ^ set(assets))
    impacted_slots = {sid for sid in set(old_slots) | set(slots) if sid not in old_slots or sid not in slots or
        changed(old_slots[sid], slots[sid], ('role_id','kind','need','basis'))}
    impacted_roles = {row.get('role_id') for sid in impacted_slots for row in
                      (old_slots.get(sid, {}), slots.get(sid, {})) if row.get('role_id') is not None}
    if global_change: impacted_assets.update(assets); tag_identity_changes.update(tags); impacted_roles.update(r.get('role_id') for r in reqs.values())
    old_scope = {r.get('tag') for r in old_reqs.values() if r.get('tag') is not None}
    new_scope = {r.get('tag') for r in reqs.values() if r.get('tag') is not None}
    # Relevant tag facts are only complete for the previously requested labels.
    added_tag_scope = bool(new_scope - old_scope)
    for aid, fact in tags.items():
        if not isinstance(fact, dict): continue
        path = ['combination','asset_tag_facts',aid]
        previous = old_tags.get(aid) or {}
        if aid in tag_identity_changes or added_tag_scope or changed(previous, fact, ('tags','basis')):
            reset(path+['tags_complete'], False)
            reset(path+['user_confirmed'], False)
        elif changed(previous, fact, ('tags_complete',)):
            reset(path+['user_confirmed'], False)
    for rid, req in reqs.items():
        if rid not in old_reqs: continue
        if req.get('role_id') in impacted_roles or old_reqs[rid].get('role_id') in impacted_roles or changed(
                old_reqs[rid], req, ('role_id','tag','min_count','max_count','basis')):
            reset(['combination','role_requirements',{'id':rid},'user_confirmed'], False)
    for aid, a in assets.items():
        path = ['request','input','assets',{'id':aid}]
        previous = old_assets.get(aid) or {}
        if aid in impacted_assets:
            reset(path+['availability'], 'unknown')
            reset(path+['purchase_costs_complete'], False)
        elif aid in old_assets and changed(previous, a, ('purchase_costs',)):
            reset(path+['purchase_costs_complete'], False)
        for sid, fact in (a.get('compatibility') or {}).items():
            if not isinstance(fact, dict): continue
            fp = path+['compatibility',sid]
            prior = (previous.get('compatibility') or {}).get(sid) or {}
            if aid in impacted_assets or sid in impacted_slots or (prior and changed(prior, fact, ('basis',))):
                reset(fp+['eligible'], 'unknown'); reset(fp+['transfer_allowed'], 'unknown'); reset(fp+['fees_complete'], False)
            elif prior and changed(prior, fact, ('fees',)):
                reset(fp+['fees_complete'], False)
    old_rules = {r['id']:r for r in old['request'].get('compatibility_rules') or []}
    for rule in data['request'].get('compatibility_rules') or []:
        previous = old_rules.get(rule['id'])
        if previous is None: continue
        if global_change or set(rule.get('asset_ids') or []) & impacted_assets or set(rule.get('slot_ids') or []) & impacted_slots or changed(
                previous, rule, ('asset_ids','slot_ids','fact')):
            reset(['request','compatibility_rules',{'id':rule['id']},'user_confirmed'], False)


LABELS = dict(schema_version='协议版本', title='这轮要做什么', server='区服', currency='币种', as_of='核实日期',
              budget='总预算', reserve='必须保留的金额', hypothetical='是否接受按明确假设试算',
              slots='同时需要的角色槽位', assets='已有物品及候选商品', physical_id='可核实且不重复的实物身份',
              label='物品名称', role_id='角色资料编号', kind='装备或召唤兽类别', need='具体需求', basis='事实依据',
              ownership='已有还是待购买', purchase_costs='完整购买费用', purchase_costs_complete='购买费用是否已列全',
              availability='在需要时是否可用', compatibility='适用槽位与转移费用', compatibility_rules='明确确认的分组规则（无分组可填空列表）',
              user_confirmed='是否明确确认这组列明的事实', asset_ids='确切物品记录编号', slot_ids='确切槽位记录编号',
              fact='这组的适用、转移及费用事实', eligible='是否适用', transfer_allowed='是否允许转移',
              fees='完整费用', fees_complete='费用是否已列全', quantity='数量', quote='报价', amount='金额',
              observed_on='报价观察日期', source='来源', context='区服、币种和核实日期', input='本轮已知资料', combination='角色组合资料', asset_tag_facts='每件物品的准确标记',
              role_requirements='角色标记件数要求', tags='完整相关标记（确认没有时才填空列表）',
              tags_complete='相关标记是否已列全', tag='准确标记', min_count='至少件数', max_count='最多件数',
              search_node_budget='搜索节点上限')


def _label(path):
    last = next((x for x in reversed(path) if isinstance(x, str)), '')
    ids = [x['id'] for x in path if isinstance(x, dict)]
    if path[:2] == ['combination','asset_tag_facts'] and len(path) > 2: ids.insert(0,path[2])
    return (' / '.join(ids) + '：' if ids else '') + LABELS.get(last, last)


def inspect(data, mode=None):
    """Deterministic questions, no solver, no inference and at most two prompts."""
    data = checked(data); issues = []
    mode = ('combo' if 'combination' in data else 'ordinary') if mode is None else mode
    if mode not in ('ordinary','combo'): raise ValueError('Invalid analysis mode')
    def issue(path, code, question, category='input_blocker'):
        issues.append(dict(path=path, code=code, question=question, category=category))
    def scan(value, spec, path, present=True):
        # Explicit null quote and force cancellation are accepted by strict schema.
        null_allowed = path and path[-1] in ('quote', 'force_assignment')
        if not present or (value is None and not null_allowed):
            category = 'host_requirement' if path[-1] == 'schema_version' else 'input_blocker'
            issue(path, 'unknown' if present else 'missing', '请补充' + _label(path) + '；暂时不知道可继续保留未知。', category); return
        if value is None:
            if path[-1] == 'quote': issue(path, 'quote_unknown', '请核实' + _label(path) + '；未知报价不会当作免费。', 'result_uncertainty')
            return
        if isinstance(spec, Obj):
            for key, child in spec.fields.items():
                if key in spec.optional and key not in value: continue
                scan(value.get(key), child, path + [key], key in value)
        elif isinstance(spec, Items):
            if len(value) < spec.minimum: issue(path, 'empty_required_list', '请列明' + _label(path) + '。')
            for n, item in enumerate(value): scan(item, spec.item, path + ([{'id':item['id']}] if spec.keyed else [n]))
        elif isinstance(spec, Mapping):
            for key, item in value.items(): scan(item, spec.item, path + [key])
        elif value == 'unknown' and isinstance(spec, tuple):
            issue(path, str(path[-1]) + '_unknown', '请核实' + _label(path) + '。', 'result_uncertainty')
        elif value is False and path[-1] in ('fees_complete','purchase_costs_complete'):
            issue(path, str(path[-1]) + '_incomplete', '请核实' + _label(path) + '。', 'result_uncertainty')
    scan(data['request'], REQUEST, ['request'])
    for ambiguity in data['ambiguities']:
        path = ['ambiguities', {'id':ambiguity['id']}]
        issue(path, 'unresolved_identity', '请核实身份疑问 ' + ambiguity['id'] + ' 涉及的记录是否指向同一实物；未核实前不会合并或按多件计算。')
        issues[-1]['asset_ids'] = ambiguity.get('asset_ids') or []
    request = data['request']; inp = request.get('input') or {}; assets = inp.get('assets') or []; slots = inp.get('slots') or []
    asset_ids = {x['id'] for x in assets}; slot_ids = {x['id'] for x in slots}; physical = {}
    for asset in assets:
        path = ['request','input','assets',{'id':asset['id']}]
        pid = asset.get('physical_id')
        if pid:
            if pid in physical: issue(path+['physical_id'], 'duplicate_physical_identity', '这些记录指向同一实物，请核实并明确保留哪条记录：' + physical[pid] + '、' + asset['id'] + '。')
            physical[pid] = asset['id']
        for sid in asset.get('compatibility') or {}:
            if sid not in slot_ids: issue(path+['compatibility',sid], 'unknown_reference', '这个例外引用的槽位未录入，请补齐或明确纠正。')
    for rule in request.get('compatibility_rules') or []:
        path = ['request','compatibility_rules',{'id':rule['id']}]
        if rule.get('user_confirmed') is False:
            issue(path+['user_confirmed'], 'unconfirmed_group', '请确认 ' + rule['id'] + ' 中列明的物品、槽位与事实；不确定可保留，暂不展开。')
        for key, known in [('asset_ids',asset_ids),('slot_ids',slot_ids)]:
            if any(x not in known for x in rule.get(key) or []): issue(path+[key], 'unknown_reference', '分组引用了未录入的记录，请按稳定编号核对。')
    if inp.get('budget') is not None and inp.get('reserve') is not None and _num(inp['reserve'],'reserve') > _num(inp['budget'],'budget'):
        issue(['request','input','reserve'], 'reserve_exceeds_budget', '保留额大于总预算，请核对这两个金额。')
    force = inp.get('force_assignment')
    if force:
        if force.get('asset_id') not in asset_ids or force.get('slot_id') not in slot_ids:
            issue(['request','input','force_assignment'], 'unknown_reference', '指定分配引用的物品或槽位未录入，请核实。')
    # Identify uncovered pairs without expanding or approving group facts.
    covered = {(aid,sid) for rule in request.get('compatibility_rules') or []
               if rule.get('user_confirmed') is True
               for aid in rule.get('asset_ids') or [] for sid in rule.get('slot_ids') or []}
    for asset in assets:
        missing = [s['id'] for s in slots if s['id'] not in (asset.get('compatibility') or {})
                   and (asset['id'],s['id']) not in covered
                   and not (asset.get('kind') and s.get('kind') and asset['kind'] != s['kind'])]
        if missing:
            issue(['request','input','assets',{'id':asset['id']},'compatibility'], 'compatibility_unknown',
                  '请核实 ' + asset['id'] + ' 在 ' + str(len(missing)) + ' 个未覆盖槽位的适用、转移与完整费用；可保留未知。', 'result_uncertainty')
            issues[-1]['slot_ids'] = missing
    if mode == 'combo':
        scan(data.get('combination'), COMBINATION, ['combination'], 'combination' in data)
        combo = data.get('combination') or {}
        facts = combo.get('asset_tag_facts') or {}
        for aid in sorted(asset_ids - set(facts)):
            issue(['combination','asset_tag_facts',aid], 'missing_asset_tags', '请补充 ' + aid + ' 的完整相关标记并确认；未知可先保存。')
        for aid, fact in facts.items():
            path = ['combination','asset_tag_facts',aid]
            if aid not in asset_ids: issue(path, 'unknown_asset_reference', '标记引用的物品未录入；请核对准确资料编号。')
            if not isinstance(fact, dict): continue
            if fact.get('tags_complete') is False: issue(path+['tags_complete'], 'incomplete_tags', '请核实 ' + aid + ' 的相关标记是否已列全；不会把缺漏当作没有。')
            if fact.get('user_confirmed') is False: issue(path+['user_confirmed'], 'unconfirmed_tags', '请确认 ' + aid + ' 的当前标记与依据；旧确认不自动沿用。')
        roles = {s.get('role_id') for s in slots if s.get('role_id') is not None}; pairs = set()
        reqs = combo.get('role_requirements') or []
        distinct = {t for f in facts.values() if isinstance(f,dict) for t in f.get('tags') or []}
        for req in reqs:
            path = ['combination','role_requirements',{'id':req['id']}]
            role, tag = req.get('role_id'), req.get('tag')
            if role is not None and role not in roles: issue(path+['role_id'], 'unknown_role_reference', '这个角色没有已列入的槽位；请核对角色编号。')
            if role is not None and tag is not None:
                if (role,tag) in pairs: issue(path, 'duplicate_role_tag', '同一角色的同一标记请合并为一条最少/最多要求。')
                pairs.add((role,tag))
            if tag is not None: distinct.add(tag)
            if req.get('user_confirmed') is False: issue(path+['user_confirmed'], 'unconfirmed_requirement', '请确认 ' + req['id'] + ' 的角色、标记与件数要求。')
            low, high = req.get('min_count'), req.get('max_count',12)
            if low is not None and high is not None and low > high: issue(path+['max_count'], 'inverted_counts', '最少件数大于最多件数，请核对。')
        for path, over in [(['request','input','slots'],len(slots)>12), (['request','input','assets'],len(assets)>24),
                           (['combination','role_requirements'],len(roles)>5), (['combination','asset_tag_facts'],len(distinct)>24)]:
            if over: issue(path, 'combo_limit', '超过组合试算上限（12位置、24物品、5角色、24标记）；请明确缩小本次范围，不能自动删减。')
    blockers = [x for x in issues if x['category'] in ('input_blocker','host_requirement')]
    # Deterministic structural-first order; does not claim economic priority.
    ordered = blockers + [x for x in issues if x['category']=='result_uncertainty']
    return dict(status='needs_input' if blockers else 'ready_for_strict_validation',
                charged=False, analysis_returned=False, analysis_mode=mode, content_sha256=digest(data), revision=data['revision'],
                next_questions=[x for x in ordered if x['category']!='host_requirement'][:2],
                host_requirements=[x for x in blockers if x['category']=='host_requirement'], issues=ordered,
                warning='通过资料检查也不代表事实已确认或当前可用；分析前仍执行原严格校验。补问按资料顺序，未证明最优问题排序。')
