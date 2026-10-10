/* Original offline comparison engine. No network, storage, libraries or game formulas. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.MHXYEngine = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const MAX_BYTES = 1000000, MAX_DEPTH = 32, MAX_OPTIONS = 64, MAX_METRICS = 12;
  const MAX_SLOTS = 12, MAX_COMBINATIONS = 10000, MAX_PARETO_CHECKS = 2000000, MAX_PARETO_RETURN = 100;
  const SCALE = 1000000n, MAX_VALUE = 1000000000000n * SCALE;
  const TOKEN = Symbol('exact JSON numeric token');
  const NUMBER_RE = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
  const ID_RE = /^[a-z][a-z0-9_-]{0,63}$/;
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v) && !isNumeric(v);
  const compareText = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  const DISCLAIMER = [
    '本结果仅比较你录入的数据、目标与取舍；高级模式使用用户自定义线性偏好，不是游戏真实伤害、收益保证或真实最优配装。',
    '价格、面板增量、指标方向及可选高级权重均由用户提供；未联网核价或验证游戏机制。',
    '按槽位增量可相加；面板上下限仅为你设置的筛选条件，不代表已验证的战斗阈值。套装联动、战斗公式、隐藏属性和未录入限制不在模型内。',
    '零花费基线始终单独展示；免费提升可能使基线不在 Pareto 前沿。'
  ];
  const OBJECTIVES = ['weighted', 'min_cost', 'pareto'];
  const OBJECTIVE_LABELS = { weighted: '高级：按自定义权重比较', min_cost: '满足全部条件后花费最少', pareto: '不设权重，查看 Pareto 取舍' };
  const MODELS = { weighted: 'user_defined_linear_preferences', min_cost: 'user_defined_min_cost', pareto: 'user_defined_pareto' };
  const RANKING_RULES = {
    weighted: '偏好分降序；同分时花费升序、变更件数升序、按槽位排序后的候选 ID 字典序。',
    min_cost: '满足全部条件后花费升序；同价时变更件数升序、按槽位排序后的候选 ID 字典序。权重不参与排序，同价可能有多个达标方案。',
    pareto: '不指定唯一最优方案；Pareto 取舍仅按花费升序、变更件数升序、按槽位排序后的候选 ID 字典序展示，展示顺序不代表推荐排名。'
  };
  class InputError extends Error {
    constructor(message, path) { super(message); this.name = 'InputError'; this.path = path || 'input'; }
  }
  function fail(message, path) { throw new InputError(message, path); }
  function isNumeric(value) { return !!(value && typeof value === 'object' && value[TOKEN] === true); }
  function numeric(text) {
    if (typeof text !== 'string' || !NUMBER_RE.test(text)) fail('必须输入完整、有限的 JSON 数值', 'number');
    const token = Object.create(null);
    Object.defineProperties(token, {
      [TOKEN]: { value: true }, lexeme: { value: text, enumerable: false },
      toString: { value: function () { return this.lexeme; } },
      valueOf: { value: function () { throw new TypeError('精确数值不可隐式转换为 Number'); } }
    });
    return Object.freeze(token);
  }
  function byteLength(text) {
    let length = 0;
    for (const ch of text) { const cp = ch.codePointAt(0); length += cp <= 0x7f ? 1 : cp <= 0x7ff ? 2 : cp <= 0xffff ? 3 : 4; }
    return length;
  }
  function parse(text, limit) {
    limit = limit === undefined ? MAX_BYTES : limit;
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 16000000) fail('JSON 大小上限无效', 'input');
    if (typeof text !== 'string' || !text.trim()) fail('请先输入 JSON', 'input');
    if (byteLength(text) > limit) fail('JSON 超过 ' + limit + ' 字节上限', 'input');
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    let i = 0;
    const white = () => { while (i < text.length && /[ \t\r\n]/.test(text[i])) i++; };
    function str() {
      const start = i++;
      while (i < text.length) {
        const ch = text[i++];
        if (ch === '"') { try { return JSON.parse(text.slice(start, i)); } catch (_) { fail('JSON 字符串无效', 'input'); } }
        if (ch === '\\') i++;
        else if (ch.charCodeAt(0) < 32) fail('JSON 字符串不允许未转义控制字符', 'input');
      }
      fail('JSON 字符串未结束', 'input');
    }
    function value(depth) {
      white(); const ch = text[i];
      if (ch === '"') return str();
      if (ch === '{' || ch === '[') {
        if (depth >= MAX_DEPTH) fail('JSON 嵌套不能超过 32 层', 'input');
        const array = ch === '[', out = array ? [] : {}, keys = new Set(); i++; white();
        const close = array ? ']' : '}';
        if (text[i] === close) { i++; return out; }
        for (;;) {
          let key;
          if (!array) {
            if (text[i] !== '"') fail('JSON 对象键必须是字符串', 'input');
            key = str();
            if (keys.has(key)) fail('JSON 对象含重复键: ' + key, 'input');
            keys.add(key); white();
            if (text[i++] !== ':') fail('JSON 对象键后缺少冒号', 'input');
          }
          const item = value(depth + 1);
          if (array) out.push(item);
          else Object.defineProperty(out, key, { value: item, enumerable: true, writable: true, configurable: true });
          white();
          if (text[i] === close) { i++; return out; }
          if (text[i++] !== ',') fail('JSON 数组或对象缺少逗号或结束符', 'input');
          white();
        }
      }
      for (const pair of [['true', true], ['false', false], ['null', null]]) {
        if (text.slice(i, i + pair[0].length) === pair[0]) { i += pair[0].length; return pair[1]; }
      }
      const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(i));
      if (!match) fail('JSON 数值或语法无效，位置 ' + i, 'input');
      i += match[0].length; return numeric(match[0]);
    }
    const result = value(0); white();
    if (i !== text.length) fail('JSON 存在多余内容或无效数值，位置 ' + i, 'input');
    return result;
  }
  function stringify(data, indent) {
    if (indent === undefined) indent = 2;
    const space = typeof indent === 'number' ? ' '.repeat(Math.max(0, Math.min(10, Math.floor(indent)))) : String(indent).slice(0, 10);
    const stack = new Set(); let outputBytes = 0;
    function output(s, repeats) { outputBytes += byteLength(s) * (repeats === undefined ? 1 : repeats); if (outputBytes > 16000000) fail('格式化后内容超过 16 MB 安全上限', 'input'); return s; }
    function serialize(v, depth) {
      if (isNumeric(v)) return output(v.lexeme);
      if (v === null || typeof v === 'boolean' || typeof v === 'string') return output(JSON.stringify(v));
      if (typeof v === 'number') { if (!Number.isFinite(v)) fail('JSON 不允许非有限数值', 'input'); return output(JSON.stringify(v)); }
      if (typeof v !== 'object') fail('JSON 不支持此值类型', 'input');
      if (depth >= MAX_DEPTH) fail('JSON 嵌套不能超过 32 层', 'input');
      if (stack.has(v)) fail('JSON 不允许循环引用', 'input');
      stack.add(v);
      const arr = Array.isArray(v), keys = arr ? null : Object.keys(v), len = arr ? v.length : keys.length;
      const parts = [];
      for (let index = 0; index < len; index++) {
        const key = arr ? index : keys[index];
        const prefix = arr ? '' : output(JSON.stringify(key) + (space ? ': ' : ':'));
        parts.push(output(space.repeat(depth + 1)) + prefix + serialize(v[key], depth + 1));
      }
      stack.delete(v);
      if (!len) return output(arr ? '[]' : '{}');
      const opening = arr ? '[' : '{', closing = arr ? ']' : '}';
      return output(opening + (space ? '\n' : '')) + parts.join(output(space ? ',\n' : ',', Math.max(0, len - 1))) + output((space ? '\n' + space.repeat(depth) : '') + closing);
    }
    return serialize(data, 0);
  }
  function fields(obj, required, optional, path) {
    if (!object(obj)) fail(path + ' 必须为对象', path);
    const missing = required.filter(k => !own(obj, k)).sort(), extra = Object.keys(obj).filter(k => !required.includes(k) && !optional.includes(k)).sort();
    if (missing.length) fail(path + ' 缺少字段: ' + missing.join(', ') + '；未知值不能自动补零', path + '.' + missing[0]);
    if (extra.length) fail(path + ' 含未知字段: ' + extra.join(', '), path + '.' + extra[0]);
  }
  function string(value, path, limit) {
    limit = limit || 200;
    if (typeof value !== 'string' || !value.trim() || Array.from(value).length > limit) fail(path + ' 必须为 1–' + limit + ' 字符的非空字符串', path);
    for (const ch of value) { const cp = ch.codePointAt(0); if (cp < 32 || (cp >= 0xd800 && cp <= 0xdfff)) fail(path + ' 不允许控制字符或无效 Unicode 代理码点', path); }
    return value;
  }
  function identifier(value, path) { string(value, path, 64); if (!ID_RE.test(value)) fail(path + ' 需小写字母开头，仅允许小写字母、数字、下划线与连字符', path); return value; }
  function number(value, path, nonnegative) {
    let token;
    if (isNumeric(value)) token = value.lexeme;
    else if (typeof value === 'number' && Number.isFinite(value)) token = String(value);
    else fail(path + ' 必须为 JSON 数值（不能是字符串、null 或布尔值）', path);
    const m = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(token);
    if (!m) fail(path + ' 数值无效', path);
    const exponentText = m[4] || '0';
    if (exponentText.replace(/^[+-]?0*/, '').length > 6) fail(path + ' 数值指数超出安全范围', path);
    const exponent = BigInt(exponentText) - BigInt((m[3] || '').length);
    if (exponent < -6n) fail(path + ' 最多保留 6 位小数', path);
    const digits = (m[2] + (m[3] || '')).replace(/^0+/, '');
    if (digits && BigInt(digits.length) + exponent > 13n) fail(path + ' 绝对值不能超过 10^12', path);
    let result = 0n;
    if (digits) result = BigInt(digits) * (10n ** (exponent + 6n)) * (m[1] ? -1n : 1n);
    if (result > MAX_VALUE || result < -MAX_VALUE) fail(path + ' 绝对值不能超过 10^12', path);
    if (nonnegative && result < 0n) fail(path + ' 不能为负数', path);
    return result;
  }
  function integer(value, path, lo, hi) { const v = number(value, path, true); if (v % SCALE || v < BigInt(lo) * SCALE || v > BigInt(hi) * SCALE) fail(path + ' 必须为 ' + lo + '–' + hi + ' 的整数', path); return Number(v / SCALE); }
  function fmt(value, places) {
    places = places === undefined ? 6 : places;
    if (value === 0n) return '0';
    const negative = value < 0n, digits = (negative ? -value : value).toString().padStart(places + 1, '0');
    const result = places ? (digits.slice(0, -places) + '.' + digits.slice(-places)).replace(/0+$/, '').replace(/\.$/, '') : digits;
    return (negative ? '-' : '') + result;
  }
  function formattedMap(map) { return Object.fromEntries(Object.keys(map).map(k => [k, fmt(map[k])])); }
  function exactMap(obj, ids, path, weights) {
    fields(obj, ids, [], path); const result = {};
    for (const id of ids) result[id] = number(obj[id], path + '.' + id, !!weights);
    if (weights && !ids.some(id => result[id] > 0n)) fail(path + ' 至少一个权重必须大于零', path);
    return result;
  }
  function partialMap(obj, ids, path) { fields(obj, [], ids, path); const result = {}; for (const id of ids) if (own(obj, id)) result[id] = number(obj[id], path + '.' + id); return result; }
  function evidence(value, path) { if (!['user_confirmed', 'unverified', 'synthetic'].includes(value)) fail(path + ' 仅允许 user_confirmed / unverified / synthetic', path); return value; }
  function collection(value, path, max) { if (!Array.isArray(value) || value.length > max) fail(path + ' 必须是数组，最多 ' + max + ' 项', path); return value; }
  function idList(value, path, permitted, max) {
    collection(value, path, max); const result = [], seen = new Set();
    value.forEach((id, i) => { identifier(id, path + '[' + i + ']'); if (!permitted.has(id)) fail(path + ' 含未知 ID: ' + id, path + '[' + i + ']'); if (seen.has(id)) fail(path + ' 含重复 ID: ' + id, path + '[' + i + ']'); seen.add(id); result.push(id); });
    return result;
  }
  function validate(data) {
    fields(data, ['schema_version', 'budget', 'currency', 'metrics', 'baseline', 'options'], ['objective', 'weights', 'title', 'notes', 'top_n', 'character', 'constraints', 'budget_scenarios', 'weight_scenarios', 'manual_plans', 'checklist'], 'input');
    if (data.schema_version !== '1.0') fail('schema_version 必须为字符串 "1.0"', 'schema_version');
    const cfg = { title: string(own(data, 'title') ? data.title : '手工录入方案比较', 'title'), budget: number(data.budget, 'budget', true), currency: string(data.currency, 'currency', 40) };
    if (own(data, 'notes')) string(data.notes, 'notes', 4000);
    cfg.notes = own(data, 'notes') ? data.notes : '';
    collection(data.metrics, 'metrics', MAX_METRICS); if (!data.metrics.length) fail('metrics 需包含 1–12 个指标', 'metrics');
    cfg.ids = []; cfg.metrics = [];
    data.metrics.forEach((m, i) => {
      const p = 'metrics[' + i + ']'; fields(m, ['id', 'name', 'unit', 'direction'], [], p); const id = identifier(m.id, p + '.id');
      if (cfg.ids.includes(id)) fail('重复指标 ID: ' + id, p + '.id'); cfg.ids.push(id);
      string(m.name, p + '.name'); string(m.unit, p + '.unit', 40);
      if (!['maximize', 'minimize'].includes(m.direction)) fail(p + '.direction 仅允许 maximize / minimize', p + '.direction');
      cfg.metrics.push({ id, name: m.name, unit: m.unit, direction: m.direction });
    });
    cfg.objective = own(data, 'objective') ? data.objective : own(data, 'weights') ? 'weighted' : 'pareto';
    if (!OBJECTIVES.includes(cfg.objective)) fail('objective 仅允许 weighted / min_cost / pareto', 'objective');
    if (cfg.objective === 'weighted' && !own(data, 'weights')) fail('objective=weighted 需要完整 weights；不想设置权重可选 min_cost 或 pareto', 'weights');
    cfg.weights = own(data, 'weights') ? exactMap(data.weights, cfg.ids, 'weights', true) : null;
    fields(data.baseline, ['label', 'stats'], ['equipment', 'evidence'], 'baseline');
    cfg.baseline_label = string(data.baseline.label, 'baseline.label'); cfg.stats = exactMap(data.baseline.stats, cfg.ids, 'baseline.stats');
    cfg.baseline_evidence = evidence(own(data.baseline, 'evidence') ? data.baseline.evidence : 'unverified', 'baseline.evidence');
    cfg.equipment = {};
    if (own(data.baseline, 'equipment')) {
      if (!object(data.baseline.equipment)) fail('baseline.equipment 必须为对象', 'baseline.equipment');
      for (const slot of Object.keys(data.baseline.equipment).sort()) cfg.equipment[identifier(slot, 'baseline.equipment.' + slot)] = string(data.baseline.equipment[slot], 'baseline.equipment.' + slot);
    }
    collection(data.options, 'options', MAX_OPTIONS); cfg.options = []; cfg.slots = {}; cfg.optionById = new Map();
    data.options.forEach((o, i) => {
      const p = 'options[' + i + ']'; fields(o, ['id', 'name', 'slot', 'price'], ['deltas', 'measured_stats', 'notes', 'fees', 'owned', 'evidence', 'source'], p);
      if (own(o, 'deltas') === own(o, 'measured_stats')) fail(p + ' 必须且只能提供 deltas / measured_stats 之一', p);
      const id = identifier(o.id, p + '.id'), slot = identifier(o.slot, p + '.slot');
      if (cfg.optionById.has(id)) fail('重复候选 ID: ' + id, p + '.id');
      const clean = { id, name: string(o.name, p + '.name'), slot, price: number(o.price, p + '.price', true), fees: number(own(o, 'fees') ? o.fees : 0, p + '.fees', true), owned: own(o, 'owned') ? o.owned : false, evidence: evidence(own(o, 'evidence') ? o.evidence : 'unverified', p + '.evidence') };
      if (typeof clean.owned !== 'boolean') fail(p + '.owned 必须为布尔值', p + '.owned');
      if (clean.owned && clean.price !== 0n) fail(p + '.owned 为 true 时 price 必须为 0', p + '.price');
      clean.total_cost = clean.price + clean.fees;
      const key = own(o, 'deltas') ? 'deltas' : 'measured_stats', values = exactMap(o[key], cfg.ids, p + '.' + key);
      clean.deltas = Object.fromEntries(cfg.ids.map(mid => [mid, key === 'deltas' ? values[mid] : values[mid] - cfg.stats[mid]]));
      for (const key of ['source', 'notes']) if (own(o, key)) clean[key] = string(o[key], p + '.' + key, key === 'source' ? 1000 : 4000);
      cfg.options.push(clean); cfg.optionById.set(id, clean); if (!own(cfg.slots, slot)) cfg.slots[slot] = []; cfg.slots[slot].push(clean);
    });
    const allSlots = new Set([...Object.keys(cfg.slots), ...Object.keys(cfg.equipment)]);
    if (allSlots.size > MAX_SLOTS) fail('槽位最多 12 个（包括当前装备槽位）', 'options');
    cfg.combinations = Object.values(cfg.slots).reduce((n, choices) => n * (choices.length + 1), 1);
    if (cfg.combinations > MAX_COMBINATIONS) fail('组合数 ' + cfg.combinations + ' 超过上限 10000；请减少候选/槽位，不会返回部分最优结果', 'options');
    cfg.top_n = integer(own(data, 'top_n') ? data.top_n : 10, 'top_n', 1, 50);
    cfg.character = {};
    if (own(data, 'character')) {
      fields(data.character, [], ['level', 'school', 'server', 'purpose'], 'character');
      if (own(data.character, 'level')) cfg.character.level = String(integer(data.character.level, 'character.level', 1, 200));
      for (const k of ['school', 'server', 'purpose']) if (own(data.character, k)) cfg.character[k] = string(data.character[k], 'character.' + k);
    }
    const c = own(data, 'constraints') ? data.constraints : {};
    fields(c, [], ['min_stats', 'max_stats', 'locked_slots', 'required_options', 'excluded_options', 'conflicts', 'max_changes'], 'constraints');
    const optionIDs = new Set(cfg.optionById.keys());
    cfg.constraints = {
      min_stats: partialMap(own(c, 'min_stats') ? c.min_stats : {}, cfg.ids, 'constraints.min_stats'),
      max_stats: partialMap(own(c, 'max_stats') ? c.max_stats : {}, cfg.ids, 'constraints.max_stats'),
      locked_slots: idList(own(c, 'locked_slots') ? c.locked_slots : [], 'constraints.locked_slots', allSlots, 12),
      required_options: idList(own(c, 'required_options') ? c.required_options : [], 'constraints.required_options', optionIDs, 64),
      excluded_options: idList(own(c, 'excluded_options') ? c.excluded_options : [], 'constraints.excluded_options', optionIDs, 64),
      conflicts: [], max_changes: integer(own(c, 'max_changes') ? c.max_changes : 12, 'constraints.max_changes', 0, 12)
    };
    const cc = cfg.constraints;
    for (const id of cfg.ids) if (own(cc.min_stats, id) && own(cc.max_stats, id) && cc.min_stats[id] > cc.max_stats[id]) fail('constraints: ' + id + ' 最低目标不能高于最高目标', 'constraints.min_stats.' + id);
    collection(own(c, 'conflicts') ? c.conflicts : [], 'constraints.conflicts', 128).forEach((pair, i) => {
      if (!Array.isArray(pair) || pair.length !== 2) fail('constraints.conflicts[' + i + '] 必须恰好包含两个候选 ID', 'constraints.conflicts[' + i + ']');
      const cleanPair = idList(pair, 'constraints.conflicts[' + i + ']', optionIDs, 2).sort();
      if (cc.conflicts.some(previous => previous[0] === cleanPair[0] && previous[1] === cleanPair[1])) fail('constraints.conflicts 含重复冲突对', 'constraints.conflicts[' + i + ']');
      cc.conflicts.push(cleanPair);
    });
    const requiredSlots = new Set();
    for (const id of cc.required_options) {
      const o = cfg.optionById.get(id);
      if (cc.excluded_options.includes(id)) fail('必选候选不能同时被排除: ' + id, 'constraints.required_options');
      if (cc.locked_slots.includes(o.slot)) fail('必选候选与保持当前装备的锁定槽位冲突: ' + id, 'constraints.required_options');
      if (requiredSlots.has(o.slot)) fail('同一槽位不能指定两个必选候选: ' + o.slot, 'constraints.required_options');
      requiredSlots.add(o.slot);
    }
    if (cc.required_options.length > cc.max_changes) fail('必选候选数超过 max_changes', 'constraints.max_changes');
    if (cc.conflicts.some(pair => pair.every(id => cc.required_options.includes(id)))) fail('必选候选之间存在冲突', 'constraints.conflicts');
    function scenarios(key, max, parseItem) {
      const labels = new Set(); return collection(own(data, key) ? data[key] : [], key, max).map((item, i) => {
        const p = key + '[' + i + ']'; if (!object(item)) fail(p + ' 必须为对象', p);
        const label = string(item.label, p + '.label'); if (labels.has(label)) fail(key + ' 标签必须唯一: ' + label, p + '.label'); labels.add(label); return parseItem(item, p, label);
      });
    }
    cfg.budget_scenarios = scenarios('budget_scenarios', 8, (s, p, label) => { fields(s, ['label', 'budget'], [], p); return { label, budget: number(s.budget, p + '.budget', true) }; });
    cfg.weight_scenarios = scenarios('weight_scenarios', 8, (s, p, label) => { fields(s, ['label', 'weights'], [], p); return { label, weights: exactMap(s.weights, cfg.ids, p + '.weights', true) }; });
    cfg.manual_plans = scenarios('manual_plans', 2, (s, p, label) => {
      fields(s, ['label', 'option_ids'], [], p); const ids = idList(s.option_ids, p + '.option_ids', optionIDs, MAX_SLOTS), slots = new Set();
      for (const id of ids) { const slot = cfg.optionById.get(id).slot; if (slots.has(slot)) fail(p + ' 同一槽位只能选一个候选', p + '.option_ids'); slots.add(slot); }
      return { label, option_ids: ids };
    });
    cfg.checklist = collection(own(data, 'checklist') ? data.checklist : [], 'checklist', 20).map((item, i) => {
      const p = 'checklist[' + i + ']'; fields(item, ['item', 'status'], ['note'], p);
      const out = { item: string(item.item, p + '.item'), status: item.status };
      if (!['confirmed', 'unverified', 'not_applicable'].includes(out.status)) fail(p + '.status 仅允许 confirmed / unverified / not_applicable', p + '.status');
      if (own(item, 'note')) out.note = string(item.note, p + '.note', 1000); return out;
    });
    return cfg;
  }
  function diagnose(data) {
    const issues = [], seen = new Set();
    const add = (path, message) => { if (!seen.has(path + '\n' + message)) { seen.add(path + '\n' + message); issues.push({ path, message }); } };
    const checkNumber = (value, path, nonnegative) => { try { number(value, path, nonnegative); } catch (e) { add(path, e.message); } };
    if (object(data)) {
      checkNumber(data.budget, 'budget', true);
      const metrics = Array.isArray(data.metrics) && data.metrics.length <= MAX_METRICS ? data.metrics.filter(object) : [];
      const ids = [...new Set(metrics.map(m => m.id).filter(id => typeof id === 'string' && ID_RE.test(id)))];
      const cells = (map, path, complete, nonnegative) => { if (!object(map)) { add(path, path + ' 必须为对象'); return; } for (const id of complete ? ids : Object.keys(map)) checkNumber(map[id], path + '.' + id, nonnegative); };
      if (own(data, 'weights') || data.objective === 'weighted') cells(data.weights, 'weights', true, true);
      cells(object(data.baseline) ? data.baseline.stats : undefined, 'baseline.stats', true, false);
      if (Array.isArray(data.options) && data.options.length <= MAX_OPTIONS) data.options.forEach((o, i) => {
        if (!object(o)) return; const p = 'options[' + i + ']'; checkNumber(o.price, p + '.price', true); if (own(o, 'fees')) checkNumber(o.fees, p + '.fees', true);
        if (own(o, 'measured_stats')) cells(o.measured_stats, p + '.measured_stats', true, false);
        if (own(o, 'deltas') || !own(o, 'measured_stats')) cells(o.deltas, p + '.deltas', true, false);
      });
      if (object(data.constraints)) for (const key of ['min_stats', 'max_stats']) if (own(data.constraints, key)) cells(data.constraints[key], 'constraints.' + key, false, false);
      if (Array.isArray(data.budget_scenarios) && data.budget_scenarios.length <= 8) data.budget_scenarios.forEach((s, i) => checkNumber(object(s) ? s.budget : undefined, 'budget_scenarios[' + i + '].budget', true));
      if (Array.isArray(data.weight_scenarios) && data.weight_scenarios.length <= 8) data.weight_scenarios.forEach((s, i) => cells(object(s) ? s.weights : undefined, 'weight_scenarios[' + i + '].weights', true, true));
      if (own(data, 'top_n')) checkNumber(data.top_n, 'top_n', true);
      if (object(data.character) && own(data.character, 'level')) checkNumber(data.character.level, 'character.level', true);
      if (object(data.constraints) && own(data.constraints, 'max_changes')) checkNumber(data.constraints.max_changes, 'constraints.max_changes', true);
    }
    try { validate(data); } catch (e) { if (!issues.some(issue => issue.path === e.path)) add(e.path || 'input', e.message); }
    return { ready: issues.length === 0, issues };
  }
  function rank(a, b) {
    if (a.score !== b.score) return a.score > b.score ? -1 : 1;
    if (a.price !== b.price) return a.price < b.price ? -1 : 1;
    if (a.selection.length !== b.selection.length) return a.selection.length - b.selection.length;
    for (let i = 0; i < a.selection.length; i++) { const cmp = compareText(a.selection[i].id, b.selection[i].id); if (cmp) return cmp; }
    return 0;
  }
  function calculate(data) {
    const cfg = validate(data), ids = cfg.ids, c = cfg.constraints;
    const signs = Object.fromEntries(cfg.metrics.map(m => [m.id, m.direction === 'maximize' ? 1n : -1n]));
    function baseCombo(selected) {
      selected = selected.slice().sort((a, b) => compareText(a.slot, b.slot) || compareText(a.id, b.id));
      const price = selected.reduce((sum, o) => sum + o.total_cost, 0n);
      const deltas = Object.fromEntries(ids.map(id => [id, selected.reduce((sum, o) => sum + o.deltas[id], 0n)]));
      const final_stats = Object.fromEntries(ids.map(id => [id, cfg.stats[id] + deltas[id]]));
      const chosen = new Set(selected.map(o => o.id)), violations = [];
      for (const id of ids) {
        if (own(c.min_stats, id) && final_stats[id] < c.min_stats[id]) violations.push(id + ' 距下限 ' + fmt(c.min_stats[id]) + ' 还差 ' + fmt(c.min_stats[id] - final_stats[id]));
        if (own(c.max_stats, id) && final_stats[id] > c.max_stats[id]) violations.push(id + ' 超过上限 ' + fmt(c.max_stats[id]) + ' 共 ' + fmt(final_stats[id] - c.max_stats[id]));
      }
      for (const slot of c.locked_slots) if (selected.some(o => o.slot === slot)) violations.push('锁定槽位必须保持当前装备: ' + slot);
      for (const id of c.required_options) if (!chosen.has(id)) violations.push('缺少必选候选: ' + id);
      for (const id of c.excluded_options) if (chosen.has(id)) violations.push('包含已排除候选: ' + id);
      for (const pair of c.conflicts) if (pair.every(id => chosen.has(id))) violations.push('候选冲突: ' + pair.join(' + '));
      if (selected.length > c.max_changes) violations.push('变更件数超过上限 ' + c.max_changes);
      return { selection: selected, price, deltas, final_stats, is_baseline: !selected.length, constraint_violations: violations, drawbacks: ids.filter(id => deltas[id] * signs[id] < 0n) };
    }
    function evaluated(combo, budget, weights) {
      const violations = (combo.price > budget ? ['超出预算 ' + fmt(combo.price - budget) + ' ' + cfg.currency] : []).concat(combo.constraint_violations);
      return Object.assign({}, combo, { score: weights === null ? null : ids.reduce((sum, id) => sum + weights[id] * signs[id] * combo.deltas[id], 0n), remaining_budget: budget - combo.price, violations, feasible: !violations.length });
    }
    function publicCombo(combo) {
      const selection = combo.selection.map(o => {
        const item = { id: o.id, name: o.name, slot: o.slot, quoted_price: fmt(o.price), fees: fmt(o.fees), total_cost: fmt(o.total_cost), owned: o.owned, evidence: o.evidence };
        item.source = own(o, 'source') ? o.source : '';
        item.notes = own(o, 'notes') ? o.notes : '';
        item.replaces = own(cfg.equipment, o.slot) ? cfg.equipment[o.slot] : '当前槽位装备';
        return item;
      });
      const out = { selection, price: fmt(combo.price), remaining_budget: fmt(combo.remaining_budget), deltas: formattedMap(combo.deltas), final_stats: formattedMap(combo.final_stats), score: combo.score === null ? null : fmt(combo.score, 12), is_baseline: combo.is_baseline, feasible: combo.feasible, violations: combo.violations.slice(), drawbacks: combo.drawbacks.slice() };
      if (own(combo, 'equivalent_count')) out.equivalent_count = combo.equivalent_count;
      return out;
    }
    const all = [], slots = Object.keys(cfg.slots).sort();
    function enumerate(index, selected) {
      if (index === slots.length) { all.push(baseCombo(selected)); return; }
      enumerate(index + 1, selected);
      for (const o of cfg.slots[slots[index]].slice().sort((a, b) => compareText(a.id, b.id))) { selected.push(o); enumerate(index + 1, selected); selected.pop(); }
    }
    enumerate(0, []);
    const activeWeights = cfg.objective === 'weighted' ? cfg.weights : null;
    const primary = all.map(combo => evaluated(combo, cfg.budget, activeWeights)), feasible = primary.filter(combo => combo.feasible).sort(rank), baseline = primary.find(combo => combo.is_baseline);
    const vectorKey = combo => [combo.price, ...ids.map(id => combo.deltas[id])].join('|');
    function paretoFrontier(feasible) {
      const distinct = new Map();
      for (const combo of feasible) { const key = vectorKey(combo); if (!distinct.has(key)) distinct.set(key, Object.assign({}, combo, { equivalent_count: 1 })); else distinct.get(key).equivalent_count++; }
      function dominates(a, b) {
        if (a.price > b.price) return false; let strict = a.price < b.price;
        for (const id of ids) { const av = a.deltas[id] * signs[id], bv = b.deltas[id] * signs[id]; if (av < bv) return false; if (av > bv) strict = true; }
        return strict;
      }
      let frontier = [], checks = 0;
      for (const candidate of distinct.values()) {
        const remove = new Set(); let rejected = false;
        for (let i = 0; i < frontier.length; i++) {
          if (++checks > MAX_PARETO_CHECKS) fail('Pareto 比较超过 2000000 次安全上限；请减少候选或指标。未输出不完整结果', 'options');
          if (dominates(frontier[i], candidate)) { rejected = true; break; }
          if (dominates(candidate, frontier[i])) remove.add(i);
        }
        if (!rejected) { frontier = frontier.filter((_, i) => !remove.has(i)); frontier.push(candidate); }
      }
      frontier.sort(rank);
      return { frontier, distinctCount: distinct.size, checks };
    }
    const { frontier, distinctCount, checks } = paretoFrontier(feasible);
    const baselineOut = publicCombo(baseline);
    Object.assign(baselineOut, { label: cfg.baseline_label, on_pareto: baseline.feasible && frontier.some(combo => vectorKey(combo) === vectorKey(baseline)), equipment: Object.assign({}, cfg.equipment), evidence: cfg.baseline_evidence });
    function scenarioBest(budget, weights, objective) {
      const choices = all.map(combo => evaluated(combo, budget, weights)).filter(combo => combo.feasible).sort(rank);
      const result = { objective, best: choices.length && objective !== 'pareto' ? publicCombo(choices[0]) : null, feasible_count: choices.length };
      if (objective === 'pareto') {
        const { frontier } = paretoFrontier(choices);
        Object.assign(result, { pareto: frontier.slice(0, MAX_PARETO_RETURN).map(publicCombo), pareto_total: frontier.length, pareto_shown: Math.min(frontier.length, MAX_PARETO_RETURN), pareto_truncated: frontier.length > MAX_PARETO_RETURN });
      }
      return result;
    }
    const evidenceSummary = { confirmed_options: cfg.options.filter(o => o.evidence === 'user_confirmed').length, unverified_options: cfg.options.filter(o => o.evidence === 'unverified').length, synthetic_options: cfg.options.filter(o => o.evidence === 'synthetic').length, baseline_evidence: cfg.baseline_evidence, notice: '证据状态和检查清单仅为用户声明，未独立验证候选、价格、角色面板或游戏机制。' };
    const diagnostics = [];
    if (!feasible.length) diagnostics.push({ kind: 'no_feasible_plan', message: '没有同时满足预算和全部限制的方案；当前装备仍作为零变更参考展示。' });
    if (cfg.baseline_evidence !== 'user_confirmed' || evidenceSummary.unverified_options || evidenceSummary.synthetic_options || cfg.checklist.some(item => item.status === 'unverified')) diagnostics.push({ kind: 'missing_evidence', message: '部分输入尚未由用户确认或属于合成数据；检查价格、单槽替换实测条件与检查清单后再作购买决策。' });
    if (cfg.objective === 'pareto') diagnostics.push({ kind: 'pareto_choice', message: RANKING_RULES.pareto });
    if (cfg.objective === 'min_cost' && !Object.keys(c.min_stats).length && !Object.keys(c.max_stats).length) diagnostics.push({ kind: 'no_panel_targets', message: '未设置面板目标，只按已录入限制找最低花费；当前方案可行时通常无需购买。可在最终面板门槛填写需要达到的值。' });
    const chosenLabel = cfg.objective === 'min_cost' ? '最低花费达标方案' : '最高偏好分方案';
    if (feasible.length && cfg.objective !== 'pareto') {
      const best = feasible[0];
      if (best.price === cfg.budget) diagnostics.push({ kind: 'binding_budget', message: chosenLabel + '恰好用尽已录入预算；未录入的费用可能改变可行性。' });
      for (const id of ids) {
        if (own(c.min_stats, id) && best.final_stats[id] === c.min_stats[id]) diagnostics.push({ kind: 'binding_target', message: id + ' 恰好达到最低目标 ' + fmt(c.min_stats[id]) });
        if (own(c.max_stats, id) && best.final_stats[id] === c.max_stats[id]) diagnostics.push({ kind: 'binding_target', message: id + ' 恰好达到最高目标 ' + fmt(c.max_stats[id]) });
      }
      if (best.drawbacks.length) diagnostics.push({ kind: 'tradeoff', message: chosenLabel + '在以下已录入指标上朝非偏好方向变化: ' + best.drawbacks.join(', ') });
    }
    diagnostics.push({ kind: 'model_caution', message: '线性偏好分不是游戏伤害或战斗瓶颈诊断；多槽增量按可相加处理，组合应在相同状态下复测。' });
    diagnostics.push({ kind: 'cost_caution', message: '总花费包含报价和已录入附加费用；已拥有候选报价须为零，不自动计入旧装备出售收入。' });
    const withinBudget = primary.filter(combo => combo.price <= cfg.budget).length;
    return {
      schema_version: '1.0', model: MODELS[cfg.objective], objective: cfg.objective, objective_description: OBJECTIVE_LABELS[cfg.objective], status: feasible.length ? 'ok' : 'no_feasible_plan', title: cfg.title, notes: cfg.notes, currency: cfg.currency, budget: fmt(cfg.budget), metrics: cfg.metrics, weights: cfg.weights === null ? null : formattedMap(cfg.weights), disclaimer: DISCLAIMER.slice(),
      baseline: baselineOut, best: feasible.length && cfg.objective !== 'pareto' ? publicCombo(feasible[0]) : null, alternatives: cfg.objective === 'pareto' ? [] : feasible.slice(1, cfg.top_n).map(publicCombo), pareto: frontier.slice(0, MAX_PARETO_RETURN).map(publicCombo),
      constraints: { min_stats: formattedMap(c.min_stats), max_stats: formattedMap(c.max_stats), locked_slots: c.locked_slots.slice(), required_options: c.required_options.slice(), excluded_options: c.excluded_options.slice(), conflicts: c.conflicts.map(pair => pair.slice()), max_changes: c.max_changes },
      character: cfg.character, checklist: cfg.checklist, evidence_summary: evidenceSummary, diagnostics,
      budget_scenarios: cfg.budget_scenarios.map(s => Object.assign({ label: s.label, budget: fmt(s.budget) }, scenarioBest(s.budget, activeWeights, cfg.objective))),
      weight_scenarios: cfg.weight_scenarios.map(s => Object.assign({ label: s.label, weights: formattedMap(s.weights) }, scenarioBest(cfg.budget, s.weights, 'weighted'))),
      manual_plans: cfg.manual_plans.map(s => ({ label: s.label, plan: publicCombo(evaluated(baseCombo(s.option_ids.map(id => cfg.optionById.get(id))), cfg.budget, activeWeights)) })),
      summary: { combinations_possible: cfg.combinations, combinations_evaluated: cfg.combinations, within_budget: withinBudget, feasible_count: feasible.length, rejected_by_constraints: withinBudget - feasible.length, distinct_vectors: distinctCount, pareto_total: frontier.length, pareto_shown: Math.min(frontier.length, MAX_PARETO_RETURN), pareto_truncated: frontier.length > MAX_PARETO_RETURN, pareto_comparisons: checks },
      limits: { max_input_bytes: MAX_BYTES, max_combinations: MAX_COMBINATIONS, max_pareto_checks: MAX_PARETO_CHECKS, pareto_return_limit: MAX_PARETO_RETURN },
      ranking_rule: RANKING_RULES[cfg.objective],
      pareto_rule: '花费越低越好，各指标按用户方向比较；至少一维严格更好且其他维不差才支配。相同向量合并并标注 equivalent_count。'
    };
  }
  function exportRows(report) {
    const rows = [{ kind: 'baseline', label: report.baseline.label || '当前装备', plan: report.baseline }];
    if (report.best) rows.push({ kind: 'best', label: report.objective === 'min_cost' ? '最低花费达标方案' : '最高偏好分方案', plan: report.best });
    (report.alternatives || []).forEach((plan, i) => rows.push({ kind: 'alternative', label: '备选 ' + (i + 1), plan }));
    (report.pareto || []).forEach((plan, i) => rows.push({ kind: 'pareto', label: 'Pareto ' + (i + 1), plan }));
    (report.manual_plans || []).forEach(s => rows.push({ kind: 'manual', label: s.label, plan: s.plan }));
    (report.budget_scenarios || []).forEach(s => {
      if (s.objective === 'pareto' && s.feasible_count) (s.pareto || []).forEach((plan, i) => rows.push({ kind: 'budget_scenario', label: s.label + '；Pareto 取舍 ' + (i + 1), plan, budget: s.budget }));
      else rows.push({ kind: 'budget_scenario', label: s.label, plan: s.best, budget: s.budget });
    });
    (report.weight_scenarios || []).forEach(s => rows.push({ kind: 'weight_scenario', label: s.label, plan: s.best, weights: s.weights }));
    return rows;
  }
  function reportText(report) {
    const lines = [report.title, '预算: ' + report.budget + ' ' + report.currency, '状态: ' + (report.status === 'no_feasible_plan' ? '无可行方案' : '已计算'), '比较目标: ' + (report.objective_description || OBJECTIVE_LABELS.weighted), report.ranking_rule || '', ''];
    if (report.notes) lines.push('用户备注（不自动作为约束）: ' + report.notes);
    lines.push(report.weights ? '高级权重' + (report.objective && report.objective !== 'weighted' ? '（主目标不使用）' : '') + ': ' + Object.entries(report.weights).map(([key, value]) => key + '=' + value).join(', ') : '主目标未设置权重；主方案不计算偏好分');
    if (report.character && Object.keys(report.character).length) lines.push('角色备注: ' + JSON.stringify(report.character));
    if (report.constraints) lines.push('用户自设限制: ' + JSON.stringify(report.constraints));
    if (report.baseline.equipment && Object.keys(report.baseline.equipment).length) lines.push('当前装备: ' + Object.entries(report.baseline.equipment).map(([slot, name]) => slot + ': ' + name).join('；'));
    lines.push('基线证据: ' + (report.baseline.evidence || (report.evidence_summary || {}).baseline_evidence || 'unverified'), '');
    for (const row of exportRows(report)) {
      lines.push('[' + row.kind + '] ' + row.label);
      if (row.budget !== undefined) lines.push('情景预算: ' + row.budget);
      if (row.weights) lines.push('情景权重: ' + Object.entries(row.weights).map(([id, value]) => id + '=' + value).join(', '));
      const p = row.plan; if (!p) { lines.push('无可行方案', ''); continue; }
      lines.push('可行: ' + (p.feasible ? '是' : '否') + '；花费: ' + p.price + '；剩余预算: ' + p.remaining_budget + (p.score === null ? '；未使用权重评分' : '；偏好分: ' + p.score));
      lines.push('选择: ' + (p.selection.length ? p.selection.map(o => o.slot + ': ' + o.name + ' (' + o.id + ', 报价 ' + o.quoted_price + ', 费用 ' + o.fees + ', 证据 ' + o.evidence + (o.replaces ? ', 替换 ' + o.replaces : '') + (o.source ? ', 来源 ' + o.source : '') + (o.notes ? ', 备注（未自动建模） ' + o.notes : '') + ')').join('；') : '保持当前装备'));
      for (const m of report.metrics) lines.push(m.name + ': ' + p.final_stats[m.id] + ' ' + m.unit + '；增量 ' + p.deltas[m.id] + '；方向 ' + m.direction);
      if (p.violations && p.violations.length) lines.push('未满足: ' + p.violations.join('；'));
      if (p.drawbacks && p.drawbacks.length) lines.push('退步指标: ' + p.drawbacks.join(', '));
      lines.push('');
    }
    lines.push('诊断:'); for (const d of report.diagnostics || []) lines.push('- ' + d.message);
    lines.push('证据说明: ' + ((report.evidence_summary || {}).notice || '用户声明，未经独立验证'));
    if ((report.checklist || []).length) { lines.push('检查清单:'); for (const item of report.checklist) lines.push('- ' + item.item + ': ' + item.status + (item.note ? '；' + item.note : '')); }
    for (const scenario of report.budget_scenarios || []) if (scenario.objective === 'pareto') lines.push('预算情景 ' + scenario.label + '：Pareto 展示 ' + scenario.pareto_shown + ' / ' + scenario.pareto_total + ' 个等价向量' + (scenario.pareto_truncated ? '（已截断）' : ''));
    lines.push('枚举摘要: ' + JSON.stringify(report.summary), '限制与说明:');
    for (const text of report.disclaimer || []) lines.push('- ' + text);
    return lines.join('\n') + '\n';
  }
  function csvCell(value, textual) {
    let text = value == null ? '' : String(value);
    if ((textual || !/^-?\d+(?:\.\d+)?$/.test(text)) && /^(?:[=+\-@\t\r\n]|\s+[=+\-@])/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function reportCSV(report) {
    const header = ['kind', 'label', 'feasible', 'budget', 'weights', 'price', 'remaining_budget', 'score', 'selection', 'evidence', 'violations', 'drawbacks'];
    for (const m of report.metrics) header.push('final_' + m.id, 'delta_' + m.id);
    header.push('objective');
    const lines = [header.map(v => csvCell(v, true)).join(',')];
    for (const row of exportRows(report)) {
      const p = row.plan;
      const values = [row.kind, row.label, p ? String(p.feasible) : 'false', row.budget || report.budget, JSON.stringify(row.weights || report.weights), p ? p.price : '', p ? p.remaining_budget : '', p ? p.score : '', p ? p.selection.map(o => o.slot + ':' + o.name + ' [' + o.id + ']；报价=' + o.quoted_price + '；费用=' + o.fees + (o.source ? '；来源=' + o.source : '') + (o.notes ? '；备注（未自动建模）=' + o.notes : '')).join(' | ') : '', p ? p.selection.map(o => o.id + ':' + o.evidence).join(' | ') : '', p ? (p.violations || []).join(' | ') : '无可行方案', p ? (p.drawbacks || []).join(' | ') : ''];
      for (const m of report.metrics) values.push(p ? p.final_stats[m.id] : '', p ? p.deltas[m.id] : '');
      values.push(row.kind === 'weight_scenario' ? 'weighted' : report.objective || 'weighted');
      lines.push(values.map((v, i) => csvCell(v, ![3, 5, 6, 7].includes(i) && i < 12)).join(','));
    }
    if (report.notes) lines.push(['user_notes_not_modeled', report.notes].map(v => csvCell(v, true)).join(','));
    lines.push(['notice', (report.disclaimer || []).join('；') + '；' + ((report.evidence_summary || {}).notice || '')].map(v => csvCell(v, true)).join(','));
    return '\ufeff' + lines.join('\r\n') + '\r\n';
  }
  function reportHTML(report) {
    const escape = value => String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    return '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; connect-src \'none\'; form-action \'none\'; base-uri \'none\'"><title>' + escape(report.title) + '</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#182a36;background:#fff}h1{font-size:1.5rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;border-top:1px solid #ccd6dc;padding-top:1rem}@media print{body{margin:0;max-width:none}}</style></head><body><h1>' + escape(report.title) + '</h1><pre>' + escape(reportText(report)) + '</pre></body></html>\n';
  }
  return Object.freeze({ parse, stringify, numeric, isNumeric, calculate, validate, diagnose, reportText, reportCSV, reportHTML, InputError, MAX_BYTES, MAX_DEPTH });
});
