/* Exact offline whole-project budget planning, mirroring scripts/portfolio.py.
 * No network, storage, paid dependencies or implicit market/mechanics assumptions.
 * Load engine.js, decisions.js, then this file. Decimal strings preserve precision.
 */
(function (root, factory) {
  'use strict';
  const common = typeof module === 'object' && module.exports;
  const api = factory(common ? require('./engine.js') : root.MHXYEngine,
    common ? require('./decisions.js') : root.MHXYDecisions);
  if (common) module.exports = api;
  if (root) root.MHXYPortfolio = api;
})(typeof globalThis === 'object' ? globalThis : this, function (E, D) {
  'use strict';
  if (!E || !D) throw new Error('Load engine.js and decisions.js before portfolio.js');
  const MAX_OPTIONS = 16, SCALE = 1000000000000n, MAX_VALUE = 1000000000000n * SCALE;
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const DECIMAL = /^-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$/;
  const BLANK = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u;
  const InputError = D.InputError;
  function fail(message, path) { throw new InputError(message, path); }
  function nativeConstructor(proto, name) {
    const d = proto && Object.getOwnPropertyDescriptor(proto, 'constructor');
    return !!d && own(d, 'value') && typeof d.value === 'function' && Function.prototype.toString.call(d.value) === 'function ' + name + '() { [native code] }';
  }
  function object(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value) || E.isNumeric(value)) return false;
    const proto = Object.getPrototypeOf(value);
    return proto === null || (Object.getPrototypeOf(proto) === null && nativeConstructor(proto, 'Object'));
  }
  function keys(value) {
    const ks = Reflect.ownKeys(value);
    if (ks.some(key => typeof key !== 'string' || !Object.getOwnPropertyDescriptor(value, key).enumerable || !own(Object.getOwnPropertyDescriptor(value, key), 'value'))) {
      fail('Expected a plain JSON object with enumerable data fields');
    }
    return ks;
  }
  // Python sorts Unicode strings by code point, not UTF-16 code unit or locale.
  function compareText(a, b) {
    const aa = Array.from(a), bb = Array.from(b);
    for (let i = 0; i < Math.min(aa.length, bb.length); i++) {
      const x = aa[i].codePointAt(0), y = bb[i].codePointAt(0);
      if (x !== y) return x < y ? -1 : 1;
    }
    return aa.length - bb.length;
  }
  const sorted = value => Array.from(value).sort(compareText);
  const record = entries => Object.fromEntries(entries);
  function fields(value, required, optional) {
    if (!object(value)) fail('Expected an object');
    const ks = keys(value), absent = sorted(required.filter(key => !own(value, key)));
    const extra = sorted(ks.filter(key => !required.includes(key) && !(optional || []).includes(key)));
    if (absent.length || extra.length) fail('Missing fields: ' + absent.join(', ') + '; unknown fields: ' + extra.join(', '));
  }
  function text(value, label, limit) {
    if (typeof value !== 'string' || BLANK.test(value) || /[\u0000-\u001f]/.test(value) || Array.from(value).length > (limit === undefined ? 1000 : limit)) {
      fail(label + ' must be nonempty text without controls', label);
    }
    return value;
  }
  function rows(value, label, unbounded) {
    if (!Array.isArray(value) || (!unbounded && value.length > 200)) fail(label + ' must be a bounded list', label);
    const proto = Object.getPrototypeOf(value);
    if (!Array.isArray(proto) || !nativeConstructor(proto, 'Array')) fail(label + ' must be a plain JSON list', label);
    const ks = Reflect.ownKeys(value);
    if (ks.length !== value.length + 1 || ks.some(key => key !== 'length' && (typeof key !== 'string' || !/^(?:0|[1-9][0-9]*)$/.test(key) || Number(key) >= value.length || !own(Object.getOwnPropertyDescriptor(value, key), 'value')))) {
      fail(label + ' must be a dense JSON list', label);
    }
    return Array.from({ length: value.length }, (_, i) => Object.getOwnPropertyDescriptor(value, String(i)).value);
  }
  function identifiers(value, label) {
    const list = rows(value, label);
    if (list.length > 100 || list.some(x => typeof x !== 'string' || BLANK.test(x)) || new Set(list).size !== list.length) fail(label + ' must contain unique nonempty identifiers', label);
    return list;
  }
  const decimal = (value, negativeZero) => ({ value, negativeZero: value === 0n && !!negativeZero });
  const zero = () => decimal(0n);
  function fromText(value) {
    const negative = value[0] === '-', parts = (negative ? value.slice(1) : value).split('.');
    const n = BigInt(parts[0]) * SCALE + BigInt((parts[1] || '').padEnd(12, '0'));
    return decimal(negative ? -n : n, negative);
  }
  function num(value, label) {
    value = numericScalar(value);
    if (typeof value !== 'string' && !(typeof value === 'number' && Number.isSafeInteger(value))) fail(label + ' must be an integer or decimal string', label);
    const s = String(value), match = DECIMAL.exec(s);
    if (!match || match[0] !== s) fail(label + ' requires a plain decimal with up to 6 decimal places', label);
    const n = fromText(s);
    if (n.value < 0n || n.value > MAX_VALUE) fail(label + ' is outside supported range', label);
    return n;
  }
  function fmt(n) {
    if (n === null) return null;
    const abs = n.value < 0n ? -n.value : n.value;
    const fraction = (abs % SCALE).toString().padStart(12, '0').replace(/0+$/, '');
    return (n.value < 0n || n.negativeZero ? '-' : '') + (abs / SCALE).toString() + (fraction ? '.' + fraction : '');
  }
  const add = (a, b) => decimal(a.value + b.value, a.negativeZero && b.negativeZero);
  const subtract = (a, b) => decimal(a.value - b.value, a.negativeZero && b.value === 0n && !b.negativeZero);
  const shortfall = (a, b) => a.value > b.value ? subtract(a, b) : zero();
  const sum = values => values.reduce(add, zero());
  const formattedMap = map => record(Array.from(map, ([k, v]) => [k, fmt(v)]));
  function validatedMapping(value, error, keyLabel, keyLimit, valueLabel, limit) {
    if (!object(value)) fail(error);
    const ks = keys(value);
    if (limit !== undefined && ks.length > limit) fail(error);
    return new Map(ks.map(key => [text(key, keyLabel, keyLimit), num(value[key], valueLabel)]));
  }
  function decisionInput(ctx, purchases, owned) {
    return { context: ctx, self_upgrade: { purchases, fees: [], owned_materials: owned }, replacement: { purchase: null, fees: [], old_item_resale: null } };
  }
  function moneyLines(value, ctx, owned) {
    const list = rows(value, owned ? 'owned materials' : 'costs').map(row => {
      if (!object(row)) return row;
      const copy = record(keys(row).map(key => [key, key === 'quantity' ? numericScalar(row[key]) : row[key]]));
      if (own(copy, 'quote') && object(copy.quote)) copy.quote = record(keys(copy.quote).map(key => [key, key === 'amount' ? numericScalar(copy.quote[key]) : copy.quote[key]]));
      return copy;
    });
    try {
      const result = D.compareUpgrade(decisionInput(ctx, owned ? [] : list, owned ? list : [])).self_upgrade;
      return { lines: owned ? result.owned_materials : result.lines,
        total: (owned ? result.owned_material_opportunity_cost : result.cash_outlay) === null ? null : fromText(owned ? result.owned_material_opportunity_cost : result.cash_outlay) };
    } catch (error) {
      if (error instanceof D.InputError && !owned) fail(error.message.replace(/^self purchase(?=[.: ]|$)/, 'cost'), error.path.replace(/^self purchase(?=[.: ]|$)/, 'cost'));
      throw error;
    }
  }
  // Numeric tokens are normalized only in numeric fields. A numeric title or
  // identifier must never become valid text as a side effect of JSON parsing.
  function numericScalar(value) {
    if (!E.isNumeric(value)) return value;
    const s = value.lexeme;
    if (/^-?(?:0|[1-9][0-9]*)$/.test(s)) return s;
    const match = /^(-?)([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$/.exec(s);
    const fraction = match[3] || '', exponent = Number(match[4] || 0) - fraction.length;
    const digits = (match[2] + fraction).replace(/^0+(?=.)/, '');
    const adjusted = exponent + digits.length - 1;
    // Outside this range Python Decimal prints scientific notation or fails
    // decisions.num's precision/range check. Never expand arbitrary exponents.
    if (!Number.isSafeInteger(exponent) || exponent > 0 || adjusted < -6 || exponent < -6 || digits.length > 19) return s;
    if (exponent === 0) return match[1] + digits;
    const point = digits.length + exponent;
    return match[1] + (point > 0 ? digits.slice(0, point) + '.' + digits.slice(point) : '0.' + '0'.repeat(-point) + digits);
  }
  // The engine parser preserves lexemes and rejects duplicate keys. Direct JS
  // decimal Numbers are rejected because their original precision is unknowable.
  function inputData(raw) {
    if (typeof raw === 'string') raw = E.parse(raw);
    const active = new Set();
    function materialize(value, depth) {
      if (E.isNumeric(value)) {
        const s = value.lexeme, n = Number(s);
        return /^-?(?:0|[1-9][0-9]*)$/.test(s) && Number.isSafeInteger(n) ? (n === 0 ? 0 : n) : value;
      }
      if (value === null || typeof value !== 'object') return value;
      if (depth >= E.MAX_DEPTH) fail('JSON 嵌套不能超过 32 层', 'input');
      if (active.has(value)) fail('JSON 不允许循环引用', 'input');
      active.add(value);
      let out;
      if (Array.isArray(value)) out = rows(value, 'input', true).map(v => materialize(v, depth + 1));
      else if (object(value)) out = record(keys(value).map(key => [key, materialize(value[key], depth + 1)]));
      else fail('Expected an object');
      active.delete(value);
      return out;
    }
    return materialize(raw, 0);
  }
  function calculate(raw) {
    const data = inputData(raw);
    fields(data, ['title', 'context', 'budget', 'goals', 'already_met', 'options', 'available_resources'], ['reserve', 'evidence_notes', 'system_budgets', 'completed_options']);
    text(data.title, 'title'); D.compareUpgrade(decisionInput(data.context, [], []));
    const ctx = data.context;
    if (!['pc_time', '电脑版时间服', '梦幻西游电脑版时间服'].includes(own(ctx, 'ruleset') ? ctx.ruleset : 'pc_time')) fail('Only PC time-server planning is supported');
    const budget = num(data.budget, 'budget'), reserve = num(own(data, 'reserve') ? data.reserve : 0, 'reserve');
    if (reserve.value > budget.value) fail('reserve cannot exceed available budget');
    const available = subtract(budget, reserve);
    const caps = validatedMapping(own(data, 'system_budgets') ? data.system_budgets : {}, 'system_budgets must map at most100 systems to amounts in the same currency', 'system budget name', 100, 'system budget', 100);
    const goals = new Map();
    for (const goal of rows(data.goals, 'goals')) {
      fields(goal, ['id', 'target', 'basis']);
      const key = text(goal.id, 'goal id', 80);
      if (goals.has(key)) fail('Duplicate goal id');
      text(goal.target, 'goal target'); text(goal.basis, 'user goal basis'); goals.set(key, goal);
    }
    if (!goals.size) fail('At least one explicit target is required; do not optimize empty goals');
    const met = new Set(identifiers(data.already_met, 'already_met'));
    if (Array.from(met).some(key => !goals.has(key))) fail('Unknown already-met goal');
    const completed = new Set(identifiers(own(data, 'completed_options') ? data.completed_options : [], 'completed_options'));
    const stock = validatedMapping(data.available_resources, 'available_resources must be a mapping of at most 100 resources', 'resource id', 80, 'available resource', 100);
    const options = new Map(), review = [], quoteConditions = [];
    const optionRows = rows(data.options, 'options');
    if (optionRows.length > MAX_OPTIONS) fail('At most 16 whole-project alternatives; split a larger decision into explicit stages');
    for (const option of optionRows) {
      fields(option, ['id', 'label', 'system', 'goals', 'costs', 'eligibility', 'effect_basis', 'requires', 'conflicts', 'consumes'], ['route_group', 'owned_materials']);
      const key = text(option.id, 'option id', 80);
      if (options.has(key)) fail('Duplicate option id');
      for (const field of ['label', 'system', 'effect_basis']) text(option[field], field);
      const gs = new Set(identifiers(option.goals, 'option goals'));
      if (Array.from(gs).some(g => !goals.has(g))) fail('Option covers unknown goal');
      if (!['confirmed', 'unknown', 'ineligible'].includes(option.eligibility)) fail('Invalid eligibility');
      const req = new Set(identifiers(option.requires, 'requires')), con = new Set(identifiers(option.conflicts, 'conflicts'));
      if (req.has(key) || con.has(key)) fail('Self dependency/conflict is invalid');
      const consumes = validatedMapping(option.consumes, 'consumes must be a mapping', 'resource id', 80, 'resource consumption');
      if (!completed.has(key) && Array.from(consumes.keys()).some(r => !stock.has(r))) fail('Every shared resource needs explicit available stock; unknown stock is not zero');
      const group = own(option, 'route_group') ? option.route_group : null;
      if (group !== null) text(group, 'route group', 80);
      const costs = moneyLines(option.costs, ctx, false), owned = moneyLines(own(option, 'owned_materials') ? option.owned_materials : [], ctx, true);
      const conditionalKinds = sorted(new Set(costs.lines.filter(row => ['estimate', 'sold'].includes(row.kind)).map(row => row.kind)));
      if (conditionalKinds.length && !completed.has(key)) quoteConditions.push({ id: key, kinds: conditionalKinds, meaning: '估算或历史成交金额，只支持条件算术，不证明当前可买' });
      if (owned.lines.some(row => row.status === 'stale_quote')) owned.total = null;
      const reasons = [];
      if (option.eligibility !== 'confirmed') reasons.push('eligibility_' + option.eligibility);
      if (costs.total === null) reasons.push('unknown_cash_cost');
      if (costs.lines.some(row => row.status === 'stale_quote')) reasons.push('stale_quote');
      if (reasons.length && !completed.has(key)) review.push({ id: key, reasons });
      options.set(key, { id: key, label: option.label, system: option.system, goals: gs, cash: costs.total,
        opportunity: owned.total, cost_lines: costs.lines, owned_materials: owned.lines, requires: req, conflicts: con,
        consumes, group, ready: !reasons.length && !completed.has(key), effect_basis: option.effect_basis });
    }
    if (Array.from(completed).some(key => !options.has(key))) fail('Unknown completed option');
    const systems = new Set(Array.from(options.values(), o => o.system));
    const unusedCaps = sorted(Array.from(caps.keys()).filter(s => !systems.has(s)));
    if (unusedCaps.length) fail('system_budgets has names matching no option: ' + unusedCaps.join(', ') + '; available systems: ' + sorted(systems).join(', '));
    const uncappedSystems = sorted(Array.from(systems).filter(s => !caps.has(s)));
    for (const o of options.values()) if ([...o.requires, ...o.conflicts].some(key => !options.has(key))) fail('Unknown dependency or conflict');
    const active = new Set(), visited = new Set(), topology = [];
    function visit(key) {
      if (active.has(key)) fail('Cyclic prerequisites');
      if (visited.has(key)) return;
      active.add(key);
      for (const req of sorted(options.get(key).requires)) visit(req);
      active.delete(key); visited.add(key); topology.push(key);
    }
    for (const key of options.keys()) visit(key);
    const done = topology.filter(key => completed.has(key)).map(key => options.get(key));
    if (done.some(o => Array.from(o.requires).some(key => !completed.has(key)))) fail('Completed options must include their completed prerequisites');
    const doneGroups = done.filter(o => o.group).map(o => o.group);
    if (doneGroups.length !== new Set(doneGroups).size || done.some(o => Array.from(o.conflicts).some(key => completed.has(key)))) fail('Completed options contain a conflict or exclusive route');
    for (const o of done) for (const goal of o.goals) met.add(goal);
    const candidates = Array.from(options.keys()).filter(key => options.get(key).ready);
    let validCount = 0, cheapest = [], runnerUp = [], best = null, cheapestCount = 0;
    let targetCount = 0, targetBest = null, targetCheapest = [], targetCheapestCount = 0;
    const counts = { budget: 0, system_budget: 0, dependencies_or_conflicts: 0, shared_resources: 0, goals: 0 };
    function resultCompare(a, b) {
      const av = fromText(a.cash_outlay).value, bv = fromText(b.cash_outlay).value;
      if (av !== bv) return av < bv ? -1 : 1;
      if (a.selected.length !== b.selected.length) return a.selected.length - b.selected.length;
      for (let i = 0; i < a.selected.length; i++) { const diff = compareText(a.selected[i], b.selected[i]); if (diff) return diff; }
      return 0;
    }
    const top = list => list.sort(resultCompare).slice(0, 10);
    // Match itertools.product((False, True)): first option is the highest bit.
    for (let bits = 0; bits < 2 ** candidates.length; bits++) {
      const selected = new Set(candidates.filter((_, i) => bits & (1 << (candidates.length - 1 - i))));
      const selectedKeys = topology.filter(key => selected.has(key)), chosen = selectedKeys.map(key => options.get(key));
      const effective = new Set([...selected, ...completed]), effectiveProjects = chosen.concat(done);
      const groups = effectiveProjects.filter(o => o.group).map(o => o.group);
      if (groups.length !== new Set(groups).size || effectiveProjects.some(o => Array.from(o.requires).some(key => !effective.has(key)) || Array.from(o.conflicts).some(key => effective.has(key)))) {
        counts.dependencies_or_conflicts++; continue;
      }
      const covered = new Set([...met, ...chosen.flatMap(o => Array.from(o.goals))]);
      if (covered.size !== goals.size) { counts.goals++; continue; }
      const used = new Map(Array.from(stock.keys(), r => [r, sum(chosen.map(o => o.consumes.get(r) || zero()))]));
      if (Array.from(stock, ([r, qty]) => used.get(r).value > qty.value).some(Boolean)) { counts.shared_resources++; continue; }
      const costBySystem = new Map();
      for (const o of chosen) costBySystem.set(o.system, add(costBySystem.get(o.system) || zero(), o.cash));
      const cost = sum(chosen.map(o => o.cash));
      const categoryGaps = new Map(Array.from(caps, ([system, cap]) => [system, shortfall(costBySystem.get(system) || zero(), cap)]));
      const targetRecord = { selected: selectedKeys, cash_outlay: fmt(cost), cash_by_system: formattedMap(costBySystem),
        global_cash_shortfall: fmt(shortfall(cost, available)), system_budget_shortfalls: formattedMap(categoryGaps),
        scope: '满足所列目标/资格/依赖/库存，尚未据预算筛选；不是当前可购方案' };
      targetCount++;
      if (targetBest === null || cost.value < targetBest.value) { targetBest = cost; targetCheapest = [targetRecord]; targetCheapestCount = 1; }
      else if (cost.value === targetBest.value) { targetCheapestCount++; targetCheapest = top(targetCheapest.concat(targetRecord)); }
      if (Array.from(categoryGaps.values()).some(v => v.value > 0n)) { counts.system_budget++; continue; }
      if (cost.value > available.value) { counts.budget++; continue; }
      const opp = chosen.some(o => o.opportunity === null) ? null : sum(chosen.map(o => o.opportunity));
      const candidate = { selected: selectedKeys, cash_outlay: fmt(cost), economic_cost: opp === null ? null : fmt(add(cost, opp)),
        remaining_after_reserve: fmt(subtract(available, cost)), resources_used: formattedMap(used),
        resources_left: record(Array.from(stock, ([r, qty]) => [r, fmt(subtract(qty, used.get(r)))])),
        cash_by_system: formattedMap(costBySystem), system_budget_remaining: record(Array.from(caps, ([r, cap]) => [r, fmt(subtract(cap, costBySystem.get(r) || zero()))])) };
      validCount++;
      if (best === null || cost.value < best.value) { runnerUp = top(cheapest.concat(runnerUp)); best = cost; cheapest = [candidate]; cheapestCount = 1; }
      else if (cost.value === best.value) { cheapestCount++; cheapest = top(cheapest.concat(candidate)); }
      else runnerUp = top(runnerUp.concat(candidate));
    }
    const missing = sorted(Array.from(goals.keys()).filter(g => !met.has(g)));
    const status = !missing.length ? 'goals_already_met' : validCount ? (quoteConditions.length ? 'conditional_feasible' : 'known_feasible') : 'no_demonstrated_feasible_plan';
    let conclusion = status === 'goals_already_met' ? '已知现状已经满足所列目标，保留现状无需新增花费' : validCount ? '按录入金额、资格与目标效果的条件计算，所列候选最少新增现金为' + fmt(best) + ctx.currency : '当前已确认的候选中没有同时达标且预算内的完整方案';
    if (review.length) conclusion += '；仍有待核实候选，不能宣称全局最省或全局无解';
    const result = { calculator: 'whole_budget_portfolio', title: data.title, status, conclusion, context: ctx,
      budget: fmt(budget), protected_reserve: fmt(reserve), spendable: fmt(available), system_budgets: formattedMap(caps), systems_without_specific_cap: uncappedSystems,
      goals: Array.from(goals.values()), keep_current: { cash_outlay: '0', met: sorted(met), missing },
      lowest_cash_plans: cheapest, lowest_cash_plan_count: cheapestCount, truncated: cheapestCount > 10, other_feasible_plans: runnerUp,
      target_plans_before_money_constraints: targetCheapest, target_plan_count_before_money_constraints: targetCount,
      minimum_target_cash_before_money_constraints: fmt(targetBest), minimum_target_plan_count: targetCheapestCount,
      target_plan_diagnostics_truncated: targetCheapestCount > 10, known_feasible_count: validCount, quote_conditions: quoteConditions,
      review_before_inclusion: review, projects: Array.from(options.values(), o => ({ id: o.id, label: o.label, system: o.system, goals: sorted(o.goals),
        cash_outlay: fmt(o.cash), opportunity_cost: fmt(o.opportunity), cost_lines: o.cost_lines, owned_materials: o.owned_materials,
        effect_basis: o.effect_basis, ready_for_comparison: o.ready })), enumerated: 2 ** candidates.length, filtered_counts: counts,
      recommendation_changes_when: ['当前预算或预留金变化', '同区同目标报价变化或过期', '旧装备出售尚未到账', '现有资源、资格或目标事实被修正', '发现未列入的更便宜或更符合目标的候选'],
      limits: ['目标与效果依据由宿主和用户明确确认，不根据门派、权重或宝石原始属性推断实战达标',
        '只优化所列独立整项项目的新增现金；库存机会成本另报，不代表经济成本最优',
        'consumes检查共享库存/可操作时间，禁止同一库存重复抵扣；项目不能在规划中创造新资源',
        '成本按采购前现金填写，不能抵扣未到账卖旧收入；不同货币不能混在一份计划',
        '依赖按顺序显示，不模拟价格随时间变化、收益、概率或隐藏机制'] };
    if (own(data, 'completed_options')) {
      result.completed_options = topology.filter(key => completed.has(key));
      for (const project of result.projects) project.completed = completed.has(project.id);
    }
    return result;
  }
  function renderText(result, resourceUnits) {
    const currency = result.context.currency, money = value => value === null ? '未知' : String(value) + currency;
    const units = resourceUnits || {}, byid = new Map(result.projects.map(p => [p.id, p])), goals = new Map(result.goals.map(g => [g.id, g.target]));
    const caps = result.system_budgets;
    const out = [result.title, result.conclusion,
      '预算 ' + money(result.budget) + '；预留 ' + money(result.protected_reserve) + '；本次可动用 ' + money(result.spendable),
      '保留现状：新增0' + currency + '；未达目标 ' + (result.keep_current.missing.map(k => goals.get(k)).join('、') || '无')];
    if (result.keep_current.met.length) out.push('已确认达成：' + result.keep_current.met.map(k => goals.get(k)).join('、'));
    if (result.completed_options && result.completed_options.length) {
      out.push('已完成项目（不再计费或耗用库存）：' + result.completed_options.map(key => byid.get(key).label).join('、'));
      out.push('预算与共享库存按本次录入的当前余额使用，不会自动扣除历史支出或消耗');
    }
    out.push('列出 ' + result.lowest_cash_plans.length + '/' + result.lowest_cash_plan_count + ' 个同价最低方案；已知可行方案共 ' + result.known_feasible_count);
    if (Object.keys(caps).length) out.push('分类预算不可互挪：' + sorted(Object.keys(caps)).map(k => k + '≤' + money(caps[k])).join('；'));
    if (Object.keys(caps).length && result.systems_without_specific_cap.length) out.push('这些分类未设独立上限，但仍受总预算与预留约束：' + result.systems_without_specific_cap.join('、'));
    function categoryLines(plan, diagnostic) {
      for (const system of sorted(new Set(Object.keys(plan.cash_by_system).concat(Object.keys(caps))))) {
        let line = '  分类 ' + system + '：计划支出 ' + money(own(plan.cash_by_system, system) ? plan.cash_by_system[system] : '0');
        if (own(caps, system)) {
          line += '；上限 ' + money(caps[system]);
          line += diagnostic ? '；分类缺口' + money(plan.system_budget_shortfalls[system]) : '；计划后分类余额 ' + money(plan.system_budget_remaining[system]);
        } else line += '；未设独立上限，仍受总预算与预留约束';
        out.push(line);
      }
    }
    function costLines(project) {
      for (const row of project.cost_lines) {
        const suffix = row.status === 'unknown_quote' ? '；报价未知，不能按0' : row.status === 'stale_quote' ? '；报价过期' : '';
        out.push('    采购/费用：' + row.label + ' × ' + row.quantity + '；小计 ' + money(row.subtotal) + suffix);
      }
      for (const row of project.owned_materials) {
        const suffix = row.status === 'stale_quote' ? '；报价过期，当前机会成本保持未知' : '';
        out.push('    库存机会成本（不是新增现金）：' + row.label + ' × ' + row.quantity + '；录入小计 ' + money(row.subtotal) + suffix);
      }
    }
    result.lowest_cash_plans.forEach((plan, i) => {
      out.push('方案 ' + (i + 1) + '：现金 ' + money(plan.cash_outlay) + '；预留后余款 ' + money(plan.remaining_after_reserve) + '；经济成本 ' + money(plan.economic_cost));
      categoryLines(plan, false);
      if (!plan.selected.length) out.push('  无需新增项目，保留现状');
      plan.selected.forEach((key, n) => {
        const project = byid.get(key);
        out.push('  ' + (n + 1) + '. ' + project.label + '（新增现金 ' + money(project.cash_outlay) + '）');
        costLines(project);
      });
      if (Object.keys(plan.resources_used).length) {
        out.push('  共享资源计划（尚未消耗；仅在此方案实际完成后才是预计余额）：');
        for (const resource of sorted(Object.keys(plan.resources_used))) {
          const unit = own(units, resource) ? units[resource] : '';
          out.push('    ' + resource + '：计划用 ' + plan.resources_used[resource] + unit + '；预计剩余 ' + plan.resources_left[resource] + unit);
        }
      } else out.push('  本方案未列共享资源消耗');
    });
    if (!result.lowest_cash_plans.length && result.target_plans_before_money_constraints.length) {
      out.push('目标已能达到但资金条件尚不成立，最低现金组合如下（不是可立即执行的推荐，尚未扣款或耗用库存）：');
      for (const plan of result.target_plans_before_money_constraints) {
        out.push('  ' + plan.selected.map(k => byid.get(k).label).join(' + ') + '：现金' + money(plan.cash_outlay) + '；全局现金缺口' + money(plan.global_cash_shortfall));
        categoryLines(plan, true);
      }
      if (result.target_plan_diagnostics_truncated) out.push('  仅列出' + result.target_plans_before_money_constraints.length + '/' + result.minimum_target_plan_count + '个同价目标组合');
    }
    if (!result.lowest_cash_plans.length && !result.target_plans_before_money_constraints.length) {
      out.push('尚无通过目标、资格、依赖和共享库存检查的完整组合；没有可执行方案，未扣款或耗用库存');
      for (const [key, label] of [['dependencies_or_conflicts', '前置/互斥不满足'], ['shared_resources', '共享资源不足'], ['goals', '目标未全满足']]) {
        if (result.filtered_counts[key]) out.push('  ' + label + '：排除 ' + result.filtered_counts[key] + ' 个组合');
      }
    }
    if (result.quote_conditions.length) out.push('报价条件：' + result.quote_conditions.map(x => byid.get(x.id).label + '：' + x.kinds.join(',') + '（' + x.meaning + '）').join('；'));
    const reasons = { eligibility_unknown: '资格未确认', eligibility_ineligible: '资格不成立', unknown_cash_cost: '新增现金缺少报价', stale_quote: '采购报价过期' };
    for (const review of result.review_before_inclusion) {
      const project = byid.get(review.id);
      out.push('待核实候选 ' + project.label + '：' + review.reasons.map(k => own(reasons, k) ? reasons[k] : k).join('、'));
      costLines(project);
    }
    out.push('需要重算的变化：' + result.recommendation_changes_when.join('；'));
    out.push(...result.limits.map(x => '边界：' + x));
    return out.join('\n') + '\n';
  }
  return Object.freeze({ calculate, renderText, InputError, limits: Object.freeze({ maxOptions: MAX_OPTIONS, maxAmount: '1000000000000', decimalPlaces: 6 }) });
});
