/* Original offline upgrade decision arithmetic. No dependencies, network or storage.
 * Mirrors scripts/decisions.py:compare_upgrade. Monetary input is decimal text
 * (at most six decimal places) or a safe integer Number, never a decimal Number.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.MHXYDecisions = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
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
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
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
    const age = has(data, 'max_age_days') ? data.max_age_days : 7;
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
  function ordering(a, b) {
    return a === null || b === null ? 'unknown' : (a.value === b.value ? 'tie' : a.value < b.value ? 'self_upgrade' : 'replacement');
  }
  function compareUpgrade(data) {
    fields(data, ['context', 'self_upgrade', 'replacement'], ['sunk_cost']);
    const ctx = context(data.context), own = data.self_upgrade, replacement = data.replacement;
    fields(own, ['purchases', 'fees', 'owned_materials'], ['eligible']);
    fields(replacement, ['purchase', 'fees', 'old_item_resale'], ['eligible']);
    for (const route of [own, replacement]) {
      if (has(route, 'eligible') && !['confirmed', 'unknown', 'ineligible'].includes(route.eligible)) fail('eligible must be confirmed/unknown/ineligible', 'eligible');
    }
    const purchaseLines = rows(own.purchases, 'self purchases').map(value => moneyLine(value, ctx, 'self purchase'));
    const feeLines = rows(own.fees, 'self fees').map(value => moneyLine(value, ctx, 'self fee'));
    const materialLines = rows(own.owned_materials, 'owned materials').map(value => moneyLine(value, ctx, 'owned opportunity cost'));
    const selfCash = lineTotal(purchaseLines.concat(feeLines)), opportunity = lineTotal(materialLines);
    const selfEconomic = selfCash === null || opportunity === null ? null : add(selfCash, opportunity);
    const buy = replacement.purchase === null ? null : quote(replacement.purchase, ctx, 'replacement purchase');
    const buyFees = rows(replacement.fees, 'replacement fees').map(value => moneyLine(value, ctx, 'replacement fee'));
    const fees = lineTotal(buyFees), gross = buy === null || fees === null ? null : add(buy.amount, fees);
    const sale = replacement.old_item_resale;
    let resale = null, resaleStatus = 'unknown', saleFees = [], saleQ = null;
    if (sale !== null) {
      fields(sale, ['quote', 'fees', 'status']);
      if (!['settled', 'conditional'].includes(sale.status)) fail('resale.status must be settled or conditional', 'resale.status');
      saleQ = quote(sale.quote, ctx, 'resale');
      saleFees = rows(sale.fees, 'resale fees').map(value => moneyLine(value, ctx, 'resale fee'));
      const sf = lineTotal(saleFees);
      if (sf !== null) resale = subtract(saleQ.amount, sf);
      resaleStatus = sale.status;
      if (resaleStatus === 'settled' && saleQ.kind !== 'sold') fail('settled resale requires kind=sold; asking prices are not proceeds', 'resale.status');
    }
    const net = gross === null || resale === null ? null : subtract(gross, resale);
    const conditions = [], allLines = purchaseLines.concat(feeLines, materialLines, buyFees, saleFees);
    if (allLines.some(line => line.status === 'stale_quote')) conditions.push('Some manual quotes are older than the chosen freshness window');
    if (buy !== null && buy.stale) conditions.push('Replacement purchase quote is stale');
    if (saleQ !== null && saleQ.stale) conditions.push('Resale quote is stale');
    if (resaleStatus !== 'settled') conditions.push('Resale is conditional or unknown; do not subtract it from cash needed before sale');
    const eligibility = { self_upgrade: has(own, 'eligible') ? own.eligible : 'unknown', replacement: has(replacement, 'eligible') ? replacement.eligible : 'unknown' };
    conditions.push('Compare only routes delivering equivalent user targets; the calculator does not infer combat equivalence');
    if (has(data, 'sunk_cost') && data.sunk_cost !== null) num(data.sunk_cost, 'sunk_cost');
    const thresholdCash = selfCash === null || fees === null || resale === null ? null : subtract(add(selfCash, resale), fees);
    const thresholdEconomic = selfEconomic === null || fees === null || resale === null ? null : subtract(add(selfEconomic, resale), fees);
    return {
      calculator: 'upgrade_compare', currency: ctx.currency, server: ctx.server,
      self_upgrade: { cash_outlay: fmt(selfCash), owned_material_opportunity_cost: fmt(opportunity), economic_cost: fmt(selfEconomic), lines: purchaseLines.concat(feeLines), owned_materials: materialLines },
      replacement: { upfront_cash_required: fmt(gross), purchase_quote: quoteOutput(buy), purchase_fee_lines: buyFees, net_resale_proceeds: fmt(resale), resale_quote: quoteOutput(saleQ), resale_fee_lines: saleFees, resale_status: resaleStatus, net_cost_if_resale_occurs: fmt(net) },
      cash_cost_comparison_if_resale_occurs: ordering(selfCash, net),
      economic_cost_comparison_if_resale_occurs: ordering(selfEconomic, net),
      comparable_routes_eligibility: eligibility,
      eligibility_confirmed: Object.values(eligibility).every(value => value === 'confirmed'),
      comparison_has_stale_quotes: conditions.some(message => message.includes('stale') || message.includes('older')),
      replacement_purchase_break_even_cash: fmt(thresholdCash), replacement_purchase_break_even_economic: fmt(thresholdEconomic),
      break_even_formula: 'replacement purchase <= self cost + net old-item resale - replacement fees',
      sunk_cost_excluded: has(data, 'sunk_cost') ? data.sunk_cost : null,
      conditions,
      unknowns: allLines.filter(line => line.subtotal === null).map(line => line.label).concat(buy === null ? ['replacement purchase'] : [], resale === null ? ['net old-item resale'] : []),
      provenance: 'manual_user_observations_not_independently_verified'
    };
  }
  const KIND = { asking: '挂牌价（不等于成交）', sold: '用户录入成交价', user_quote: '用户手工报价', estimate: '估计值' };
  const ELIGIBILITY = { confirmed: '用户已确认', unknown: '待确认', ineligible: '不符合使用条件' };
  const ORDERING = { self_upgrade: '自行升级较低', replacement: '直接换成品较低', tie: '相同', unknown: '未知，信息不足' };
  const CONDITIONS = {
    'Some manual quotes are older than the chosen freshness window': '部分明细报价超过所选时效窗口，需重新核价',
    'Replacement purchase quote is stale': '成品购买报价已过期，需重新核价',
    'Resale quote is stale': '旧件出售报价已过期，需重新核价',
    'Resale is conditional or unknown; do not subtract it from cash needed before sale': '旧件出售有条件或未知；成交前不能从所需现金中扣除预计回款',
    'Compare only routes delivering equivalent user targets; the calculator does not infer combat equivalence': '只比较能实现相同目标的路线；本工具不推断实战等价、伤害或真实最优方案'
  };
  function sameJSON(a, b) {
    if (a === b) return true;
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return false;
    const ak = Object.keys(a), bk = Object.keys(b);
    return ak.length === bk.length && bk.every(key => has(a, key) && sameJSON(a[key], b[key]));
  }
  function reportText(result, data) {
    // Recompute from the supplied input; never export an unrelated old result.
    const r = compareUpgrade(data);
    if (!sameJSON(result, r)) fail('Report result does not match supplied input', 'result');
    const money = value => value === null ? '未知' : value + ' ' + r.currency;
    const lines = ['自行升级 / 直接换成品：离线决策摘要',
      '区服：' + r.server + '；统一货币：' + r.currency,
      '比较基准日：' + data.context.as_of + '；报价时效窗口：' + (has(data.context, 'max_age_days') ? data.context.max_age_days : 7) + ' 天'];
    if (has(data.context, 'ruleset')) lines.push('规则集：' + data.context.ruleset);
    lines.push('来源声明：全部价格为用户手工录入，未联网核价、未独立验证；挂牌价不等于成交价。', '',
      '自行升级新增现金：' + money(r.self_upgrade.cash_outlay),
      '消耗库存的机会成本：' + money(r.self_upgrade.owned_material_opportunity_cost),
      '自行升级经济成本：' + money(r.self_upgrade.economic_cost),
      '换成品成交前所需现金（购买 + 费用）：' + money(r.replacement.upfront_cash_required),
      '旧件净出售收入（扣除出售费）：' + money(r.replacement.net_resale_proceeds),
      '旧件出售状态：' + ({ settled: '用户声明已成交', conditional: '有条件，尚不能视为回款', unknown: '未知' }[r.replacement.resale_status]),
      '若旧件出售实现，换成品净成本：' + money(r.replacement.net_cost_if_resale_occurs),
      '已发生投入（沉没成本，不重复计入）：' + (r.sunk_cost_excluded === null ? '未记录' : String(r.sunk_cost_excluded) + ' ' + r.currency), '',
      '使用资格：自行升级 ' + ELIGIBILITY[r.comparable_routes_eligibility.self_upgrade] + '；换成品 ' + ELIGIBILITY[r.comparable_routes_eligibility.replacement],
      '以下仅为条件成立时的算术对比，不构成购买建议：',
      '旧件出售实现后的现金成本：' + ORDERING[r.cash_cost_comparison_if_resale_occurs],
      '旧件出售实现后的经济成本：' + ORDERING[r.economic_cost_comparison_if_resale_occurs],
      '成品购买价现金口径临界值：' + money(r.replacement_purchase_break_even_cash),
      '成品购买价经济口径临界值：' + money(r.replacement_purchase_break_even_economic),
      '临界公式：成品购买价 ≤ 自行升级成本 + 旧件净出售收入 − 成品购买费用',
      '临界值为负时，没有满足该阈值的非负购买价；未知值不能按 0 处理。', '', '报价与明细（全部为用户记录）：');
    function quoteLine(label, q) {
      if (q === null) { lines.push('- ' + label + '：未知报价'); return; }
      lines.push('- ' + label + '：' + money(q.amount) + '；' + KIND[q.kind] + '；来源：' + q.source + '；记录日：' + q.observed_on + '；距基准日 ' + q.age_days + ' 天' + (q.stale ? '（已超时效）' : '') + '；区服：' + q.server);
    }
    function group(label, entries) {
      if (!entries.length) lines.push('- ' + label + '：无录入项');
      for (const entry of entries) {
        quoteLine(label + ' / ' + entry.label, entry.unit_quote || null);
        lines.push('  数量：' + entry.quantity + '；小计：' + money(entry.subtotal));
      }
    }
    group('自行升级购买及费用', r.self_upgrade.lines);
    group('库存机会成本', r.self_upgrade.owned_materials);
    quoteLine('成品购买', r.replacement.purchase_quote);
    group('成品购买费用', r.replacement.purchase_fee_lines);
    quoteLine('旧件出售', r.replacement.resale_quote);
    group('旧件出售费用', r.replacement.resale_fee_lines);
    lines.push('', '风险与待确认事项：');
    if (!r.eligibility_confirmed) lines.push('- 两条路线的使用资格尚未全部确认，不应据此直接选购');
    for (const condition of r.conditions) lines.push('- ' + CONDITIONS[condition]);
    // User labels may literally equal an internal identifier: preserve their
    // text, and translate only the separately determined system unknowns.
    const unknownLabels = r.self_upgrade.lines.concat(r.self_upgrade.owned_materials, r.replacement.purchase_fee_lines, r.replacement.resale_fee_lines).filter(entry => entry.subtotal === null).map(entry => entry.label);
    if (r.replacement.purchase_quote === null) unknownLabels.push('成品购买价');
    if (r.replacement.net_resale_proceeds === null) unknownLabels.push('旧件净出售收入');
    if (unknownLabels.length) lines.push('- 尚未知：' + unknownLabels.join('、'));
    lines.push('- 未列出的费用、损耗、交易限制和游戏机制不在计算范围内；请按实际情况补充');
    return lines.join('\n') + '\n';
  }
  return Object.freeze({ compareUpgrade, reportText, InputError, limits: Object.freeze({ maxRows: MAX_ROWS, maxAmount: '1000000000000', decimalPlaces: 6 }) });
});
