/* Exact offline gem-upgrade and mixed-training plans. Original vanilla JS port
 * of scripts/plans.py and routes.py:gem_feasibility. Monetary products use
 * twelve-place BigInt decimals; thresholds and XP use reduced BigInt fractions.
 * No network, storage, installation, market estimates or game-client actions.
 * Load engine.js, resources.js and decisions.js before this browser script.
 */
(function (root, factory) {
  'use strict';
  const common = typeof module === 'object' && module.exports;
  const api = factory(common ? require('./engine.js') : root.MHXYEngine,
    common ? require('./resources.js') : root.MHXYResources,
    common ? require('./decisions.js') : root.MHXYDecisions);
  if (common) module.exports = api;
  if (root) root.MHXYPlans = api;
})(typeof globalThis === 'object' ? globalThis : this, function (E, R, D) {
  'use strict';
  if (!E || !R || !D) throw new Error('Planning requires engine.js, resources.js and decisions.js');
  const MAX_ROWS = 200;
  // Products can have twelve fractional places. All calculations remain exact.
  const SCALE = 1000000000000n;
  const MAX_VALUE = 1000000000000n * SCALE;
  const has = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const DECIMAL = /^-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$/;
  // Python str.strip() whitespace, including U+0085 and excluding the BOM.
  const BLANK = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u;
  class InputError extends Error {
    constructor(message, path) { super(message); this.name = 'InputError'; this.path = path || 'input'; }
  }
  function fail(message, path) { throw new InputError(message, path); }
  function nativeConstructor(proto, name) {
    const descriptor = proto && Object.getOwnPropertyDescriptor(proto, 'constructor');
    return !!descriptor && has(descriptor, 'value') && typeof descriptor.value === 'function' && Function.prototype.toString.call(descriptor.value) === 'function ' + name + '() { [native code] }';
  }
  function object(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value) || E.isNumeric(value)) return false;
    const proto = Object.getPrototypeOf(value);
    return proto === null || (Object.getPrototypeOf(proto) === null && nativeConstructor(proto, 'Object')); // Also allow another realm's plain objects.
  }
  function fields(value, required, optional) {
    if (!object(value)) fail('Expected an object');
    const keys = Reflect.ownKeys(value);
    if (keys.some(key => typeof key !== 'string' || !Object.getOwnPropertyDescriptor(value, key).enumerable || !has(Object.getOwnPropertyDescriptor(value, key), 'value'))) {
      fail('Expected a plain JSON object with enumerable data fields');
    }
    const absent = required.filter(key => !has(value, key)).sort();
    const extra = keys.filter(key => !required.includes(key) && !(optional || []).includes(key)).sort();
    if (absent.length || extra.length) fail('Missing fields: ' + absent.join(', ') + '; unknown fields: ' + extra.join(', '));
  }
  function text(value, label, limit) {
    limit = limit === undefined ? 1000 : limit;
    if (typeof value !== 'string' || BLANK.test(value) || /[\u0000-\u001f]/.test(value) || Array.from(value).length > limit) {
      fail(label + ' must be nonempty text without controls', label);
    }
    return value;
  }
  function decimal(value, negativeZero) { return { value: value, negativeZero: value === 0n && !!negativeZero }; }
  function fromText(value) {
    const negative = value[0] === '-';
    const parts = (negative ? value.slice(1) : value).split('.');
    const raw = BigInt(parts[0]) * SCALE + BigInt((parts[1] || '').padEnd(12, '0'));
    return decimal(negative ? -raw : raw, negative && raw === 0n);
  }
  function num(value, label) {
    if (E.isNumeric(value)) value = decimalTokenText(value);
    if (typeof value !== 'string' && !(typeof value === 'number' && Number.isSafeInteger(value))) {
      fail(label + ' must be an integer or decimal string', label);
    }
    const s = String(value), match = DECIMAL.exec(s);
    if (!match || match[0] !== s) fail(label + ' requires a plain decimal with up to 6 decimal places', label);
    const n = fromText(s);
    if (n.value < 0n || n.value > MAX_VALUE) fail(label + ' is outside supported range', label);
    return n;
  }
  function fmt(n) {
    if (n === null) return null;
    const negative = n.value < 0n || n.negativeZero;
    const absolute = n.value < 0n ? -n.value : n.value;
    const fraction = (absolute % SCALE).toString().padStart(12, '0').replace(/0+$/, '');
    return (negative ? '-' : '') + (absolute / SCALE).toString() + (fraction ? '.' + fraction : '');
  }
  function add(a, b) { return decimal(a.value + b.value, a.negativeZero && b.negativeZero); }
  function subtract(a, b) { return decimal(a.value - b.value, a.negativeZero && b.value === 0n && !b.negativeZero); }
  function multiply(a, b) {
    const negative = (a.value < 0n || a.negativeZero) !== (b.value < 0n || b.negativeZero);
    return decimal(a.value * b.value / SCALE, negative);
  }
  function rows(value, label) {
    if (!Array.isArray(value) || value.length > MAX_ROWS) fail(label + ' must be a bounded list', label);
    const proto = Object.getPrototypeOf(value);
    if (!Array.isArray(proto) || !nativeConstructor(proto, 'Array')) fail(label + ' must be a plain JSON list', label);
    // Reject sparse arrays, accessors and extra properties, which cannot come
    // from JSON and would otherwise silently omit or execute a cost line.
    const keys = Reflect.ownKeys(value);
    if (keys.length !== value.length + 1 || keys.some(key => key !== 'length' && (typeof key !== 'string' || !/^(?:0|[1-9][0-9]*)$/.test(key) || Number(key) >= value.length || !has(Object.getOwnPropertyDescriptor(value, key), 'value')))) {
      fail(label + ' must be a dense JSON list', label);
    }
    const copy = [];
    for (let index = 0; index < value.length; index++) copy.push(Object.getOwnPropertyDescriptor(value, String(index)).value);
    return copy;
  }
  function day(value, label) {
    text(value, label, 10);
    const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(value);
    if (!match || match[0] !== value) fail(label + ' must be YYYY-MM-DD', label);
    const year = Number(match[1]), month = Number(match[2]), date = Number(match[3]);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const lengths = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (year < 1 || month < 1 || month > 12 || date < 1 || date > lengths[month - 1]) fail(label + ' must be YYYY-MM-DD', label);
    const previous = year - 1;
    return previous * 365 + Math.floor(previous / 4) - Math.floor(previous / 100) + Math.floor(previous / 400) + lengths.slice(0, month - 1).reduce((a, b) => a + b, 0) + date;
  }
  function context(data) {
    fields(data, ['server', 'currency', 'as_of'], ['max_age_days', 'ruleset']);
    const server = text(data.server, 'server', 100), currency = text(data.currency, 'currency', 40);
    const asof = day(data.as_of, 'as_of');
    const age = has(data, 'max_age_days') ? jsonInteger(data.max_age_days) : 7;
    if (!Number.isSafeInteger(age) || age < 0 || age > 365) fail('max_age_days must be an integer between 0 and 365', 'max_age_days');
    if (has(data, 'ruleset')) text(data.ruleset, 'ruleset', 100);
    return { server, currency, asof, age };
  }
  function quote(value, ctx, label) {
    fields(value, ['amount', 'currency', 'server', 'observed_on', 'source', 'kind'], ['notes']);
    const amount = num(value.amount, label + '.amount');
    text(value.source, label + '.source');
    for (const key of ['currency', 'server']) {
      if (value[key] !== ctx[key]) fail(label + ': mixed ' + key + ' requires a separate scenario, not implicit conversion', label + '.' + key);
    }
    if (!['asking', 'sold', 'user_quote', 'estimate'].includes(value.kind)) fail(label + '.kind must be asking/sold/user_quote/estimate', label + '.kind');
    const observed = day(value.observed_on, label + '.observed_on');
    if (observed > ctx.asof) fail(label + ': quote date is after as_of', label + '.observed_on');
    if (has(value, 'notes')) text(value.notes, label + '.notes');
    const age = ctx.asof - observed;
    return { amount, stale: age > ctx.age, age_days: age, kind: value.kind, source: value.source, currency: value.currency, server: value.server, observed_on: value.observed_on };
  }
  function quoteOutput(value) {
    return value === null ? null : { amount: fmt(value.amount), stale: value.stale, age_days: value.age_days, kind: value.kind, source: value.source, currency: value.currency, server: value.server, observed_on: value.observed_on };
  }
  function moneyLine(value, ctx, label) {
    fields(value, ['label', 'quantity', 'quote']);
    text(value.label, label + '.label');
    const qty = num(value.quantity, label + '.quantity');
    if (value.quote === null) return { label: value.label, quantity: fmt(qty), subtotal: null, status: 'unknown_quote' };
    const q = quote(value.quote, ctx, label + '.quote');
    return { label: value.label, quantity: fmt(qty), subtotal: fmt(multiply(q.amount, qty)), status: q.stale ? 'stale_quote' : 'manual_quote', kind: q.kind, source: q.source, age_days: q.age_days, unit_quote: quoteOutput(q) };
  }
  function lineTotal(lines) {
    if (lines.some(line => line.subtotal === null)) return null;
    return lines.reduce((sum, line) => add(sum, fromText(line.subtotal)), decimal(0n));
  }
  // The shared JSON parser preserves every numeric lexeme. Python's reader
  // distinguishes JSON integers from Decimal tokens, including 1 versus 1.0.
  function jsonInteger(value) {
    if (!E.isNumeric(value)) return value;
    const s = value.lexeme;
    if (!/^-?(?:0|[1-9][0-9]*)$/.test(s)) return value;
    const n = Number(s);
    return Number.isSafeInteger(n) ? n : value;
  }
  function decimalTokenText(token) {
    const raw = token.lexeme;
    if (/^-?(?:0|[1-9][0-9]*)$/.test(raw)) return raw === '-0' ? '0' : raw;
    const match = /^(-?)([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$/.exec(raw);
    const sign = match[1], fraction = match[3] || '';
    const exponent = BigInt(match[4] || 0) - BigInt(fraction.length);
    const digits = (match[2] + fraction).replace(/^0+(?=.)/, '');
    const adjusted = BigInt(digits.length - 1) + exponent;
    // Decimal uses scientific notation outside these bounds; num rejects it.
    if (exponent > 0n || adjusted < -6n) return '1E+999';
    const places = Number(-exponent);
    if (!places) return sign + digits;
    return sign + (digits.length > places ? digits.slice(0, -places) + '.' + digits.slice(-places) : '0.' + '0'.repeat(places - digits.length) + digits);
  }
  function safeJSON(value, depth, stack) {
    depth = depth || 0; stack = stack || new Set();
    if (value === null || typeof value === 'string' || typeof value === 'boolean' || E.isNumeric(value)) return;
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) fail('JSON does not support non-finite numbers');
      return;
    }
    if (typeof value !== 'object') fail('Expected a plain JSON value');
    if (depth >= E.MAX_DEPTH || stack.has(value)) fail('JSON exceeds supported nesting or contains a cycle');
    stack.add(value);
    if (Array.isArray(value)) {
      // Generic JSON arrays are not money-line arrays and have no 200-row cap.
      const keys = Reflect.ownKeys(value), proto = Object.getPrototypeOf(value);
      if (!Array.isArray(proto) || !nativeConstructor(proto, 'Array') || keys.length !== value.length + 1 ||
          keys.some(k => k !== 'length' && (typeof k !== 'string' || !/^(?:0|[1-9][0-9]*)$/.test(k) || Number(k) >= value.length || !has(Object.getOwnPropertyDescriptor(value, k), 'value')))) fail('Expected a dense plain JSON list');
      for (let i = 0; i < value.length; i++) safeJSON(Object.getOwnPropertyDescriptor(value, String(i)).value, depth + 1, stack);
    } else {
      if (!object(value)) fail('Expected an object');
      const keys = Reflect.ownKeys(value);
      for (const key of keys) {
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        if (typeof key !== 'string' || !descriptor.enumerable || !has(descriptor, 'value')) fail('Expected a plain JSON object with enumerable data fields');
        safeJSON(descriptor.value, depth + 1, stack);
      }
    }
    stack.delete(value);
  }
  function input(raw) {
    const data = typeof raw === 'string' ? E.parse(raw) : raw;
    safeJSON(data); return data;
  }
  const STRIP = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu;
  function integer(value, label, low, high) {
    low = low === undefined ? 0n : BigInt(low);
    high = high === undefined ? null : high === null ? null : BigInt(high);
    value = jsonInteger(value);
    if (!(typeof value === 'string' || (typeof value === 'number' && Number.isSafeInteger(value)))) fail(label + '必须是非负整数或整数字符串');
    const s = String(value).replace(STRIP, '');
    if (!/^[0-9]{1,30}$/.test(s)) fail(label + '必须是至多30位的非负整数');
    const result = BigInt(s);
    if (result < low || (high !== null && result > high)) fail(label + '超出允许范围');
    return result;
  }
  function resourceFields(data, required, optional) {
    if (!object(data)) fail('输入必须是对象');
    const extra = Object.keys(data).filter(k => !required.includes(k) && !(optional || []).includes(k)).sort();
    if (extra.length) fail('未知输入字段：' + extra.map(k => "'" + k + "'").join(', '));
    const missing = required.filter(k => !has(data, k));
    if (missing.length) fail('缺少必填字段：' + missing.join(', '));
  }
  function enumValue(value, values, label) {
    if (typeof value !== 'string' || !values.includes(value)) fail(label + '无效');
    return value;
  }
  function pcContext(value) {
    const ctx = context(value);
    if (!['pc_time', '电脑版时间服', '梦幻西游电脑版时间服'].includes(has(value, 'ruleset') ? value.ruleset : 'pc_time')) fail('Only MHXY PC time-server rules are supported; do not apply to mobile/free/classic variants');
    return ctx;
  }
  function gcd(a, b) { a = a < 0n ? -a : a; while (b) { const next = a % b; a = b; b = next; } return a; }
  function rational(n, denominator) {
    const divisor = gcd(n, denominator);
    return { n: n / divisor, d: denominator / divisor };
  }
  function rationalText(value) { return value.n.toString() + (value.d === 1n ? '' : '/' + value.d); }
  function fraction(value, label, positive) {
    let result;
    if (typeof value === 'string' && value.includes('/')) {
      const parts = value.split('/');
      if (parts.length !== 2) fail(label + '必须是整数或分数字符串');
      result = rational(integer(parts[0], label), integer(parts[1], label + '分母', 1));
    } else result = rational(integer(value, label), 1n);
    if (positive && result.n <= 0n) fail(label + '必须大于0');
    return result;
  }
  function ceil(n, denominator) { return (n + denominator - 1n) / denominator; }
  function priceCeiling(numerator, quantity) {
    quantity = quantity === undefined ? decimal(SCALE) : quantity;
    if (numerator === null || quantity.value <= 0n) return null;
    const exact = rational(numerator.value, quantity.value);
    let scaled = exact.n * 1000000n / exact.d;
    if (exact.n < 0n && exact.n * 1000000n % exact.d) scaled--;
    const ceiling = decimal(scaled * 1000000n > MAX_VALUE ? MAX_VALUE : scaled * 1000000n);
    return { exact_limit: rationalText(exact), max_nonnegative_quote_at_6dp: exact.n < 0n ? null : fmt(ceiling),
      nonnegative_quote_possible: exact.n >= 0n,
      meaning: '该临界线在其他已填价格/费用/目标条件不变时成立；可填单价按六位小数向下取整，并限制在接口单价上限1万亿，避免超预算' };
  }
  function compareInput(value, key) {
    if (E.isNumeric(value)) {
      if (key === 'max_age_days') return jsonInteger(value);
      // Preserve typed non-monetary fields. Converting every numeric token to
      // text would accidentally accept a numeric source, label, or notes value.
      return ['amount', 'quantity', 'sunk_cost'].includes(key) ? decimalTokenText(value) : value;
    }
    if (Array.isArray(value)) return value.map(v => compareInput(v));
    if (value !== null && typeof value === 'object') {
      const copy = Object.create(null);
      for (const k of Object.keys(value)) copy[k] = compareInput(value[k], k);
      return copy;
    }
    return value;
  }
  function gemFeasibility(raw) {
    const data = input(raw);
    resourceFields(data, ['gemType', 'slot', 'equipmentLevel', 'currentForge', 'targetForge', 'existingGemTypes', 'effects'], ['providedGrades', 'characterLevel']);
    const gem = R.gemTypes.find(g => g.id === data.gemType);
    if (!gem) fail('仅支持八种普通属性宝石');
    const slot = enumValue(data.slot, ['武器', '头盔', '铠甲', '腰带', '鞋子', '项链'], '装备部位');
    const equipment = integer(data.equipmentLevel, '装备原始要求等级', 0, 160);
    if (equipment % 10n) fail('仅支持原始要求等级为10倍数的装备，简易不改变此输入');
    const current = integer(data.currentForge, '当前锻炼', 0, 20), target = integer(data.targetForge, '目标锻炼', current, 20);
    const existing = data.existingGemTypes, effects = data.effects;
    if (!Array.isArray(existing) || existing.some(g => typeof g !== 'string' || !R.gemTypes.some(item => item.id === g)) || new Set(existing).size !== existing.length || existing.length > 2) fail('已有宝石类型须为不重复的0至2种支持类型');
    if ((current === 0n && existing.length) || (current > 0n && !existing.length) || BigInt(existing.length) > current) fail('已有锻炼等级与已有宝石类型矛盾');
    if (existing.some(g => !R.gemTypes.find(item => item.id === g).slots.includes(slot))) fail('已有宝石与装备部位不符');
    if (!Array.isArray(effects) || effects.some(x => !['精致', '无级别限制', '简易'].includes(x)) || new Set(effects).size !== effects.length) fail('effects仅接受不重复的精致/无级别限制/简易列表，普通装备填[]');
    const cap = effects.includes('无级别限制') ? null : equipment / 10n + (effects.includes('精致') ? 1n : 0n);
    const role = has(data, 'characterLevel') ? integer(data.characterLevel, '人物等级', 0, 175) : null;
    let wearingMin = effects.includes('无级别限制') ? 0n : equipment - (effects.includes('简易') ? 5n : 0n);
    if (wearingMin < 0n) wearingMin = 0n;
    const reasons = [];
    if (role !== null && role < wearingMin) reasons.push('人物等级不满足所填装备穿戴门槛；核对等级/简易/无级别，不能只凭已镶宝石推定可穿');
    if (target > current && !gem.slots.includes(slot)) reasons.push('所选宝石不适用于该部位');
    if (target > current && new Set(existing.concat(gem.id)).size > 2) reasons.push('会超过同件装备最多两种宝石的限制');
    if (cap !== null && current > cap) fail('已有锻炼超过所填装备/特效允许上限，请核对装备信息');
    if (cap !== null && target > cap) reasons.push('目标超过该装备锻炼上限');
    const grades = []; for (let g = current + 1n; g <= target; g++) grades.push(String(g));
    if (has(data, 'providedGrades')) {
      if (!Array.isArray(data.providedGrades)) fail('providedGrades必须是有序列表');
      const supplied = data.providedGrades.map(g => String(integer(g, '提供的宝石等级', 1, 20)));
      if (supplied.length !== grades.length || supplied.some((g, i) => g !== grades[i])) reasons.push('须按顺序提供每个新增等级宝石各一颗，不可跳级或只用最高级一颗');
    }
    const checkedDate = '2026-10-06';
    return { calculator: 'ordinary_gem_feasibility', scope: '梦幻西游电脑版时间服', checkedDate,
      ruleVersion: 'pc-time-routes-2026-10-06', ruleIds: ['ordinary_gem_insertion', 'refined_gem_cap', 'wearing_level_effects'],
      citations: [
        { id: 'equipment_effects', title: '官方装备特效', url: 'https://xyq.163.com/introduce/jn002.html', checkedDate },
        { id: 'gems', title: '官方宝石', url: 'https://xyq.163.com/introduce/dj008.html', checkedDate },
        { id: 'toolbox', title: '官方综合工具箱', url: 'https://xyq.163.com/tools/index.html', checkedDate }
      ], status: reasons.length ? 'ineligible' : 'eligible', reasons, equipmentLevel: String(equipment), slot,
      characterLevel: role === null ? null : String(role), minimumCharacterLevel: String(wearingMin), characterLevelEligible: role === null ? null : role >= wearingMin,
      wearingScope: '只查已给人物等级；未核武器造型/性别等资格，未给人物等级时不能把镶嵌可行当角色可穿', forgeCap: cap === null ? null : String(cap),
      capMeaning: cap === null ? '无级别不受装备等级÷10限制；本工具只核验至20锻' : '原装备等级÷10，精致加1，简易不另减原装备等级', requiredGrades: grades, allowedSlots: Array.from(gem.slots),
      rawStatDelta: reasons.length ? null : { key: gem.stat, value: String((target - current) * BigInt(gem.perStep)), unit: '原始装备属性' } };
  }
  function comparisonViews(comparison) {
    // Each conclusion depends only on its own prices. Stale resale or stock
    // opportunity values must not invalidate an otherwise known cash outlay.
    const own = comparison.self_upgrade, replacement = comparison.replacement;
    const cashLines = own.lines.concat(replacement.purchase_fee_lines);
    const buy = replacement.purchase_quote, sale = replacement.resale_quote;
    const netLines = cashLines.concat(replacement.resale_fee_lines);
    const economicLines = netLines.concat(own.owned_materials);
    const qualified = comparison.eligibility_confirmed && comparison.target_equivalence.status === 'confirmed';
    function view(left, right, lines, quoteValues, resaleDependent = false) {
      const quotes = quoteValues.filter(q => q !== null);
      const stale = lines.some(line => line.status === 'stale_quote') || quotes.some(q => q.stale);
      const missing = left === null || right === null;
      const conditional = lines.some(line => ['sold', 'estimate'].includes(line.kind)) || quotes.some(q => ['sold', 'estimate'].includes(q.kind));
      const status = !qualified ? 'eligibility_unconfirmed' : missing ? 'missing' : stale ? 'stale'
        : conditional || (resaleDependent && replacement.resale_status !== 'settled') ? 'conditional' : 'ready';
      let ordering = 'unknown';
      if (qualified && !missing && !stale) {
        const a = fromText(left).value, b = fromText(right).value;
        ordering = a === b ? 'tie' : a < b ? 'self_upgrade' : 'replacement';
      }
      return { self_upgrade_cost: left, replacement_cost: right, status, ordering,
        has_stale_quotes: stale, missing_values: missing, eligibility_confirmed: qualified,
        has_historical_or_estimated_quotes: conditional };
    }
    return { upfront_cash: view(own.cash_outlay, replacement.upfront_cash_required, cashLines, [buy]),
      net_cash: view(own.cash_outlay, replacement.net_cost_if_resale_occurs, netLines, [buy, sale], true),
      economic_cost: view(own.economic_cost, replacement.net_cost_if_resale_occurs, economicLines, [buy, sale], true) };
  }
  function viewSummary(view, objective) {
    const label = objective === 'upfront_cash' ? '立即新增现金' : '卖旧后条件经济成本';
    if (view.ordering === 'unknown') {
      const reason = { eligibility_unconfirmed: '资格或同目标未确认', missing: '缺少相关金额', stale: '相关报价过期' }[view.status] || '条件不足';
      return label + '尚不能排序：' + reason;
    }
    const prefix = '自升' + view.self_upgrade_cost + '两，成品' + view.replacement_cost + '两';
    let order = { self_upgrade: '自升较低', replacement: '成品较低', tie: '两条路线相同' }[view.ordering];
    if (view.ordering !== 'tie') {
      const difference = subtract(fromText(view.self_upgrade_cost), fromText(view.replacement_cost));
      order += '（少' + fmt(decimal(difference.value < 0n ? -difference.value : difference.value)) + '两）';
    }
    const condition = objective === 'economic_cost' ? '（仅在录入卖旧净回款实现时）' : '';
    return label + '：' + prefix + '；' + order + condition;
  }
  function gemUpgrade(raw) {
    const data = input(raw);
    fields(data, ['context', 'equipment', 'grade_quotes', 'owned_stones', 'fees'], ['budget', 'replacement', 'sunk_cost', 'decision_objective']);
    const objective = has(data, 'decision_objective') ? data.decision_objective : 'unspecified';
    if (has(data, 'decision_objective') && (typeof objective !== 'string' || !['upfront_cash', 'economic_cost'].includes(objective))) fail('decision_objective must be upfront_cash/economic_cost when provided');
    const ctx = pcContext(data.context);
    if (ctx.currency !== '两') fail('Gem plans use 两; no implicit currency conversion');
    const check = gemFeasibility(data.equipment), budget = data.budget == null ? null : num(data.budget, 'budget');
    if (!object(data.grade_quotes) || !object(data.owned_stones)) fail('grade_quotes and owned_stones must be grade-keyed objects');
    const quotes = Object.create(null), stock = Object.create(null);
    for (const [key, value] of Object.entries(data.grade_quotes)) {
      const g = integer(key, 'grade', 1, 20);
      if (String(g) !== key) fail('Grades must use canonical integer keys');
      if (value !== null) quote(value, ctx, 'grade ' + key);
      quotes[key] = value;
    }
    for (const [key, value] of Object.entries(data.owned_stones)) {
      const g = integer(key, 'owned grade', 1, 20);
      if (String(g) !== key) fail('Grades must use canonical integer keys');
      fields(value, ['quantity', 'opportunity_quote']);
      const count = integer(value.quantity, 'owned quantity', 0, 100000);
      if (value.opportunity_quote !== null) quote(value.opportunity_quote, ctx, 'owned opportunity quote');
      stock[key] = { count, quote: value.opportunity_quote };
    }
    const fees = rows(data.fees, 'fees');
    for (const row of fees) moneyLine(row, ctx, 'fee');
    // Historical/estimated remaining fees cannot certify that actual fees are zero.
    // An unused replacement's fees do not participate in this completion guard.
    const conditionalFees = fees.filter(row => row.quote !== null && ['sold', 'estimate'].includes(row.quote.kind)).map(row => row.label);
    const purchases = [], owned = [], bill = [];
    for (const grade of check.requiredGrades) {
      const useStock = has(stock, grade) && stock[grade].count > 0n;
      const q = useStock ? stock[grade].quote : has(quotes, grade) ? quotes[grade] : null;
      const row = { label: grade + '级宝石', quantity: '1', quote: q };
      (useStock ? owned : purchases).push(row);
      bill.push({ grade, required: '1', from_stock: useStock ? '1' : '0', to_buy: useStock ? '0' : '1', quote: q,
        cost_meaning: useStock ? '库存可变现机会成本' : '新增采购现金' });
    }
    const simple = R.gems({ gemType: data.equipment.gemType, currentForge: String(integer(data.equipment.currentForge, '当前锻炼', 0, 20)), targetForge: String(integer(data.equipment.targetForge, '目标锻炼', 0, 20)) });
    const amounts = purchases.concat(fees).map(row => moneyLine(row, ctx, 'purchase'));
    const totalCash = lineTotal(amounts);
    let opportunity = lineTotal(owned.map(row => moneyLine(row, ctx, 'owned stone')));
    let economic = totalCash === null || opportunity === null ? null : add(totalCash, opportunity);
    const stale = purchases.concat(fees).filter(row => row.quote !== null && quote(row.quote, ctx, row.label).stale).map(row => row.label);
    const ownedStale = owned.filter(row => row.quote !== null && quote(row.quote, ctx, row.label).stale).map(row => row.label);
    if (ownedStale.length) { opportunity = null; economic = null; }
    let comparison = null, timing = null;
    const alternative = data.replacement == null ? null : data.replacement;
    if (alternative !== null) {
      fields(alternative, ['purchase', 'fees', 'old_item_resale', 'eligibility', 'equivalence'], ['resale_timing']);
      fields(alternative.equivalence, ['status', 'basis']);
      if (!['confirmed', 'unknown', 'different_target'].includes(alternative.equivalence.status)) fail('equivalence status must be confirmed/unknown/different_target');
      text(alternative.equivalence.basis, 'equivalence basis');
      const compare = { context: data.context,
        self_upgrade: { purchases, owned_materials: owned, fees, eligible: check.status === 'eligible' ? 'confirmed' : 'ineligible' },
        replacement: { purchase: alternative.purchase, fees: alternative.fees, old_item_resale: alternative.old_item_resale, eligible: alternative.eligibility } };
      if (has(data, 'sunk_cost')) compare.sunk_cost = data.sunk_cost;
      try { comparison = D.compareUpgrade(compareInput(compare)); }
      catch (error) { throw new InputError(error.message, error.path); }
      if (has(data, 'sunk_cost')) comparison.sunk_cost_excluded = data.sunk_cost;
      comparison.target_equivalence = alternative.equivalence;
      comparison.decision_views = comparisonViews(comparison);
      if (alternative.resale_timing != null) {
        const original = alternative.resale_timing;
        fields(original, ['not_before', 'keep_until_replacement', 'basis']);
        text(original.basis, 'resale timing basis');
        if (typeof original.keep_until_replacement !== 'boolean') fail('keep_until_replacement must be boolean');
        const when = original.not_before === null ? null : day(original.not_before, 'resale not_before');
        if (comparison.replacement.resale_status === 'settled' && when !== null && when > ctx.asof) fail('Settled sale contradicts future/keep-until-replacement sale restriction');
        timing = Object.assign({}, original, { unlocked_as_of: when === null ? null : when <= ctx.asof });
        comparison.resale_timing = timing;
      }
    }
    const blockers = Array.from(check.reasons);
    const missing = purchases.concat(fees).filter(row => row.quote === null).map(row => row.label);
    if (missing.length) blockers.push('缺少新增采购报价：' + missing.join('、'));
    if (stale.length) blockers.push('现金采购报价超过设定有效期：' + stale.join('、'));
    if (ownedStale.length) blockers.push('库存机会价值报价过期，只影响经济成本比较，不影响已知采购现金：' + ownedStale.join('、'));
    const selfOK = check.status === 'eligible' && totalCash !== null && !stale.length;
    const selfAfford = budget === null || totalCash === null ? null : totalCash.value <= budget.value;
    let recommendation = '条件不足，保留原装备；先补会改变决定的项目';
    if (check.status === 'ineligible') recommendation = '不要按这条路线采购，目标锻数或宝石资格不成立';
    else if (selfOK) {
      recommendation = budget === null ? '可按逐级采购清单核价；资源规则已通过，预算尚未提供' : '可按逐级采购清单自升；这只说明资源和预算可行';
      if (selfAfford === false) recommendation = '当前预算不足；先降低目标或等待预算，不把旧装挂牌价当现钱';
    }
    let replacementAfford = null;
    if (comparison !== null) {
      const gross = comparison.replacement.upfront_cash_required;
      replacementAfford = gross === null || budget === null ? null : fromText(gross).value <= budget.value;
      const views = comparison.decision_views;
      if (alternative.equivalence.status !== 'confirmed') blockers.push('成品尚未确认达到同一目标，不能只按价格二选一');
      else if (!comparison.eligibility_confirmed) blockers.push('成品或自升资格尚未确认');
      else {
        const cashSummary = viewSummary(views.upfront_cash, 'upfront_cash');
        const economicSummary = viewSummary(views.economic_cost, 'economic_cost');
        if (objective === 'upfront_cash') recommendation = '按最低立即新增现金比较：' + cashSummary;
        else if (objective === 'economic_cost') recommendation = '按经济成本比较：' + economicSummary;
        else recommendation = '未指定成本优先级；' + cashSummary + '；' + economicSummary;
        if (views.upfront_cash.ordering === 'unknown') blockers.push(cashSummary);
        if (views.economic_cost.ordering === 'unknown') blockers.push(economicSummary + '；不阻断不依赖这些资料的立即现金结论');
        if (replacementAfford === false) recommendation += '；但当前现金不足以先买成品，应等旧装成交或放弃该方案';
        if (selfAfford === false) recommendation += '；自升本次现金预算仍不够，先缩小目标';
      }
    }
    const conditionalQuotes = purchases.concat(fees).filter(row => row.quote !== null && ['sold', 'estimate'].includes(row.quote.kind)).map(row => row.label);
    if (comparison !== null) {
      if (comparison.replacement.purchase_quote !== null && ['sold', 'estimate'].includes(comparison.replacement.purchase_quote.kind)) conditionalQuotes.push('成品');
      for (const row of comparison.replacement.purchase_fee_lines) if (['sold', 'estimate'].includes(row.kind)) conditionalQuotes.push('成品购入费用：' + row.label);
      // Future resale fees do not determine upfront procurement cash. Their
      // conditions remain in decision_views and the original attributed lines.
    }
    if (conditionalQuotes.length) {
      blockers.push('含历史成交/估算报价，不能据此认定当前可成交：' + conditionalQuotes.join('、'));
      recommendation = '只作条件成本比较：含历史或估算价格，采购前先核实当前可买报价；' + recommendation.replace('可按逐级采购清单自升；这只说明资源和预算可行', '录入金额在预算内，不证明现在可成交');
    }
    if (selfAfford === false) blockers.push('自升新增现金超过本次预算');
    if (replacementAfford === false) blockers.push('成品先买现金超过本次预算，未成交卖价不能抵扣');
    if (selfAfford === false && replacementAfford === false) recommendation += '；两条路线当前都缺现金，先等成交回款或降低目标';
    if (timing !== null && timing.unlocked_as_of === false) {
      blockers.push('旧物在' + timing.not_before + '之前不能卖；未来回款仍是条件，不能抵本次先买现金');
      if (!timing.keep_until_replacement) {
        recommendation = recommendation.replace('应等旧装成交或放弃该方案', '只能在' + timing.not_before + '解限并实际成交后重新比较，或放弃该方案');
        recommendation = recommendation.replace('先等成交回款或降低目标', '只能在' + timing.not_before + '解限并实际成交后重算，或降低目标');
      }
    }
    if (timing !== null && timing.keep_until_replacement) {
      blockers.push('必须先取得替换物再卖旧物；不能先卖旧来弥补购入现金缺口');
      recommendation = recommendation.replace('应等旧装成交或放弃该方案', '需压价或增加自有现金，不能先卖旧筹款');
      recommendation = recommendation.replace('先等成交回款或降低目标', '需压价、降低目标或增加自有现金，不能先卖旧筹款');
      if (replacementAfford === false) {
        recommendation += '；先换后卖限制生效，不能靠这笔未来卖旧款启动替换';
        if (selfAfford === true && selfOK && !conditionalQuotes.length) recommendation += '；按本次已录入条件，自升现金够，当前可保留自升路线';
      }
    }
    let goalStatus = 'remaining_work';
    let nextAction = '仅核对本轮目标所依赖的缺项或变动报价；按已列采购清单执行前确认，不自动采购';
    if (comparison !== null) {
      const selectedView = comparison.decision_views[objective];
      if (selectedView !== undefined && selectedView.ordering !== 'unknown') {
        nextAction = selectedView.status === 'ready'
          ? '本轮成本比较已可给出；仅在相关报价、费用、资格或目标变化时重算，不自动采购'
          : '本轮可作条件金额比较；采购前核实所选路线的当前可买报价，不自动采购';
        if (objective === 'economic_cost' && comparison.decision_views.upfront_cash.status === 'ready') {
          nextAction = '采用已列经济成本条件；实际成交或到账后更新，不将条件回款当作先买现金，不自动采购';
        }
      } else if (objective === 'unspecified') nextAction = '按已列现金与经济口径选择；只补所选口径依赖的缺项，不自动采购';
    }
    if (!bill.length) {
      if (check.status !== 'eligible') nextAction = '先解决已列资格或目标冲突；没有新增锻数，不应继续逐级询价';
      else if (alternative !== null && alternative.equivalence.status !== 'confirmed') {
        goalStatus = 'forge_met_target_unresolved';
        recommendation = '本件已达目标锻数；成品同目标尚未确认，不能据此认定整个替换目标已完成';
        nextAction = '核对已列同目标差异；本件无新增宝石需求，费用仍按下列记录保留';
      } else if (totalCash !== null && totalCash.value === 0n && !stale.length && !conditionalFees.length) {
        goalStatus = 'completed';
        recommendation = '目标已达成，新增现金0两；无需为本目标询价或采购';
        nextAction = '保留已确认现状；本目标无需新增动作，其他未完成目标仍独立核算';
      } else {
        goalStatus = 'forge_met_fees_remaining';
        recommendation = '本件已达目标锻数；仍有已录入费用' + (totalCash === null ? '待核实' : fmt(totalCash) + '两') + '，不能把剩余费用当作0';
        if (conditionalFees.length) recommendation = '本件已达目标锻数；剩余费用仅有历史/估算记录，条件金额'
          + (totalCash === null ? '未知' : fmt(totalCash) + '两') + '，仍需核实，不能确认费用为0';
        if (stale.length) recommendation += '；费用报价过期，仅保留条件金额';
        if (selfAfford === false) recommendation += '；当前预算不足';
        nextAction = '仅处理已列剩余费用或其缺项；无新增宝石需求，不必逐级询价';
      }
    }
    const unknown = purchases.concat(fees).filter((row, i) => amounts[i].subtotal === null);
    let oneUnknown = null;
    if (unknown.length === 1) {
      const row = unknown[0], qty = num(row.quantity, 'unknown quote quantity');
      const known = lineTotal(amounts.filter(c => c.subtotal !== null));
      const gross = comparison === null || comparison.replacement.upfront_cash_required === null ? null : fromText(comparison.replacement.upfront_cash_required);
      const net = comparison === null || comparison.replacement.net_cost_if_resale_occurs === null ? null : fromText(comparison.replacement.net_cost_if_resale_occurs);
      oneUnknown = { label: row.label, quantity: fmt(qty), known_other_cash: fmt(known), currency: ctx.currency,
        within_budget: priceCeiling(budget === null ? null : subtract(budget, known), qty),
        same_upfront_cash_as_replacement: priceCeiling(gross === null ? null : subtract(gross, known), qty),
        same_net_cash_if_resale_occurs: priceCeiling(net === null ? null : subtract(net, known), qty),
        same_economic_cost_if_resale_occurs: priceCeiling(net === null || opportunity === null ? null : subtract(subtract(net, known), opportunity), qty),
        limits: '只是一个未知单价的条件临界线；不填补现价，不解除资格/报价/卖旧时间限制' };
    }
    let replacementLimit = null;
    if (comparison !== null && budget !== null) {
      const f = lineTotal(comparison.replacement.purchase_fee_lines);
      replacementLimit = priceCeiling(f === null ? null : subtract(budget, f));
    }
    return { calculator: 'gem_upgrade_plan', scope: '梦幻西游电脑版时间服，单件普通宝石逐级升级与同目标成品比较',
      recommendation, decision_objective: objective, goal_status: goalStatus, eligibility: check, bill,
      self_upgrade: { cash_outlay: fmt(totalCash), owned_material_opportunity_cost: fmt(opportunity), economic_cost: fmt(economic), cash_within_budget: selfAfford,
        cash_remaining: budget !== null && totalCash !== null ? fmt(subtract(budget, totalCash)) : null },
      budget: fmt(budget), currency: '两', replacement_upfront_within_budget: replacementAfford,
      comparison, resale_timing: timing, replacement_purchase_affordability_ceiling: replacementLimit, single_unknown_quote_thresholds: oneUnknown,
      blockers: Array.from(new Set(blockers)), resource_check: simple,
      next_action: nextAction,
      limits: ['一段各需一颗对应级别，库存只抵同级同类宝石，不擅自拆合或折现',
        '材料下限不当作预计合成成本；此采购清单使用对应等级成品石报价',
        '最终面板、套装差异、修理失败与实战效果另核；不会自动认为两件物品等效',
        '费用空列表表示用户明确确认无额外费用；不确定时填一行quote=null以保持未知'] };
  }
  function ordinaryCultivation(data) {
    resourceFields(data, ['type', 'currentLevel', 'targetLevel', 'currentProgressXp', 'confirmedCap']);
    if (typeof data.type !== 'string' || !['attack', 'spell', 'defense', 'anti_spell', 'hunting'].includes(data.type)) fail('修炼类型无效');
    const limit = data.type === 'hunting' ? 20 : 25;
    const current = integer(data.currentLevel, '当前修炼等级', 0, limit), target = integer(data.targetLevel, '目标修炼等级', 0, limit), cap = integer(data.confirmedCap, '已确认修炼上限', 0, limit);
    const progress = integer(data.currentProgressXp, '本级已有修炼经验');
    try { return R.cultivation({ type: data.type, currentLevel: String(current), targetLevel: String(target), confirmedCap: String(cap), currentProgressXp: String(progress) }); }
    catch (error) { throw new InputError(error.message); }
  }
  function trainingMix(raw) {
    const data = input(raw);
    const itemFields = ['item_xp', 'item_xp_evidence', 'item_quote', 'mixing_eligibility'];
    fields(data, ['cultivation'], itemFields.concat('max_items', 'context'));
    // No market/account context is needed for the fixed-rule ordinary branch.
    const ctx = has(data, 'context') ? pcContext(data.context) : null;
    if (ctx !== null && ctx.currency !== '两') fail('Training uses 两');
    const normal = ordinaryCultivation(data.cultivation);
    if (!['attack', 'spell', 'defense', 'anti_spell'].includes(data.cultivation.type)) fail('Mixed item routes support only the four human cultivation types');
    // resources.cultivation validates range/progress; routes._range additionally
    // disallows progress at a user-confirmed cap below the absolute level limit.
    if (normal.currentLevel === normal.confirmedCap && normal.currentProgressXp !== '0') fail('已到确认上限时本级进度必须为0；本工具不假定封顶经验保留');
    const needed = BigInt(normal.requiredXp);
    const explicitMaximum = has(data, 'max_items') ? integer(data.max_items, 'max_items', 0, 100000) : null;
    // These two statuses explicitly select the ordinary/no-op route. The four
    // unused item fields may be absent/null; supplied JSON values are ignored.
    // Every explicit max_items is validated, even when there is no XP needed.
    if (needed === 0n || explicitMaximum === 0n) return {
      calculator: 'training_mix', status: needed === 0n ? 'no_upgrade_needed' : 'ordinary_only',
      recommendation: needed === 0n ? '目标已达到，无需采购或点修' : '本次道具可用上限为0，只有普通路线；无需道具报价', ordinary: normal,
      best_mix: { items: '0', ordinary_purchases: normal.purchases, cost_liang: normal.costLiang, ordinary_materials: normal.materialsConsumed, surplus_xp: normal.surplusXp, saving_vs_all_ordinary: '0' },
      limits: ['普通路线仍须满足角色、帮派和开放资格；无需升级时不产生新增花费']
    };
    fields(data, ['context', 'cultivation'].concat(itemFields), ['max_items']);
    const xp = fraction(data.item_xp, 'item_xp', true);
    text(data.item_xp_evidence, 'item XP evidence');
    const eligibility = data.mixing_eligibility;
    if (!['confirmed', 'unknown', 'ineligible'].includes(eligibility)) fail('Invalid mixing eligibility');
    const q = data.item_quote === null ? null : quote(data.item_quote, ctx, 'item quote');
    let maximum = ceil(needed * xp.d, xp.n);
    const providedMaximum = explicitMaximum === null ? maximum : explicitMaximum;
    // Python validates the computed default too, before taking the minimum.
    if (!has(data, 'max_items') && maximum > 9007199254740991n) fail('max_items必须是非负整数或整数字符串');
    if (!has(data, 'max_items') && maximum > 100000n) fail('max_items超出允许范围');
    if (providedMaximum < maximum) maximum = providedMaximum;
    const perClick = ['defense', 'anti_spell'].includes(data.cultivation.type) ? 20000n : 30000n;
    if (q === null) return { calculator: 'training_mix', status: 'missing_quote', ordinary: normal, recommendation: '先用普通路线确定预算上限；缺道具报价时不能确定混合最省方案', missing: ['item_quote'] };
    let best = null, tied = 0n;
    for (let count = 0n; count <= maximum; count++) {
      let remaining = needed * xp.d - count * xp.n;
      if (remaining < 0n) remaining = 0n;
      const clicks = ceil(remaining, 10n * xp.d);
      const cost = add(multiply(decimal(count * SCALE), q.amount), decimal(clicks * perClick * SCALE));
      const surplus = count * xp.n + (clicks * 10n - needed) * xp.d;
      const candidate = { cost, surplus, count, clicks };
      if (best === null || cost.value < best.cost.value) { best = candidate; tied = 1n; }
      else if (cost.value === best.cost.value) {
        tied++;
        if (surplus < best.surplus || (surplus === best.surplus && (count < best.count || (count === best.count && clicks < best.clicks)))) best = candidate;
      }
    }
    const qualified = eligibility === 'confirmed' && !q.stale;
    return { calculator: 'training_mix', status: qualified ? 'conditional_calculated' : 'eligibility_or_quote_unresolved',
      recommendation: qualified ? '在道具经验、报价、可混用与可用次数均成立时，下列组合现金最少' : '这是条件算术，先确认道具/普通修炼资格或更新报价', ordinary: normal,
      best_mix: { items: String(best.count), ordinary_purchases: String(best.clicks), cost_liang: fmt(best.cost), ordinary_materials: String(best.clicks * 5n),
        surplus_xp: rationalText(rational(best.surplus, xp.d)), saving_vs_all_ordinary: fmt(subtract(fromText(normal.costLiang), best.cost)) },
      item_quote: quoteOutput(q), item_xp: rationalText(xp), item_xp_evidence: data.item_xp_evidence,
      mixing_eligibility: eligibility, max_items: String(maximum), price_tied_counts: String(tied),
      method: '枚举0至所需全道具颗数/用户可用上限，每种用普通10XP购次补足，精确十进制比较',
      limits: ['每颗XP与混用资格由用户确认，不从品质推断；普通购次资格仍须满足',
        '先把普通修炼做在前，再用道具覆盖剩余需求，仅在两者均可使用时成立',
        '不包含时间成本、帮派等候、道具每日限量或封顶余量可保留性；max_items可录入用户确认的当期上限',
        '所有价格为手工数据；最小成本不保证当前可以买到足够数量'] };
  }
  return Object.freeze({ gemUpgrade, trainingMix, gemFeasibility, parseJSON: E.parse, stringifyJSON: E.stringify, InputError });
});
