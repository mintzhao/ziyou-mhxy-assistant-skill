/* Offline UI. Exact decimal parsing and all calculations belong to engine.js. */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./engine.js'), require('./resources.js'), require('./intake.js'));
  else { root.MHXYPlannerUI = factory(root.MHXYEngine, root.MHXYResources, root.MHXYIntake); if (root.document) root.MHXYPlannerUI.mount(root.document); }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (Engine, Resources, Intake) {
  'use strict';
  const SAMPLE_TEXT = "{\n  \"schema_version\": \"1.0\",\n  \"title\": \"纯合成示例：109 神木林手工装备比较（非真实角色或市价）\",\n  \"notes\": \"所有数值与价格均为演示构造，不代表游戏公式、真实商品、门派结论或配装建议。价格单位也仅为演示。\",\n  \"budget\": 900,\n  \"currency\": \"演示预算单位\",\n  \"metrics\": [\n    {\n      \"id\": \"magic\",\n      \"name\": \"法伤\",\n      \"unit\": \"点\",\n      \"direction\": \"maximize\"\n    },\n    {\n      \"id\": \"speed\",\n      \"name\": \"速度\",\n      \"unit\": \"点\",\n      \"direction\": \"maximize\"\n    },\n    {\n      \"id\": \"defense\",\n      \"name\": \"防御\",\n      \"unit\": \"点\",\n      \"direction\": \"maximize\"\n    }\n  ],\n  \"weights\": {\n    \"magic\": 1,\n    \"speed\": 0.5,\n    \"defense\": 0.2\n  },\n  \"baseline\": {\n    \"label\": \"合成现有面板\",\n    \"stats\": {\n      \"magic\": 1200,\n      \"speed\": 350,\n      \"defense\": 700\n    },\n    \"equipment\": {\n      \"weapon\": \"合成当前武器\",\n      \"necklace\": \"合成当前项链\",\n      \"shoes\": \"合成当前鞋子\"\n    },\n    \"evidence\": \"synthetic\"\n  },\n  \"options\": [\n    {\n      \"id\": \"weapon-a\",\n      \"name\": \"合成武器 A\",\n      \"slot\": \"weapon\",\n      \"price\": 600,\n      \"deltas\": {\n        \"magic\": 40,\n        \"speed\": -5,\n        \"defense\": 0\n      },\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\"\n    },\n    {\n      \"id\": \"weapon-b\",\n      \"name\": \"合成武器 B\",\n      \"slot\": \"weapon\",\n      \"price\": 900,\n      \"deltas\": {\n        \"magic\": 65,\n        \"speed\": -10,\n        \"defense\": 0\n      },\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\"\n    },\n    {\n      \"id\": \"necklace-a\",\n      \"name\": \"合成项链 A\",\n      \"slot\": \"necklace\",\n      \"price\": 300,\n      \"deltas\": {\n        \"magic\": 25,\n        \"speed\": 0,\n        \"defense\": -10\n      },\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\"\n    },\n    {\n      \"id\": \"necklace-b\",\n      \"name\": \"合成项链 B\",\n      \"slot\": \"necklace\",\n      \"price\": 500,\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\",\n      \"measured_stats\": {\n        \"magic\": 1235,\n        \"speed\": 350,\n        \"defense\": 705\n      }\n    },\n    {\n      \"id\": \"shoes-a\",\n      \"name\": \"合成鞋子 A\",\n      \"slot\": \"shoes\",\n      \"price\": 250,\n      \"deltas\": {\n        \"magic\": 0,\n        \"speed\": 20,\n        \"defense\": 10\n      },\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\"\n    },\n    {\n      \"id\": \"shoes-free\",\n      \"name\": \"合成已有备用鞋（新增花费为零）\",\n      \"slot\": \"shoes\",\n      \"price\": 0,\n      \"deltas\": {\n        \"magic\": 0,\n        \"speed\": 5,\n        \"defense\": -5\n      },\n      \"fees\": 0,\n      \"evidence\": \"synthetic\",\n      \"source\": \"纯合成示例，无商品链接、报价时间或真实价格\",\n      \"owned\": true\n    }\n  ],\n  \"top_n\": 8,\n  \"character\": {\n    \"level\": 109,\n    \"school\": \"神木林（合成背景）\",\n    \"server\": \"仅演示，无真实区服\",\n    \"purpose\": \"展示预算、面板目标与人工偏好取舍\"\n  },\n  \"constraints\": {\n    \"min_stats\": {\n      \"speed\": 340,\n      \"defense\": 680\n    },\n    \"max_stats\": {},\n    \"locked_slots\": [],\n    \"required_options\": [],\n    \"excluded_options\": [],\n    \"conflicts\": [\n      [\n        \"weapon-b\",\n        \"necklace-b\"\n      ]\n    ],\n    \"max_changes\": 3\n  },\n  \"budget_scenarios\": [\n    {\n      \"label\": \"先不花钱\",\n      \"budget\": 0\n    },\n    {\n      \"label\": \"较低预算\",\n      \"budget\": 500\n    },\n    {\n      \"label\": \"较高预算，仅作比较\",\n      \"budget\": 1200\n    }\n  ],\n  \"weight_scenarios\": [\n    {\n      \"label\": \"更重视速度的演示偏好\",\n      \"weights\": {\n        \"magic\": 0.5,\n        \"speed\": 2,\n        \"defense\": 0.2\n      }\n    },\n    {\n      \"label\": \"更重视防御的演示偏好\",\n      \"weights\": {\n        \"magic\": 0.5,\n        \"speed\": 0.5,\n        \"defense\": 2\n      }\n    }\n  ],\n  \"manual_plans\": [\n    {\n      \"label\": \"A：武器 A + 项链 A\",\n      \"option_ids\": [\n        \"weapon-a\",\n        \"necklace-a\"\n      ]\n    },\n    {\n      \"label\": \"B：武器 B + 鞋子 A\",\n      \"option_ids\": [\n        \"weapon-b\",\n        \"shoes-a\"\n      ]\n    }\n  ],\n  \"checklist\": [\n    {\n      \"item\": \"示例是否为真实角色与市价\",\n      \"status\": \"not_applicable\",\n      \"note\": \"这是纯合成演示，不可用于购买\"\n    },\n    {\n      \"item\": \"同一临时符、坐骑与套装测试状态\",\n      \"status\": \"unverified\",\n      \"note\": \"真实使用必须自行确认\"\n    },\n    {\n      \"item\": \"使用资格、套装和特技联动\",\n      \"status\": \"unverified\",\n      \"note\": \"本工具不自动验证\"\n    }\n  ]\n}\n";
  const BLANK_TEXT = "{\n  \"schema_version\": \"1.0\",\n  \"title\": \"我的装备预算计划\",\n  \"budget\": null,\n  \"currency\": \"请填写统一货币单位\",\n  \"metrics\": [\n    {\n      \"id\": \"metric\",\n      \"name\": \"请填写面板指标\",\n      \"unit\": \"点\",\n      \"direction\": \"maximize\"\n    }\n  ],\n  \"baseline\": {\n    \"label\": \"当前装备与面板\",\n    \"stats\": {\n      \"metric\": null\n    },\n    \"equipment\": {},\n    \"evidence\": \"unverified\"\n  },\n  \"options\": [],\n  \"constraints\": {},\n  \"budget_scenarios\": [],\n  \"weight_scenarios\": [],\n  \"manual_plans\": [],\n  \"checklist\": [\n    {\n      \"item\": \"报价包含所有必要费用且单位一致\",\n      \"status\": \"unverified\"\n    },\n    {\n      \"item\": \"候选变化在同一测试状态测得\",\n      \"status\": \"unverified\"\n    },\n    {\n      \"item\": \"装备使用资格、套装和特技联动已人工检查\",\n      \"status\": \"unverified\"\n    }\n  ],\n  \"objective\": \"pareto\"\n}\n";
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  const record = value => value !== null && typeof value === 'object' && !Array.isArray(value) && !(Engine && Engine.isNumeric && Engine.isNumeric(value));
  const entries = value => record(value) ? Object.entries(value) : [];
  const list = value => Array.isArray(value) ? value : [];
  const text = value => value === undefined || value === null ? '' : String(value);
  const put = (obj, key, value) => Object.defineProperty(obj, key, {value, writable:true, enumerable:true, configurable:true});
  const numericText = value => value === undefined || value === null ? '' : Engine.stringify(value, 0);
  const fresh = source => Engine.parse(source);
  const evidenceLabels = {user_confirmed:'用户已确认', unverified:'尚未核实', synthetic:'合成演示'};
  const slotChoices=[['weapon','武器'],['helmet','头盔 / 发钗'],['necklace','项链'],['armor','铠甲 / 女衣'],['belt','腰带'],['shoes','鞋子'],['ring','戒指'],['earring','耳饰'],['bracelet','手镯'],['accessory','配饰']];
  const evidenceChoices = [['unverified','尚未核实'],['user_confirmed','用户已确认'],['synthetic','合成演示']];
  function uniqueId(items, prefix) { let n = 1; while (items.some(item => item.id === prefix + n)) n++; return prefix + n; }
  function editableShape(data) {
    if (!record(data) || data.schema_version !== '1.0') throw new Error('不支持此装备草稿版本；仅支持schema_version 1.0，未替换当前内容。');
    if (!record(data) || !Array.isArray(data.metrics) || (own(data,'weights') && !record(data.weights)) || !record(data.baseline) || !record(data.baseline.stats) || !Array.isArray(data.options)) throw new Error('输入必须包含 metrics、baseline.stats 和 options；高级权重如有填写须为对象。可先下载空白草稿，再补齐内容。');
    if (data.metrics.length > 12 || data.options.length > 64) throw new Error('表单最多支持 12 个指标、64 个候选。');
    if (data.metrics.some(m => !record(m) || typeof m.id !== 'string') || data.options.some(o => !record(o) || typeof o.id !== 'string' || (o.deltas !== undefined && !record(o.deltas)) || (o.measured_stats !== undefined && !record(o.measured_stats)))) throw new Error('指标、候选及其属性映射结构不正确。');
    for (const k of ['character','constraints']) if (data[k] !== undefined && !record(data[k])) throw new Error(k + ' 必须是对象。');
    if (data.baseline.equipment !== undefined && (!record(data.baseline.equipment)||Object.keys(data.baseline.equipment).length>12)) throw new Error('baseline.equipment 必须是最多12部位的对象。');
    const c = data.constraints || {};
    for (const k of ['min_stats','max_stats']) if (c[k] !== undefined && !record(c[k])) throw new Error('constraints.' + k + ' 必须是对象。');
    for (const [k,max] of [['locked_slots',12],['required_options',64],['excluded_options',64],['conflicts',128]]) if (c[k] !== undefined && (!Array.isArray(c[k])||c[k].length>max)) throw new Error('constraints.' + k + ' 必须是有界数组（最多 '+max+' 项）。');
    for (const [key,max] of [['budget_scenarios',8],['weight_scenarios',8],['manual_plans',2],['checklist',20]]) {
      if (data[key] !== undefined && (!Array.isArray(data[key]) || data[key].length > max || data[key].some(v => !record(v)))) throw new Error(key + ' 结构不正确或超过数量上限。');
    }
    if (list(data.weight_scenarios).some(s => !record(s.weights)) || list(data.manual_plans).some(s => !Array.isArray(s.option_ids))) throw new Error('权重场景需包含 weights，手动方案需包含 option_ids。');
    function scalarString(object,key,path){if(object[key]!==undefined&&typeof object[key]!=='string')throw new Error(path+' 必须是文字；未替换当前草稿。');}
    for(const key of ['schema_version','title','currency','notes','objective'])scalarString(data,key,key);
    for(const key of ['label','evidence'])scalarString(data.baseline,key,'baseline.'+key);
    for(const [key,value] of entries(data.baseline.equipment))if(typeof value!=='string')throw new Error('当前装备名称必须是文字：'+key);
    data.metrics.forEach((m,i)=>{for(const key of ['name','unit','direction'])scalarString(m,key,'metrics['+i+'].'+key);});
    data.options.forEach((o,i)=>{for(const key of ['name','slot','evidence','source','notes'])scalarString(o,key,'options['+i+'].'+key);if(o.owned!==undefined&&typeof o.owned!=='boolean')throw new Error('owned 必须是布尔值');});
    if(data.character)for(const key of ['school','server','purpose'])scalarString(data.character,key,'character.'+key);
    for(const key of ['locked_slots','required_options','excluded_options'])if(list(c[key]).some(v=>typeof v!=='string'))throw new Error('constraints.'+key+' 只能包含文字标识');
    if(list(c.conflicts).length>128||list(c.conflicts).some(pair=>!Array.isArray(pair)||pair.length!==2||pair.some(v=>typeof v!=='string')))throw new Error('每组互斥必须包含两个候选标识，最多128组');
    for(const key of ['budget_scenarios','weight_scenarios','manual_plans'])list(data[key]).forEach((s,i)=>scalarString(s,'label',key+'['+i+'].label'));
    list(data.manual_plans).forEach(s=>{if(s.option_ids.length>12||s.option_ids.some(v=>typeof v!=='string'))throw new Error('手动方案最多12个文字候选标识');});
    list(data.checklist).forEach((item,i)=>{for(const key of ['item','status','note'])scalarString(item,key,'checklist['+i+'].'+key);});
    return data;
  }
  function validateReport(value) {
    function fail(message){throw new Error(message);}
    function obj(v,p){if(!record(v))fail(p+' 必须是对象');return v;}
    function string(v,p,max=4000){if(typeof v!=='string'||v.length>max)fail(p+' 必须是受限长度的文字');return v;}
    function array(v,p,max){if(!Array.isArray(v)||v.length>max)fail(p+' 必须是数组且最多 '+max+' 项');return v;}
    function decimal(v,p,nonnegative){if(typeof v!=='string'||v.length>100||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$/.test(v))fail(p+' 必须是报告中的精确数字字符串');if(nonnegative&&v.startsWith('-')&&!/^-0+(?:\.0*)?(?:[eE][-+]?\d+)?$/.test(v))fail(p+' 不能为负数');}
    obj(value,'报告');const objective=value.objective===undefined?'weighted':value.objective;
    if(!['weighted','min_cost','pareto'].includes(objective))fail('报告 objective 无效');
    const models={weighted:'user_defined_linear_preferences',min_cost:'user_defined_min_cost',pareto:'user_defined_pareto'};
    if(value.schema_version!=='1.0'||value.model!==models[objective])fail('不是 schema_version 1.0 的配装目标比较报告');
    for(const key of ['objective_description','ranking_rule'])if(value[key]!==undefined)string(value[key],key);
    string(value.title,'title');if(value.notes!==undefined)string(value.notes,'notes',4000);string(value.currency,'currency',200);decimal(value.budget,'budget',true);
    const metrics=array(value.metrics,'metrics',12);if(!metrics.length)fail('报告至少需要一个指标');const ids=new Set();
    metrics.forEach((m,i)=>{obj(m,'metrics');string(m.id,'metric.id',64);string(m.name,'metric.name',200);string(m.unit,'metric.unit',100);if(ids.has(m.id))fail('报告指标 ID 重复');ids.add(m.id);if(!['maximize','minimize'].includes(m.direction))fail('报告指标方向无效');});
    function map(v,p,complete){obj(v,p);if(Object.keys(v).some(k=>!ids.has(k)))fail(p+' 含未知指标');for(const id of complete?ids:Object.keys(v))decimal(v[id],p+'.'+id,false);}
    if(value.weights!==null)map(value.weights,'weights',true);else if(objective==='weighted')fail('加权报告需要权重');
    function strings(v,p,max=200){array(v,p,max).forEach(s=>string(s,p));}
    function combo(c,p,mode=objective){obj(c,p);decimal(c.price,p+'.price',true);decimal(c.remaining_budget,p+'.remaining_budget',false);if(mode==='weighted')decimal(c.score,p+'.score',false);else if(c.score!==null)fail(p+'.score 在非加权模式必须为 null');map(c.deltas,p+'.deltas',true);map(c.final_stats,p+'.final_stats',true);if(typeof c.is_baseline!=='boolean')fail(p+'.is_baseline 必须为布尔值');
      if(c.feasible!==undefined&&typeof c.feasible!=='boolean')fail(p+'.feasible 必须为布尔值');if(c.violations!==undefined)strings(c.violations,p+'.violations',200);if(c.drawbacks!==undefined){strings(c.drawbacks,p+'.drawbacks',12);if(c.drawbacks.some(id=>!ids.has(id)))fail(p+'.drawbacks 含未知指标');}
      if(c.label!==undefined)string(c.label,p+'.label');if(c.equipment!==undefined){obj(c.equipment,p+'.equipment');if(Object.keys(c.equipment).length>12)fail('当前装备最多12部位');Object.values(c.equipment).forEach(s=>string(s,'当前装备名',200));}
      array(c.selection,p+'.selection',12).forEach(o=>{obj(o,p+'.selection');for(const key of ['id','name','slot'])string(o[key],p+'.selection.'+key,200);for(const key of ['quoted_price','fees','total_cost'])if(o[key]!==undefined)decimal(o[key],key,true);for(const key of ['evidence','source','replaces'])if(o[key]!==undefined)string(o[key],key,1000);if(o.notes!==undefined)string(o.notes,'selection.notes',4000);if(o.owned!==undefined&&typeof o.owned!=='boolean')fail('owned 必须为布尔值');});
    }
    combo(value.baseline,'baseline');if(value.best!==null)combo(value.best,'best');for(const k of ['alternatives','pareto'])array(value[k],k,k==='pareto'?100:50).forEach(c=>combo(c,k));
    if(value.status!==undefined&&!['ok','no_feasible_plan'].includes(value.status))fail('报告 status 无效');
    if(value.status==='ok'&&objective!=='pareto'&&value.best===null)fail('状态与 best 不一致');if(objective==='pareto'&&(value.best!==null||value.alternatives.length))fail('Pareto 报告不能指定 best 或高分备选');if(value.status==='no_feasible_plan'&&value.best!==null)fail('状态与 best 不一致');
    if(value.disclaimer!==undefined)strings(value.disclaimer,'disclaimer',30);obj(value.summary,'summary');
    if(value.diagnostics!==undefined)array(value.diagnostics,'diagnostics',100).forEach(d=>{obj(d,'diagnostics');string(d.kind,'diagnostics.kind',100);string(d.message,'diagnostics.message');});
    if(value.evidence_summary!==undefined){obj(value.evidence_summary,'evidence_summary');if(value.evidence_summary.notice!==undefined)string(value.evidence_summary.notice,'notice');if(value.evidence_summary.baseline_evidence!==undefined)string(value.evidence_summary.baseline_evidence,'baseline_evidence',100);}
    for(const [key,max] of [['budget_scenarios',8],['weight_scenarios',8],['manual_plans',2]])if(value[key]!==undefined)array(value[key],key,max).forEach(s=>{
      obj(s,key);string(s.label,key+'.label',200);if(key==='manual_plans'){combo(s.plan,key+'.plan');return;}
      const mode=key==='weight_scenarios'?'weighted':objective;
      if(s.objective!==undefined&&s.objective!==mode)fail(key+' 比较目标不一致');
      if(s.best!==null)combo(s.best,key+'.best',mode);
      if(key==='budget_scenarios')decimal(s.budget,key+'.budget',true);else map(s.weights,key+'.weights',true);
      if(mode==='pareto'){if(s.best!==null)fail('Pareto 情景不能指定 best');array(s.pareto,key+'.pareto',100).forEach(c=>combo(c,key+'.pareto',mode));for(const field of ['pareto_total','pareto_shown'])count(s[field],key+'.'+field);if(typeof s.pareto_truncated!=='boolean')fail('Pareto 情景缺少截断说明');}
    });
    if(value.checklist!==undefined)array(value.checklist,'checklist',20).forEach(c=>{obj(c,'checklist');string(c.item,'checklist.item',200);if(!['confirmed','unverified','not_applicable'].includes(c.status))fail('核对状态无效');if(c.note!==undefined)string(c.note,'checklist.note',1000);});
    function count(v,p){if(v===undefined)return;const raw=Engine.isNumeric(v)?Engine.stringify(v,0):typeof v==='number'?String(v):'';if(!/^\d+$/.test(raw)||BigInt(raw)>100000000n)fail(p+' 必须是有界非负整数计数');}
    for(const key of ['combinations_possible','combinations_evaluated','within_budget','feasible_count','rejected_by_constraints','distinct_vectors','pareto_total','pareto_shown','pareto_comparisons'])count(value.summary[key],'summary.'+key);
    if(value.evidence_summary)for(const key of ['confirmed_options','unverified_options','synthetic_options'])count(value.evidence_summary[key],'evidence_summary.'+key);
    for(const key of ['budget_scenarios','weight_scenarios'])list(value[key]).forEach(s=>count(s.feasible_count,key+'.feasible_count'));
    // Only report counts are JSON numbers. Validate every numeric token before
    // converting these bounded exact integers; money/stats/weights stay strings.
    function safeCounts(v){if(Engine.isNumeric(v)){const lex=Engine.stringify(v,0);if(!/^\d+$/.test(lex)||BigInt(lex)>100000000n)fail('报告 JSON 数字只允许 0–100000000 的整数计数；金额与属性必须使用字符串');return;}if(typeof v==='number'){if(!/^[0-9]+$/.test(String(v))||BigInt(v)>100000000n)fail('报告计数超出安全范围');return;}if(Array.isArray(v))v.forEach(safeCounts);else if(record(v))Object.values(v).forEach(safeCounts);}
    safeCounts(value);return JSON.parse(Engine.stringify(value,0));
  }
  const RESOURCE_SCHEMA = 'mhxy-resource-draft/v2';
  function resourceDraft(raw) {
    const value=typeof raw==='string'?Engine.parse(raw):raw;
    if(!record(value)||!record(value.inputs))throw new Error('不是资源草稿；装备草稿请用页面顶部打开。');
    if(value.schema!==undefined&&value.schema!==RESOURCE_SCHEMA&&value.schema!=='mhxy-resource-draft/v1')throw new Error('不支持此资源草稿版本，未替换当前内容。');
    if(value.schema===undefined&&value.title!=='独立资源试算：不是配装优化输入')throw new Error('无法识别旧版资源导出。');
    if(Object.keys(value).some(k=>!['schema','title','inputs','results','notice','question_receipt'].includes(k)))throw new Error('资源草稿含未知字段。');
    const input=value.inputs;
    if(Object.keys(input).some(k=>!['cultivation','gems'].includes(k))||!record(input.cultivation)||!record(input.gems))throw new Error('资源输入结构不完整。');
    function fields(obj,keys){if(Object.keys(obj).length!==keys.length||keys.some(k=>!own(obj,k))||Object.keys(obj).some(k=>!keys.includes(k)))throw new Error('资源字段缺失或未知。');}
    function bounded(v){if(typeof v!=='string'||v.length>100||v.includes('\0'))throw new Error('资源表单值须为不超过100字的文本。');}
    fields(input.cultivation,['type','currentLevel','targetLevel','currentProgressXp','confirmedCap']);
    Object.values(input.cultivation).forEach(bounded);
    if(input.cultivation.type!==''&&!Resources.cultivationTypes.some(t=>t.id===input.cultivation.type))throw new Error('未知修炼类型。');
    fields(input.gems,['gemType','currentForge','targetForge','quotes']);
    ['gemType','currentForge','targetForge'].forEach(k=>bounded(input.gems[k]));
    if(!Resources.gemTypes.some(t=>t.id===input.gems.gemType)||!record(input.gems.quotes))throw new Error('未知宝石类型或报价结构。');
    if(Object.keys(input.gems.quotes).length>20)throw new Error('宝石报价最多20级。');
    for(const [key,v] of Object.entries(input.gems.quotes)){if(!/^(?:[1-9]|1[0-9]|20)$/.test(key))throw new Error('宝石报价等级必须为1–20。');bounded(v);}
    if(value.question_receipt!==undefined&&value.question_receipt!==null){if(!Intake||Intake.validate(value.question_receipt).route!=='resources')throw new Error('资源问题出处不匹配');}
    // Saved results are untrusted historical caches, never loaded into active results.
    return JSON.parse(Engine.stringify(input,0));
  }
  function mount(doc, environment) {
    const env = environment || (typeof globalThis !== 'undefined' ? globalThis : {});
    const $ = id => doc.getElementById(id);
    if (!Engine) { $('input-status').textContent = '计算引擎未加载。请把 index.html、engine.js、app.js 放在同一个目录后重新打开。'; $('calculate-button').disabled = true; return null; }
    let data = fresh(SAMPLE_TEXT), report = null, source = '纯合成演示', dirty = false, advancedDirty = false, inputVersion = 0, uid = 0, fileGeneration = 0, resultGeneration = 0, resourceDirty = false, reportSource = null, resourceVersion = 0, resourceGeneration = 0;
    const resourceState={cultivation:{type:'attack',currentLevel:'',targetLevel:'',currentProgressXp:'',confirmedCap:''},gems:{gemType:'moon',currentForge:'',targetForge:'',quotes:{}}};
    const resourceResults={cultivation:null,gems:null};
    let loadResources = () => false, applyResourceIntake = () => false, syncResourceIntake = () => false;
    let resourceReceipt=null, pendingResourceIntake=null, intakeHash=null, intakeReviewVersion=0;
    let advancedWeights = null;
    const invalid = new Map();
    const controls = new Map();
    function node(tag, content, className) { const n = doc.createElement(tag); if (content !== undefined && content !== null) n.textContent = text(content); if (className) n.className = className; return n; }
    function clear(n) { n.textContent = ''; }
    function add(parent, ...children) { children.forEach(child => { if (child) parent.append(child); }); return parent; }
    function button(label, fn, className) { const b = node('button', label, className); b.type = 'button'; b.addEventListener('click', fn); return b; }
    function grid(className) { return node('div', undefined, 'grid' + (className ? ' ' + className : '')); }
    function small(value) { return node('small', value); }
    function status(id, message, error) { $(id).textContent = message; $(id).className = 'status ' + (error ? 'error' : 'success'); }
    function invalidate() {
      inputVersion++; dirty = true;
      if (report) { report = null; $('output-section').hidden = true; status('input-status','输入已修改，旧结果已收起。请重新比较。'); }
    }
    function updated() { invalidate(); if(!advancedDirty)$('input-editor').value=Engine.stringify(data,2); diagnose(); }
    function structuralChange(fn) { if(invalid.size){status('input-status','请先修正红框里的无效数字，再添加、移除或切换条目。',true);return;} fn(); invalidate(); render(); }
    function field(label, value, update, opts) {
      opts = opts || {};
      const wrap = node('label', undefined, 'field' + (opts.full ? ' full' : ''));
      const title = node('span', label); wrap.append(title);
      let input;
      if (opts.choices) {
        input = node('select'); opts.choices.forEach(([v,l]) => { const choice = node('option',l); choice.value = v; input.append(choice); }); input.value = text(value);
      } else { input = node(opts.multiline ? 'textarea' : 'input'); if (!opts.multiline) input.type = 'text'; input.value = text(value); }
      input.id = 'control-' + (++uid);
      if (opts.path) { input.setAttribute('data-path',opts.path); controls.set(opts.path,input); }
      if (opts.numeric) input.inputMode = 'decimal';
      if (opts.placeholder) input.placeholder = opts.placeholder;
      if (opts.disabled) input.disabled = true;
      if(!opts.choices)input.maxLength=opts.maxLength||(opts.numeric?100:opts.multiline?4000:1000);
      input.autocomplete = 'off';
      input.addEventListener(opts.choices ? 'change' : 'input', () => update(input.value, input));
      wrap.append(input); if (opts.help) wrap.append(small(opts.help));
      return wrap;
    }
    function textField(label, object, key, path, opts) { const optional=(opts&&opts.optional)||['notes','note','source','title'].includes(key); return field(label, object[key], value => { if(optional&&value.trim()==='')delete object[key];else put(object,key,value); updated(); }, Object.assign({path},opts)); }
    function numberField(label, object, key, path, opts) {
      opts = opts || {};
      return field(label, invalid.has(path) ? invalid.get(path) : numericText(object[key]), (value, input) => {
        invalid.delete(path); input.removeAttribute('aria-invalid');
        if (value.trim() === '') { if (opts.optional) delete object[key]; else put(object,key,null); }
        else { try { put(object,key,Engine.numeric(value.trim())); } catch (_) { put(object,key,null); invalid.set(path,value); input.setAttribute('aria-invalid','true'); } }
        updated();
      }, Object.assign({numeric:true,placeholder:opts.optional ? '不设置' : '未知请留空',path},opts));
    }
    function selectField(label, object, key, choices, path, opts) { return field(label, object[key], value => { put(object,key,value); updated(); },Object.assign({choices,path},opts)); }
    function check(label, checked, fn, path) { const wrap = node('label',undefined,'check'); const input = node('input'); input.type='checkbox'; input.checked=checked; input.setAttribute('aria-label',label); if (path) { input.setAttribute('data-path',path); controls.set(path,input); } input.addEventListener('change',()=>fn(input.checked)); add(wrap,input,node('span',label)); return wrap; }
    function subhead(parent,title,addLabel,fn,disabled) { const n = node('div',undefined,'subhead'); n.append(node('h3',title)); if(addLabel) { const b=button(addLabel,fn,'small'); b.disabled=!!disabled;n.append(b); } parent.append(n); }
    function ensureRoot(key) { if (!record(data[key])) put(data,key,{}); return data[key]; }
    function ensureMap(object,key) { if (!record(object[key])) put(object,key,{}); return object[key]; }
    function constraints() { return ensureRoot('constraints'); }
    function getSlots() { return [...new Set(data.options.map(o=>o.slot).filter(s=>typeof s==='string'&&s.trim()).concat(Object.keys(data.baseline.equipment||{})))].sort(); }
    function toggleList(object,key,value,checked) { const values=list(object[key]).filter(v=>v!==value); if(checked)values.push(value); put(object,key,values); updated(); }
    function chooseOptions(parent, object, key, path) { if(!data.options.length) parent.append(node('p','先添加装备候选','muted')); data.options.forEach(o=>parent.append(check(text(o.name)+' · '+text(o.slot)+' ['+o.id+']',list(object[key]).includes(o.id),on=>toggleList(object,key,o.id,on),path+'.'+o.id))); }
    function numericMap(keys,value) { const map=Object.create(null); keys.forEach(k=>put(map,k,value)); return map; }
    function objectiveMode() {return data.objective===undefined?(own(data,'weights')?'weighted':'pareto'):data.objective;}
    function renderCharacter() {
      const parent=$('character-fields');clear(parent);
      const mode=objectiveMode();
      parent.append(field('你想解决什么问题？',mode,value=>{
        structuralChange(()=>{if(record(data.weights))advancedWeights=data.weights;data.objective=value;if(value==='weighted')data.weights=advancedWeights||numericMap(data.metrics.map(m=>m.id),null);else delete data.weights;});
        if(controls.has('objective'))controls.get('objective').value=objectiveMode();
      },{path:'objective',choices:[['min_cost','达到目标后，尽量少花钱'],['pareto','还没定目标，先看各方案取舍（无需权重）'],['weighted','高级：我自己设置权重评分']]}));
      parent.append(node('p',mode==='min_cost'?'在下方“最终面板硬门槛”填写要达到的数值；会比较所有达标方案的总花费，无需权重。当前装备已达标时可以不买。':mode==='pareto'?'按价格和每项指标列出互有取舍的方案，不替你编权重，也不指定唯一最优。': '高级线性评分：数值单位会影响结果；每项权重由你填写，至少一项大于 0。','notice info'));
      if(mode!=='weighted'&&record(data.weights)){
        const extra=node('details');extra.append(node('summary','草稿带有未使用的高级主权重'));
        extra.append(node('p','当前目标不使用这些权重；已填写的权重仍会校验。移除后可继续无权重比较。','muted'));
        extra.append(button('移除主权重',()=>structuralChange(()=>{advancedWeights=data.weights;delete data.weights;}),'small'));
        parent.append(extra);
      }
      const main=grid();add(main,textField('这份比较的名称',data,'title','title',{full:true}),numberField('本次总预算',data,'budget','budget'),textField('统一价格单位',data,'currency','currency',{placeholder:'例如：万元游戏币 / 元'}));parent.append(main);
      const meta=node('details');meta.append(node('summary','角色备注（可选）'));
      const character=ensureRoot('character');const g=grid('four');
      add(g,numberField('等级',character,'level','character.level',{optional:true,help:'1–200，仅记录'}),textField('门派',character,'school','character.school',{optional:true}),textField('区服',character,'server','character.server',{optional:true}),textField('用途',character,'purpose','character.purpose',{placeholder:'如日常 / PK',optional:true}));
      meta.append(g);parent.append(meta);
      const base=node('div',undefined,'subhead');base.append(node('h3','当前面板基线'));parent.append(base);
      const b=grid();add(b,textField('基线名称',data.baseline,'label','baseline.label'),selectField('当前面板的依据',data.baseline,'evidence',evidenceChoices,'baseline.evidence'));
      if(data.baseline.evidence===undefined)controls.get('baseline.evidence').value='unverified';parent.append(b);
    }
    function renderMetrics() {
      const parent=$('metric-fields');clear(parent);
      data.metrics.forEach((m,index)=>{
        const card=node('div',undefined,'entry-card');const head=node('div',undefined,'entry-head');
        add(head,node('span','指标 '+(index+1)+' · '+m.id,'entry-number'),button('移除指标',()=>structuralChange(()=>{
          data.metrics.splice(index,1);if(data.weights)delete data.weights[m.id];if(advancedWeights)delete advancedWeights[m.id];delete data.baseline.stats[m.id];
          data.options.forEach(o=>{if(o.deltas)delete o.deltas[m.id];if(o.measured_stats)delete o.measured_stats[m.id];});
          list(data.weight_scenarios).forEach(s=>delete s.weights[m.id]);const c=data.constraints||{};if(c.min_stats)delete c.min_stats[m.id];if(c.max_stats)delete c.max_stats[m.id];
        }),'small danger'));card.append(head);
        const g=node('div',undefined,'metric-entry');
        add(g,textField('指标名称',m,'name','metrics.'+index+'.name'),textField('属性单位',m,'unit','metrics.'+index+'.unit'),selectField('比较方向',m,'direction',[['maximize','越高越好'],['minimize','越低越好']],'metrics.'+index+'.direction'));
        if(objectiveMode()==='weighted')g.append(numberField('高级：偏好权重',ensureRoot('weights'),m.id,'weights.'+m.id));
        card.append(g);const stats=grid();stats.style.marginTop='10px';add(stats,numberField('当前角色面板',data.baseline.stats,m.id,'baseline.stats.'+m.id),node('p','请在同一测试状态读取完整角色面板；只有明确不变的增量才能填写 0。','muted'));card.append(stats);parent.append(card);
      });
      if(!data.metrics.length)parent.append(node('p','请至少添加一个要比较的指标','empty'));
      $('add-metric').disabled=data.metrics.length>=12;
    }
    function renderCandidates() {
      const parent=$('candidate-fields');clear(parent);
      data.options.forEach((o,index)=>{
        const p='options.'+index;const card=node('article',undefined,'entry-card');const head=node('div',undefined,'entry-head');
        add(head,node('span','候选 '+String(index+1).padStart(2,'0')+' · '+o.id,'entry-number'),button('移除候选',()=>structuralChange(()=>{
          data.options.splice(index,1);const c=data.constraints||{};
          for(const k of ['required_options','excluded_options'])if(c[k])c[k]=c[k].filter(id=>id!==o.id);
          if(c.conflicts)c.conflicts=c.conflicts.filter(pair=>!list(pair).includes(o.id));
          list(data.manual_plans).forEach(plan=>plan.option_ids=plan.option_ids.filter(id=>id!==o.id));
        }),'small danger'));card.append(head);
        const g=grid();add(g,textField('装备名称',o,'name',p+'.name'));
        const commonSlot=slotChoices.some(([id])=>id===o.slot);
        g.append(field('装备部位',commonSlot?o.slot:(o.slot?'__custom':''),value=>structuralChange(()=>{o.slot=value==='__custom'?uniqueId(getSlots().map(id=>({id})),'slot-'):value;}),{path:p+'.slot',choices:[['','请选择部位'],...slotChoices,['__custom','自定义部位…']]}));
        if(o.slot&&!commonSlot)g.append(field('自定义部位标识',o.slot,value=>{o.slot=value;updated();},{path:p+'.custom_slot',help:'同一部位使用相同标识；小写字母开头，只含字母、数字、_、-'}));
        if(controls.has(p+'.custom_slot'))controls.get(p+'.custom_slot').addEventListener('change',()=>{renderConstraints();renderScenarios();diagnose();});
        controls.get(p+'.name').addEventListener('change',()=>{renderConstraints();renderScenarios();diagnose();});
        add(g,numberField('确认报价',o,'price',p+'.price',{disabled:!!o.owned,help:o.owned?'已有物品的新增报价为 0':'不减去旧装备预期售价'}),numberField('额外费用',o,'fees',p+'.fees',{placeholder:o.fees===undefined?'旧版未填：规则默认 0':'未知请留空',help:'镶嵌、转移等已计入属性的费用别重复计算'}));
        card.append(g);card.append(check('这是已有物品（报价设为 0，额外费用仍需确认）',!!o.owned,on=>structuralChange(()=>{o.owned=on;if(on)o.price=Engine.numeric('0');}),p+'.owned'));
        const mode=o.measured_stats!==undefined?'measured_stats':'deltas';
        card.append(field('属性录入方式',mode,value=>{
          if(value===mode)return; const old=o[mode]; const hasValues=entries(old).some(([,v])=>v!==null&&v!==undefined);
          if(hasValues&&!confirmAction('切换录入方式会清空这件候选的属性数值，避免把净变化误当作完整面板。继续吗？')){controls.get(p+'.mode').value=mode;return;}
          structuralChange(()=>{delete o.deltas;delete o.measured_stats;o[value]=numericMap(data.metrics.map(m=>m.id),null);});
        },{path:p+'.mode',choices:[['deltas','净变化：相对当前同部位装备'],['measured_stats','完整角色面板：仅换这一件后实测']]}));
        const mg=grid('three');mg.style.marginTop='11px';
        const map=ensureMap(o,mode);data.metrics.forEach(m=>mg.append(numberField(text(m.name)+(m.unit?'（'+m.unit+'）':'')+(mode==='deltas'?' · 净变化':' · 换后面板'),map,m.id,p+'.'+mode+'.'+m.id,{help:mode==='deltas'?'减少请填负数；不变需明确填 0': '仅换这一件，保持其他测试条件一致'})));card.append(mg);
        const details=node('details');details.append(node('summary','来源、证据与备注'));const eg=grid();
        add(eg,selectField('证据状态',o,'evidence',evidenceChoices,p+'.evidence'),textField('来源记录',o,'source',p+'.source',{placeholder:'手工报价日期 / 实测记录，不自动访问'}),textField('备注',o,'notes',p+'.notes',{full:true,multiline:true}));
        if(o.evidence===undefined)controls.get(p+'.evidence').value='unverified';details.append(eg);card.append(details);parent.append(card);
      });
      if(!data.options.length)parent.append(node('p','可以先计算零换装基线，也可以添加候选再比较','empty'));
      $('add-option').disabled=data.options.length>=64;
    }
    function renderConstraints() {
      const parent=$('constraint-fields');clear(parent);const c=constraints();
      subhead(parent,'当前装备与部位锁定');
      const slots=getSlots();const equipment=ensureMap(data.baseline,'equipment');
      if(!slots.length)parent.append(node('p','添加候选部位后，就能记录当前装备与锁定该部位','muted'));
      slots.forEach(slot=>{const row=node('div',undefined,'entry-card');const g=grid();
        const current=textField('当前 '+slot+' 装备',equipment,slot,'baseline.equipment.'+slot,{placeholder:'可选：填写当前装备名称',optional:true});g.append(current);
        g.append(check('锁定 '+slot+'：保留当前',list(c.locked_slots).includes(slot),on=>toggleList(c,'locked_slots',slot,on),'constraints.locked_slots.'+slot));row.append(g);parent.append(row);
      });
      const retained=list(c.locked_slots).filter(s=>!slots.includes(s));if(retained.length)parent.append(node('p','当前锁定列表还含：'+retained.join('、')+'。请在高级 JSON 修正，或补回该部位。','notice error'));
      subhead(parent,'最终面板硬门槛');const targets=grid();
      const min=ensureMap(c,'min_stats'),max=ensureMap(c,'max_stats');
      data.metrics.forEach(m=>{targets.append(numberField(text(m.name)+' · 最低值',min,m.id,'constraints.min_stats.'+m.id,{optional:true}));targets.append(numberField(text(m.name)+' · 最高值',max,m.id,'constraints.max_stats.'+m.id,{optional:true}));});parent.append(targets);
      const count=grid();count.style.marginTop='12px';count.append(numberField('最多替换几件',c,'max_changes','constraints.max_changes',{optional:true,help:'留空不限；填 0 则只允许保持当前'}));parent.append(count);
      const detail=node('details');detail.append(node('summary','必选、排除与候选互斥'));
      const groups=grid();const req=node('div'),exc=node('div');add(req,node('h3','必须选择'));chooseOptions(req,c,'required_options','constraints.required_options');add(exc,node('h3','排除候选'));chooseOptions(exc,c,'excluded_options','constraints.excluded_options');add(groups,req,exc);detail.append(groups);
      subhead(detail,'不能同时使用的候选组合','＋ 添加互斥',()=>structuralChange(()=>{if(!c.conflicts)c.conflicts=[];c.conflicts.push(['','']);}),list(c.conflicts).length>=128);
      const choices=[['','请选择候选'],...data.options.map(o=>[o.id,text(o.name)+' ['+o.id+']'])];
      list(c.conflicts).forEach((pair,i)=>{const row=node('div',undefined,'entry-card');const g=grid();const vals=list(pair);add(g,field('候选一',vals[0],value=>{if(!Array.isArray(c.conflicts[i]))c.conflicts[i]=['',''];c.conflicts[i][0]=value;updated();},{choices,path:'constraints.conflicts.'+i+'.0'}),field('候选二',vals[1],value=>{if(!Array.isArray(c.conflicts[i]))c.conflicts[i]=['',''];c.conflicts[i][1]=value;updated();},{choices,path:'constraints.conflicts.'+i+'.1'}));row.append(g);const remove=node('div',undefined,'remove-row');remove.append(button('删除这组互斥',()=>structuralChange(()=>c.conflicts.splice(i,1)),'small danger'));row.append(remove);detail.append(row);});parent.append(detail);
    }
    function renderScenarios() {
      const parent=$('scenario-fields');clear(parent);
      function arrayFor(key) { if(!data[key])data[key]=[];return data[key]; }
      subhead(parent,'不同预算下的方案比较','＋ 预算试算',()=>structuralChange(()=>arrayFor('budget_scenarios').push({label:'预算场景 '+(list(data.budget_scenarios).length+1),budget:null})),list(data.budget_scenarios).length>=8);
      if(!list(data.budget_scenarios).length)parent.append(node('p','例如在预算减少或增加时，比较方案会不会改变。最多 8 组。','muted'));
      list(data.budget_scenarios).forEach((s,i)=>{const card=node('div',undefined,'entry-card');const g=grid();add(g,textField('场景名称',s,'label','budget_scenarios.'+i+'.label'),numberField('该场景预算',s,'budget','budget_scenarios.'+i+'.budget'));card.append(g);const row=node('div',undefined,'remove-row');row.append(button('移除预算场景',()=>structuralChange(()=>data.budget_scenarios.splice(i,1)),'small danger'));card.append(row);parent.append(card);});
      const wd=node('details');wd.append(node('summary','高级（可选）：不同偏好权重下的方案'));subhead(wd,'权重试算','＋ 权重试算',()=>structuralChange(()=>arrayFor('weight_scenarios').push({label:'权重场景 '+(list(data.weight_scenarios).length+1),weights:numericMap(data.metrics.map(m=>m.id),null)})),list(data.weight_scenarios).length>=8);
      list(data.weight_scenarios).forEach((s,i)=>{const card=node('div',undefined,'entry-card');card.append(textField('场景名称',s,'label','weight_scenarios.'+i+'.label'));const g=grid('three');data.metrics.forEach(m=>g.append(numberField(text(m.name)+' 权重',s.weights,m.id,'weight_scenarios.'+i+'.weights.'+m.id)));card.append(g);const row=node('div',undefined,'remove-row');row.append(button('移除权重场景',()=>structuralChange(()=>data.weight_scenarios.splice(i,1)),'small danger'));card.append(row);wd.append(card);});parent.append(wd);
      subhead(parent,'手动 A / B 对照','＋ 手动方案',()=>structuralChange(()=>arrayFor('manual_plans').push({label:list(data.manual_plans).length?'方案 B':'方案 A',option_ids:[]})),list(data.manual_plans).length>=2);
      if(!list(data.manual_plans).length)parent.append(node('p','挑选你心中的方案，与当前装备和系统排序并排看。最多 2 组；不勾选表示零换装。','muted'));
      list(data.manual_plans).forEach((s,i)=>{const card=node('div',undefined,'entry-card');card.append(textField('方案名称',s,'label','manual_plans.'+i+'.label'));chooseOptions(card,s,'option_ids','manual_plans.'+i+'.option_ids');const row=node('div',undefined,'remove-row');row.append(button('移除手动方案',()=>structuralChange(()=>data.manual_plans.splice(i,1)),'small danger'));card.append(row);parent.append(card);});
    }
    function renderChecklist() {
      const parent=$('checklist-fields');clear(parent);
      subhead(parent,'自己的核对记录','＋ 添加检查项',()=>structuralChange(()=>{if(!data.checklist)data.checklist=[];data.checklist.push({item:'',status:'unverified'});}),list(data.checklist).length>=20);
      if(!list(data.checklist).length)parent.append(node('p','建议确认：报价时效、完整费用、同一测试状态、装备资格、套装或阈值联动。未录入的机制不会参与计算。','notice info'));
      list(data.checklist).forEach((s,i)=>{const card=node('div',undefined,'entry-card');const g=grid();add(g,textField('要确认的事项',s,'item','checklist.'+i+'.item'),selectField('你的核对状态',s,'status',[['unverified','尚未确认'],['confirmed','已确认（本人声明）'],['not_applicable','不适用']],'checklist.'+i+'.status'),textField('核对备注',s,'note','checklist.'+i+'.note',{full:true}));card.append(g);const row=node('div',undefined,'remove-row');row.append(button('移除检查项',()=>structuralChange(()=>data.checklist.splice(i,1)),'small danger'));card.append(row);parent.append(card);});
      const notes=grid();notes.style.marginTop='15px';add(notes,textField('整份比较的备注',data,'notes','notes',{multiline:true,full:true}),numberField('报告最多展示多少个备选',data,'top_n','top_n',{optional:true,help:'留空采用引擎默认上限'}));parent.append(notes);
    }
    function renderResources() {
      if(!Resources){$('cultivation-result').textContent='资源模块未加载，请核对 resources.js 是否与页面在同一目录。';$('calculate-cultivation').disabled=true;$('calculate-gems').disabled=true;$('save-resources').disabled=true;return;}
      function resourceChange(kind,key,value) {resourceState[kind][key]=value;resourceDirty=true;resourceVersion++;resourceResults[kind]=null;showResourceReceipt();clear($(kind==='gems'?'gem-result':'cultivation-result'));status('resource-status','输入已变化，请重新计算相应资源试算。');}
      const cf=grid();
      cf.append(field('修炼类型',resourceState.cultivation.type,v=>resourceChange('cultivation','type',v),{path:'resource.cultivation.type',choices:[['','请确认修炼类型'],...Resources.cultivationTypes.map(t=>[t.id,t.name])]}));
      for(const [key,label,help] of [['currentLevel','当前修炼等级','填写游戏内当前等级'],['targetLevel','目标修炼等级','必须不超过你已确认的上限'],['confirmedCap','已确认的修炼上限','请在游戏内确认，不按角色等级猜测'],['currentProgressXp','本级已有修炼经验','未知请留空，确认没有才填 0']])cf.append(field(label,resourceState.cultivation[key],v=>resourceChange('cultivation',key,v),{path:'resource.cultivation.'+key,numeric:true,placeholder:'请明确填写整数',help}));
      $('cultivation-fields').append(cf);
      const gf=grid();gf.append(field('普通宝石类型',resourceState.gems.gemType,v=>{if(v!==resourceState.gems.gemType&&Object.keys(resourceState.gems.quotes).length){if(!confirmAction('切换宝石种类会清空旧种类的所有逐级报价，不能将它们作为新种类价格。建议先保存草稿。确定切换吗？')){controls.get('resource.gems.gemType').value=resourceState.gems.gemType;return;}resourceState.gems.quotes={};}resourceChange('gems','gemType',v);renderQuotes();},{path:'resource.gems.gemType',choices:Resources.gemTypes.map(t=>[t.id,t.name])}));
      for(const [key,label] of [['currentForge','当前锻炼等级'],['targetForge','目标锻炼等级']])gf.append(field(label,resourceState.gems[key],v=>{resourceChange('gems',key,v);renderQuotes();},{path:'resource.gems.'+key,numeric:true,placeholder:'0–20，需人工核对装备上限'}));$('gem-fields').append(gf);
      function renderQuotes() {
        const parent=$('gem-quote-fields');clear(parent);const g=resourceState.gems;
        if(!/^\d{1,2}$/.test(g.currentForge)||!/^\d{1,2}$/.test(g.targetForge)){parent.append(node('p','填写当前与目标锻炼等级后，可录入每个新增等级的宝石报价。','muted'));return;}
        const start=BigInt(g.currentForge),end=BigInt(g.targetForge);if(end<start||end>20n){parent.append(node('p','目标等级必须不低于当前，且不超过 20。','muted'));return;}
        parent.append(node('p','逐级成品宝石报价 · 单位：游戏币两（整数）','muted'));const fields=grid();
        for(let grade=start+1n;grade<=end;grade++){const key=String(grade);fields.append(field(key+' 级宝石报价',g.quotes[key]||'',v=>{if(v.trim()==='')delete g.quotes[key];else put(g.quotes,key,v);resourceDirty=true;resourceVersion++;resourceResults.gems=null;clear($('gem-result'));},{path:'resource.gems.quotes.'+key,numeric:true,placeholder:'未知留空，不计作 0'}));}parent.append(fields);
      }
      renderQuotes();
      function describe(parent,result) {
        const notes=node('ul',undefined,'diagnostics');list(result.explanations).forEach(message=>notes.append(node('li',message)));parent.append(notes);
        list(result.citations).forEach(citation=>{if(!/^https:\/\/xyq\.163\.com\//.test(citation.url))return;const p=node('p',undefined,'muted');const a=node('a',citation.title+'（联网查看）');a.href=citation.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);p.append(node('span',' · 核对日期 '+citation.checkedDate));parent.append(p);});
      }
      function resultLines(parent,lines) {const table=node('table',undefined,'metrics-table');const body=node('tbody');lines.forEach(([label,value])=>{const tr=node('tr');add(tr,node('td',label),node('td',value));body.append(tr);});table.append(body);const wrap=node('div',undefined,'table-wrap');wrap.append(table);parent.append(wrap);}
      $('calculate-cultivation').addEventListener('click',()=>{
        const parent=$('cultivation-result');clear(parent);try{
          const input=resourceState.cultivation;for(const [k,v] of Object.entries(input))if(v.trim()==='')throw new Error('请填写所有修炼数值；没有本级经验时需明确填写 0。');
          const r=Resources.cultivation(input);resourceResults.cultivation=r;
          parent.append(node('p',r.typeLabel+'：'+r.currentLevel+' → '+r.targetLevel,'notice info'));
          resultLines(parent,[['还需修炼经验',r.requiredXp],['普通修炼次数',r.purchases],['游戏币消耗（两）',r.costLiang],['帮派资材消耗',r.materialsConsumed],['帮贡消耗',r.contributionConsumed],['角色等级至少',r.requiredCharacterLevel],['累计帮贡必须大于',r.requiredContributionExclusive],['入帮天数必须大于',r.requiredGuildMembershipDaysExclusive],['本次购买经验算术余量',r.surplusXp]]);describe(parent,r);status('resource-status','普通修炼试算完成；帮贡与入帮天数是严格大于门槛，还需人工核对帮派开放状态。');
        }catch(error){resourceResults.cultivation=null;parent.append(node('p',error.message,'notice error'));}
      });
      $('calculate-gems').addEventListener('click',()=>{
        const parent=$('gem-result');clear(parent);try{
          const input=resourceState.gems;if(!input.currentForge.trim()||!input.targetForge.trim())throw new Error('请明确填写当前与目标锻炼等级。');
          const r=Resources.gems(input);resourceResults.gems=r;
          parent.append(node('p',r.gemName+'：'+r.currentForge+' → '+r.targetForge,'notice info'));
          if(r.quoteTotalLiang===null)parent.append(node('p','缺少 '+r.missingQuoteGrades.join('、')+' 级宝石报价，总花费未知。已知小计不能当作预算总额。','notice'));
          resultLines(parent,[['逐级成品报价合计（两）',r.quoteTotalLiang===null?'未知，报价不完整':r.quoteTotalLiang],['已知报价小计（两）',r.knownQuoteSubtotalLiang],['本次全部锻炼的一级材料下限',r.baseUnitsLowerBound],['目标等级单颗的一级材料下限',r.targetStoneBaseUnitsLowerBound],['新增原始装备属性',r.rawStatDelta.label+' +'+r.rawStatDelta.value],['公开规则所列部位',r.allowedSlots.join('、')]]);
          parent.append(node('p','原始属性不能直接当作角色面板增量；没有自动加入上方候选装备。','notice info'));describe(parent,r);status('resource-status','宝石试算完成。材料数是下限，不含失败损耗；购买前还需人工核对装备资格与全部费用。');
        }catch(error){resourceResults.gems=null;parent.append(node('p',error.message,'notice error'));}
      });
      $('save-resources').addEventListener('click',()=>{try{download(Engine.stringify({schema:RESOURCE_SCHEMA,title:'独立资源试算：不是配装优化输入',question_receipt:resourceReceipt,inputs:resourceState,results:resourceResults,notice:'未算出的结果为 null；未填宝石报价仍未知。公开规则与人工资格检查见结果说明。'},2),'mhxy-resource-trials.json','application/json;charset=utf-8');resourceDirty=false;status('resource-status','已生成独立资源试算下载，包含输入与最近一次有效结果。');}catch(error){status('resource-status','资源试算未生成：'+error.message,true);}});
      loadResources=(raw,filename,skipConfirm)=>{
        try {
          const parsed=typeof raw==='string'?Engine.parse(raw):raw,next=resourceDraft(parsed),nextReceipt=parsed.question_receipt?Intake.validate(parsed.question_receipt):null;
          if(!skipConfirm&&resourceDirty&&!confirmAction('当前未保存的资源试算会被替换，确定打开新草稿吗？'))return false;
          resourceState.cultivation=next.cultivation;resourceState.gems=next.gems;resourceReceipt=nextReceipt;
          for(const kind of ['cultivation','gems'])for(const [key,v] of Object.entries(resourceState[kind]))if(key!=='quotes')controls.get('resource.'+kind+'.'+key).value=v;
          renderQuotes();resourceResults.cultivation=null;resourceResults.gems=null;resourceDirty=false;resourceVersion++;showResourceReceipt();
          clear($('cultivation-result'));clear($('gem-result'));
          status('resource-status','已打开 '+filename+'；保留原输入，旧结果缓存已丢弃，请重新计算。');return true;
        }catch(error){status('resource-status','没有替换资源草稿：'+error.message,true);return false;}
      };
      $('resource-file').addEventListener('change',event=>{
        const generation=++resourceGeneration,file=event.target.files&&event.target.files[0];event.target.value='';$('cancel-resource-import').hidden=true;if(!file)return;
        if(file.size>1000000){status('resource-status','资源草稿超过1 MB，未读取。',true);return;}
        const version=resourceVersion,reader=new env.FileReader();$('cancel-resource-import').hidden=false;
        reader.onload=()=>{if(generation!==resourceGeneration)return;$('cancel-resource-import').hidden=true;if(version!==resourceVersion){status('resource-status','读取期间资源输入已变化，未覆盖；请重新选择文件。',true);return;}loadResources(String(reader.result),file.name);};
        reader.onerror=()=>{if(generation===resourceGeneration){$('cancel-resource-import').hidden=true;status('resource-status','读取失败，没有替换资源草稿。',true);}};reader.readAsText(file,'UTF-8');
      });
      $('cancel-resource-import').addEventListener('click',()=>{resourceGeneration++;$('cancel-resource-import').hidden=true;status('resource-status','已取消资源读取，当前输入与结果保持不变。');});
      $('resource-text').addEventListener('click',()=>{
        const lines=['独立资源试算说明','仅适用电脑版时间服；人工填写，未联网核价。','资源草稿可重新打开；此说明是静态报告。',...receiptLines()];
        for(const [kind,label] of [['cultivation','普通修炼'],['gems','普通宝石']]){
          lines.push('\n'+label);const result=resourceResults[kind];
          if(!result){lines.push('当前输入尚无有效结果，请补齐或重新计算。');continue;}
          if(kind==='cultivation')lines.push(result.typeLabel+' '+result.currentLevel+' → '+result.targetLevel,'经验：'+result.requiredXp,'普通购买次数：'+result.purchases,'游戏币两：'+result.costLiang,'消耗资材：'+result.materialsConsumed,'帮贡消耗：'+result.contributionConsumed,'角色等级至少：'+result.requiredCharacterLevel,'累计帮贡必须大于：'+result.requiredContributionExclusive,'入帮天数必须大于：'+result.requiredGuildMembershipDaysExclusive);
          else lines.push(result.gemName+' '+result.currentForge+' → '+result.targetForge,'全部新增段数材料下限：'+result.baseUnitsLowerBound,'目标单颗材料下限：'+result.targetStoneBaseUnitsLowerBound,'报价总额：'+(result.quoteTotalLiang===null?'未知，缺报价等级 '+result.missingQuoteGrades.join('、'):result.quoteTotalLiang),'已知小计：'+result.knownQuoteSubtotalLiang,'原始装备属性（不是人物面板）：'+result.rawStatDelta.label+' +'+result.rawStatDelta.value);
          if(kind==='gems'){for(const step of result.steps)lines.push(step.grade+'级：需1颗同级宝石；手填单价 '+(step.quoteLiang===null?'未知':step.quoteLiang+'两')+'；该单颗一级材料下限 '+step.baseUnitsLowerBound);lines.push('普通资源报价没有结构化区服/日期/来源，不是已核价采购建议；需要采购决定请使用完整宝石计划。');}
          else lines.push('本级已有经验：'+resourceState.cultivation.currentProgressXp+'；已确认上限：'+resourceState.cultivation.confirmedCap);
          list(result.explanations).forEach(x=>lines.push(x));list(result.citations).forEach(x=>lines.push(x.title+' '+x.url+' 核对日 '+x.checkedDate));
        }
        try{download(lines.join('\n')+'\n','mhxy-resource-report.txt','text/plain;charset=utf-8');status('resource-status','已生成资源说明；实际文件请核对下载目录。');}catch(error){status('resource-status','资源说明未生成：'+error.message,true);}
      });
      function receiptLines(){if(!resourceReceipt)return[];return['普通修炼问题出处（历史条件，用户已选择应用，未独立验证）：',...resourceReceipt.fields.map(f=>f.label+'：'+f.value+'；原话短语“'+f.source.text+'”；原文位置'+f.source.start+'–'+f.source.end+'；'+(f.scope==='hypothetical'?'假设条件':'原话所述条件')+'；'+(resourceState.cultivation[f.key]===f.value?'当前未改':'当前已改为 '+(resourceState.cultivation[f.key]||'未知')))];}
      function showResourceReceipt(){const host=$('resource-question-receipt');clear(host);for(const line of receiptLines())host.append(node('p',line));}
      syncResourceIntake=()=>{
        const hash=env.location?env.location.hash:'';if(hash===intakeHash)return false;intakeHash=hash;pendingResourceIntake=null;const host=$('resource-question-review');clear(host);host.hidden=true;
        if(!Intake)return false;try{const payload=Intake.fromHash(hash);if(!payload)return false;if(payload.route!=='resources')throw new Error('这份问题交接属于另一个工具，请返回对应页面');pendingResourceIntake=payload;intakeReviewVersion=resourceVersion;host.hidden=false;host.append(node('h3','先核对问题中的普通修炼字段'));
          for(const f of payload.fields)host.append(node('p',f.label+'：'+f.value+'；原话“'+f.source.text+'”（位置'+f.source.start+'–'+f.source.end+'，'+(f.scope==='hypothetical'?'假设':'原话所述')+'）'));
          host.append(node('p','仅应用列出的条件；缺项保持空白，不当作0。只有你点击应用才替换普通修炼输入，宝石和装备数据不变。本地链接含必要短语，可能保留在浏览历史或复制的链接中；不要分享含私密信息的链接。','notice'));
          host.append(button('已核对，应用到普通修炼',()=>applyResourceIntake()));host.append(button('取消问题交接',()=>{pendingResourceIntake=null;clear(host);host.hidden=true;status('resource-status','已取消问题交接，当前表单与结果保持不变。');}));return true;
        }catch(error){host.hidden=false;host.append(node('p','问题交接未应用：'+error.message,'notice error'));return false;}
      };
      applyResourceIntake=()=>{
        if(!pendingResourceIntake)return false;const receipt=Intake.validate(pendingResourceIntake),hash=intakeHash,revision=resourceVersion;
        if(env.location&&env.location.hash!==hash){syncResourceIntake();return false;}
        const old=resourceState.cultivation,hasWork=resourceDirty||resourceReceipt||old.type!=='attack'||['currentLevel','targetLevel','currentProgressXp','confirmedCap'].some(k=>old[k]!=='');
        if(hasWork&&!confirmAction('将替换现有普通修炼输入（包括已保存的内容），未应用的字段变为空白；请先保存需要保留的数据。宝石和装备输入不变。确定应用这些问题条件吗？'))return false;
        if(resourceVersion!==revision||(env.location&&env.location.hash!==hash)||!pendingResourceIntake){status('resource-status','确认期间数据或问题交接已变化，未覆盖；请重新核对。',true);return false;}
        const next={type:'',currentLevel:'',targetLevel:'',currentProgressXp:'',confirmedCap:''};for(const f of receipt.fields)next[f.key]=f.value;
        resourceState.cultivation=next;resourceReceipt=receipt;resourceResults.cultivation=null;resourceDirty=true;resourceVersion++;resourceGeneration++;$('cancel-resource-import').hidden=true;pendingResourceIntake=null;
        for(const[k,v]of Object.entries(next))controls.get('resource.cultivation.'+k).value=v;clear($('cultivation-result'));clear($('resource-question-review'));$('resource-question-review').hidden=true;showResourceReceipt();status('resource-status','已应用问题条件；缺项仍为空白，请核对后计算并保存新资源草稿。');return true;
      };
      showResourceReceipt();syncResourceIntake();if(typeof env.addEventListener==='function')env.addEventListener('hashchange',syncResourceIntake);
    }
    function sourceInfo() { $('source-label').textContent=source; $('source-description').textContent=source==='纯合成演示'?'价格、角色和属性仅用于学习，不代表真实市价或实测':'仅在当前页面内编辑；未核实数值请留空，关闭前保存本地草稿'; }
    function render() { const resourceControls=[...controls].filter(([key])=>key.startsWith('resource.'));controls.clear();resourceControls.forEach(([key,value])=>controls.set(key,value));renderCharacter();renderMetrics();renderCandidates();renderConstraints();renderScenarios();renderChecklist();sourceInfo();if(!advancedDirty)$('input-editor').value=Engine.stringify(data,2);diagnose(); }
    function diagnose() {
      let result;
      try {result=Engine.diagnose(data);}catch(error){result={ready:false,issues:[{path:'输入',message:error.message}]};}
      const issues=[...invalid.entries()].map(([path])=>({path,message:'不是可识别的十进制数字，请修正或留空'})).concat(result.issues||[]);
      if(advancedDirty)issues.unshift({path:'高级 JSON',message:'存在尚未应用的修改。请应用 JSON 或用当前表单刷新'});
      for(const input of controls.values())input.removeAttribute('aria-invalid');
      issues.forEach(issue=>{const input=controls.get(text(issue.path).replace(/\[(\d+)\]/g,'.$1'));if(input)input.setAttribute('aria-invalid','true');});
      const ready=!!result.ready&&!invalid.size&&!advancedDirty;
      $('readiness').textContent=ready?'可以开始比较':'还差一点数据';$('readiness-note').textContent=ready?'结构与数值检查通过，证据仍需你确认':'请处理下方提示；未知数据不会按 0 计算';
      $('calculate-button').disabled=!ready;$('calculate-bottom').disabled=!ready;
      clear($('issue-list'));issues.slice(0,24).forEach(issue=>$('issue-list').append(node('li',text(issue.path)+'：'+text(issue.message))));if(issues.length>24)$('issue-list').append(node('li','另有 '+(issues.length-24)+' 项问题，补齐后会继续显示'));
      clear($('input-summary'));for(const [v,l] of [[data.metrics.length,'比较指标'],[data.options.length,'装备候选'],[getSlots().length,'装备部位'],[list(data.manual_plans).length,'手动方案']]){const s=node('div',undefined,'rail-stat');add(s,node('b',v),node('span',l));$('input-summary').append(s);}
      return {ready,issues};
    }
    function confirmAction(message) { return typeof env.confirm==='function'?env.confirm(message):false; }
    function mayReplace() { return !dirty||confirmAction('当前未保存的修改会被替换。建议先保存草稿。确定继续吗？'); }
    function loadInput(raw, filename, skipConfirm) {
      let previous=null;
      try { const parsed=editableShape(Engine.parse(raw));if(!skipConfirm&&!mayReplace())return false;
        previous={data,advancedWeights,report,reportSource,source,dirty,advancedDirty,inputVersion,fileGeneration,resultGeneration,invalid:new Map(invalid),editor:$('input-editor').value};
        data=parsed;advancedWeights=null;invalid.clear();report=null;reportSource=null;fileGeneration++;resultGeneration++;source=filename||'本地草稿';dirty=false;advancedDirty=false;inputVersion++;$('output-section').hidden=true;render();status('file-status','已打开 '+source+'。文件只在本地读取。');status('input-status','');status('json-status','');return true;
      }catch(error){
        if(previous){data=previous.data;advancedWeights=previous.advancedWeights;report=previous.report;reportSource=previous.reportSource;source=previous.source;dirty=previous.dirty;advancedDirty=previous.advancedDirty;inputVersion=previous.inputVersion;fileGeneration=previous.fileGeneration;resultGeneration=previous.resultGeneration;invalid.clear();previous.invalid.forEach((v,k)=>invalid.set(k,v));try{render();$('input-editor').value=previous.editor;if(report)renderReport();else $('output-section').hidden=true;}catch(_){status('input-status','页面显示恢复失败；原草稿数据仍保留，请保存草稿后重新打开。',true);}}
        status('file-status','没有替换当前草稿：'+error.message,true);return false;
      }
    }
    function loadReport(raw, filename) {
      const previous=report,previousSource=reportSource;
      try{const next=validateReport(Engine.parse(raw,16000000));report=next;reportSource=filename||'导入结果';renderReport();resultGeneration++;status('report-import-status','已载入 '+reportSource+'。与当前表单独立，未重新计算或核实来源。');if(typeof $('output-section').focus==='function')$('output-section').focus();return true;
      }catch(error){report=previous;reportSource=previousSource;try{if(report)renderReport();else $('output-section').hidden=true;}catch(_){}status('report-import-status','报告未载入，当前结果保持不变：'+error.message,true);return false;}
    }
    function comboCard(combo,label,featured,currency) {
      if(!combo){const card=node('div',undefined,'combo infeasible');add(card,node('h3',label),node('p','没有满足预算与全部约束的方案','notice error'),node('p','先检查目标门槛、必选 / 排除条件和预算。不要把未达标的高分方案当成建议。','muted'));return card;}
      const card=node('article',undefined,'combo'+(featured?' featured':'')+(combo.feasible===false?' infeasible':''));const head=node('div',undefined,'combo-label');
      add(head,node('h3',label),node('span',combo.feasible===undefined?'报告未提供可行性标记':combo.feasible===false?'未满足约束':reportSource?'报告标记为可行':'满足当前约束','tag '+(combo.feasible===false?'bad':combo.feasible===undefined?'warn':'good')));card.append(head);
      const amount=node('div',combo.price,'amount');amount.append(small(currency||report.currency));card.append(amount);
      card.append(node('p',(combo.score===null?'未使用权重评分':'偏好分 '+combo.score)+' · 剩余预算 '+combo.remaining_budget,'combo-sub'));
      const selection=node('ul',undefined,'selections');
      if(!list(combo.selection).length)selection.append(node('li','保留当前全部装备 · 不替换、不花费'));
      list(combo.selection).forEach(o=>{const li=node('li');li.append(node('strong',text(o.name)+' · '+text(o.slot)));li.append(small('替换：'+(o.replaces||'当前同部位装备')+' · '+(o.owned?'已有物品':'购入候选')+' · '+(evidenceLabels[o.evidence]||'尚未核实')));if(o.total_cost!==undefined)li.append(small('报价 '+o.quoted_price+' + 费用 '+o.fees+' = '+o.total_cost+' '+(currency||report.currency)));if(o.source)li.append(small('来源记录：'+o.source));if(o.notes)li.append(small('用户备注（未作为约束计算）：'+o.notes));selection.append(li);});card.append(selection);
      const table=node('table',undefined,'metrics-table');const thead=node('thead'),tr=node('tr');['指标','当前','净变化','最终'].forEach(s=>tr.append(node('th',s)));thead.append(tr);table.append(thead);const tbody=node('tbody');
      list(report.metrics).forEach(m=>{const row=node('tr');row.append(node('td',m.name+(m.unit?' / '+m.unit:'')));row.append(node('td',report.baseline&&report.baseline.final_stats?report.baseline.final_stats[m.id]:'—'));const delta=text(combo.deltas&&combo.deltas[m.id]);const worsens=list(combo.drawbacks).includes(m.id);row.append(node('td',delta,worsens?'negative':''));row.append(node('td',combo.final_stats&&combo.final_stats[m.id]));tbody.append(row);});table.append(tbody);const wrap=node('div',undefined,'table-wrap');wrap.append(table);card.append(wrap);
      if(list(combo.drawbacks).length){const labels=list(combo.drawbacks).map(id=>{const m=list(report.metrics).find(v=>v.id===id);return m?m.name:id;});card.append(node('p','需要接受的取舍：'+labels.join('、')+' 向你不偏好的方向变化','drawback'));}
      if(list(combo.violations).length){const ul=node('ul',undefined,'violations');combo.violations.forEach(v=>ul.append(node('li',v)));card.append(ul);}
      if(combo.is_baseline)card.append(node('p','零换装参照始终保留，即使未达门槛或不在帕累托前沿','muted'));return card;
    }
    function renderReport() {
      $('output-section').hidden=false;clear($('report-meta'));
      const summary=report.summary||{};
      for(const [value,label] of [[report.budget,'本次预算 · '+report.currency],[summary.feasible_count,'满足全部约束的组合'],[summary.combinations_evaluated,'已枚举组合'],[summary.pareto_total,'帕累托取舍组合']]){const s=node('div',undefined,'result-stat');add(s,node('strong',value===undefined?'—':value),node('span',label));$('report-meta').append(s);}
      clear($('report-notice'));$('report-notice').append(node('div','本次目标：'+(report.objective_description||'高级：按自定义权重比较')+'。'+(report.ranking_rule||''),'notice info'));if(report.notes)$('report-notice').append(node('div','用户备注（未作为约束计算）：'+report.notes,'notice info'));if(reportSource)$('report-notice').append(node('div','外部报告：'+reportSource+'。与上方输入独立；仅展示报告声明，未重新计算、核价或核实可行性。','notice'));const hasSynthetic=report.evidence_summary&&(report.evidence_summary.synthetic_options>0||report.evidence_summary.baseline_evidence==='synthetic');
      if(hasSynthetic)$('report-notice').append(node('div','本报告包含合成演示数据，不能用于真实购买决策。','notice'));
      if(report.status==='no_feasible_plan')$('report-notice').append(node('div','当前条件下没有可行方案。零换装基线仅作参照，不表示它已经达到你的目标。','notice error'));
      clear($('primary-results'));$('primary-results').append(comboCard(report.baseline,'零换装 · 当前参照',false));if(report.objective!=='pareto')$('primary-results').append(comboCard(report.best,report.objective==='min_cost'?'满足全部条件的最低花费方案':'按当前偏好排序的第一名',true));else $('primary-results').append(node('div','不指定唯一最优方案。下方展开显示 '+summary.pareto_shown+' / '+summary.pareto_total+' 个 Pareto 取舍；请按最终面板、花费和需要接受的退步来选。','notice info'));
      clear($('diagnostic-results'));const body=node('div',undefined,'panel-body');const ul=node('ul',undefined,'diagnostics');list(report.diagnostics).forEach(d=>ul.append(node('li',typeof d==='string'?d:d.message)));body.append(ul);
      const ev=report.evidence_summary||{};body.append(node('p','候选证据：已确认 '+(ev.confirmed_options||0)+' · 未核实 '+(ev.unverified_options||0)+' · 合成 '+(ev.synthetic_options||0)+'；当前面板：'+(evidenceLabels[ev.baseline_evidence]||'尚未核实'),'muted'));if(ev.notice)body.append(node('p',ev.notice,'muted'));
      const checks=list(report.checklist);if(checks.length){body.append(node('h3','核对记录（用户声明）'));checks.forEach(c=>body.append(node('p',(c.status==='confirmed'?'已确认':c.status==='not_applicable'?'不适用':'尚未确认')+' · '+c.item+(c.note?'：'+c.note:''),'muted')));}
      list(report.disclaimer).forEach(d=>body.append(node('p',d,'muted')));$('diagnostic-results').append(body);
      clear($('manual-results'));$('manual-section').hidden=!list(report.manual_plans).length;list(report.manual_plans).forEach(s=>$('manual-results').append(comboCard(s.plan,s.label,false)));
      clear($('scenario-results'));
      for(const [key,title,isBudget] of [['budget_scenarios','预算变化后的选择',true],['weight_scenarios','偏好权重变化后的选择',false]]){
        if(!list(report[key]).length)continue;$('scenario-results').append(node('h3',title));const cards=node('div',undefined,'result-grid');
        report[key].forEach(s=>{
          if(s.objective==='pareto'&&s.feasible_count){const section=node('details');section.append(node('summary',s.label+' · 预算 '+s.budget+' '+report.currency+' · 可行 '+s.feasible_count+' 组'));section.append(node('p','不指定唯一最优；展示 '+s.pareto_shown+' / '+s.pareto_total+' 个 Pareto 取舍'+(s.pareto_truncated?'（已截断）':''),'muted'));list(s.pareto).forEach((plan,i)=>section.append(comboCard(plan,'取舍 '+(i+1),false)));cards.append(section);return;}
          const card=comboCard(s.best,s.label,false);card.append(node('p',(isBudget?'场景预算 '+s.budget+' '+report.currency:'高级权重 '+entries(s.weights).map(([id,w])=>{const m=report.metrics.find(v=>v.id===id);return (m?m.name:id)+' '+w;}).join(' / '))+' · 可行 '+s.feasible_count+' 组','muted'));cards.append(card);
        });$('scenario-results').append(cards);
      }
      clear($('alternatives-results'));list(report.alternatives).forEach((c,i)=>$('alternatives-results').append(comboCard(c,'备选 '+(i+1),false)));
      $('pareto-details').open=report.objective==='pareto';$('alternatives-details').hidden=report.objective==='pareto';
      clear($('pareto-results'));if(summary.pareto_truncated)$('pareto-results').append(node('p','前沿展示已截断：显示 '+summary.pareto_shown+' / '+summary.pareto_total+' 个等价向量。','notice'));list(report.pareto).forEach((c,i)=>$('pareto-results').append(comboCard(c,'取舍 '+(i+1),false)));
      $('report-raw').textContent=Engine.stringify(report,2);status('download-status','');
    }
    function calculate() {
      const result=diagnose();if(!result.ready){status('input-status','请先补齐或修正输入，再比较方案。',true);return null;}
      try{report=Engine.calculate(data);reportSource=null;resultGeneration++;renderReport();status('input-status',report.status==='no_feasible_plan'?'计算完成，当前没有可行方案。请查看目标与约束诊断。':'计算完成，结果已在页面下方展开。');if(typeof $('output-section').focus==='function')$('output-section').focus();if(typeof $('output-section').scrollIntoView==='function')$('output-section').scrollIntoView({behavior:'smooth',block:'start'});return report;}catch(error){report=null;$('output-section').hidden=true;status('input-status','计算未完成：'+error.message,true);return null;}
    }
    function download(content, filename, mime) {
      const blob=new env.Blob([content],{type:mime});const url=env.URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=filename;doc.body.append(a);a.click();a.remove();env.setTimeout(()=>env.URL.revokeObjectURL(url),1000);return content;
    }
    function saveDraft() {
      if(invalid.size||advancedDirty){status('file-status','请先修正无效数字或应用高级 JSON，再保存；未知的空白值可以直接保存。',true);return false;}
      try{let raw=Engine.stringify(data,2);try{Engine.parse(raw);}catch(_){raw=Engine.stringify(data,0);Engine.parse(raw);}download(raw,'mhxy-input-draft.json','application/json;charset=utf-8');dirty=false;status('file-status','已生成本地草稿下载。空白值保留为 null；请在浏览器下载目录核对文件。');return raw;}catch(error){status('file-status','草稿未生成：'+error.message,true);return false;}
    }
    function exportReport(format) {
      if(!report){status('download-status','请先使用当前输入完成一次计算。',true);return false;}
      try { const formats={json:[()=>Engine.stringify(report,2),'application/json'],text:[()=>Engine.reportText(report),'text/plain'],csv:[()=>Engine.reportCSV(report),'text/csv'],html:[()=>Engine.reportHTML(report),'text/html']};const entry=formats[format];const content=entry[0]();download(content,'mhxy-report.'+(format==='text'?'txt':format),entry[1]+';charset=utf-8');status('download-status','已生成 '+format.toUpperCase()+' 报告下载，请在浏览器下载目录核对。');return content;}catch(error){status('download-status','报告未生成：'+error.message,true);return false;}
    }
    $('sample-button').addEventListener('click',()=>loadInput(SAMPLE_TEXT,'纯合成演示'));
    $('blank-button').addEventListener('click',()=>loadInput(BLANK_TEXT,'空白草稿'));
    $('save-draft-button').addEventListener('click',saveDraft);
    $('calculate-button').addEventListener('click',calculate);$('calculate-bottom').addEventListener('click',calculate);
    $('validate-button').addEventListener('click',()=>{const r=diagnose();status('input-status',r.ready?'输入检查通过。计算结果仍取决于你填写的数据和模型假设。':'发现 '+r.issues.length+' 项待处理内容。',!r.ready);});
    $('add-metric').addEventListener('click',()=>{if(data.metrics.length>=12)return;structuralChange(()=>{const id=uniqueId(data.metrics,'metric-');data.metrics.push({id,name:'新指标',unit:'点',direction:'maximize'});if(data.weights)put(data.weights,id,null);if(advancedWeights)put(advancedWeights,id,null);put(data.baseline.stats,id,null);data.options.forEach(o=>put(ensureMap(o,o.measured_stats!==undefined?'measured_stats':'deltas'),id,null));list(data.weight_scenarios).forEach(s=>put(s.weights,id,null));});});
    $('add-option').addEventListener('click',()=>{if(data.options.length>=64)return;structuralChange(()=>{data.options.push({id:uniqueId(data.options,'candidate-'),name:'',slot:'',price:null,fees:null,owned:false,evidence:'unverified',deltas:numericMap(data.metrics.map(m=>m.id),null)});});});
    $('input-file').addEventListener('change',event=>{
      const file=event.target.files&&event.target.files[0];if(!file)return;const generation=++fileGeneration;
      if(file.size>(Engine.MAX_BYTES||1000000)){status('file-status','文件超过 1 MB，未读取。当前草稿保持不变。',true);event.target.value='';return;}
      const revision=inputVersion;const reader=new env.FileReader();reader.onload=()=>{if(generation!==fileGeneration)return;if(revision!==inputVersion){status('file-status','读取期间表单已经变化，未覆盖当前内容。请重新选择文件。',true);return;}loadInput(String(reader.result),file.name);};reader.onerror=()=>status('file-status','本地文件读取失败，当前草稿保持不变。',true);reader.readAsText(file,'UTF-8');event.target.value='';
    });
    $('result-file').addEventListener('change',event=>{
      const file=event.target.files&&event.target.files[0];if(!file)return;const generation=++resultGeneration;
      if(file.size>16000000){status('report-import-status','报告超过 16 MB，未读取。当前结果保持不变。',true);event.target.value='';return;}
      const reader=new env.FileReader();reader.onload=()=>{if(generation!==resultGeneration)return;loadReport(String(reader.result),file.name);};reader.onerror=()=>{if(generation===resultGeneration)status('report-import-status','报告读取失败，当前结果保持不变。',true);};reader.readAsText(file,'UTF-8');event.target.value='';
    });
    $('input-editor').addEventListener('input',()=>{advancedDirty=true;invalidate();diagnose();status('json-status','JSON 修改尚未应用。');});
    $('apply-json-button').addEventListener('click',()=>{const raw=$('input-editor').value;if(loadInput(raw,'高级 JSON 输入',true)){dirty=true;status('json-status','已应用 JSON，并更新表单。');}else status('json-status','JSON 未应用，请查看上方文件提示。',true);});
    $('refresh-json-button').addEventListener('click',()=>{if(advancedDirty&&!confirmAction('放弃尚未应用的 JSON 修改，使用当前表单内容替换吗？'))return;advancedDirty=false;$('input-editor').value=Engine.stringify(data,2);diagnose();status('json-status','已用当前表单刷新。');});
    for(const format of ['json','text','csv','html'])$('download-'+format).addEventListener('click',()=>exportReport(format));
    if(typeof env.addEventListener==='function')env.addEventListener('beforeunload',event=>{if(dirty||resourceDirty){event.preventDefault();event.returnValue='';}});
    editableShape(data);render();renderResources();$('startup-notice').hidden=true;
    return {applyResourceIntake:(...args)=>applyResourceIntake(...args),syncResourceIntake:(...args)=>syncResourceIntake(...args),getResourceReceipt:()=>resourceReceipt,loadResources:(...args)=>loadResources(...args),getResources:()=>({inputs:resourceState,results:resourceResults,dirty:resourceDirty,version:resourceVersion}),getData:()=>data,getReport:()=>report,getControls:()=>controls,diagnose,calculate,loadInput,loadReport,saveDraft,exportReport,render,getState:()=>({dirty,advancedDirty,source,inputVersion})};
  }
  return {mount,resourceDraft,RESOURCE_SCHEMA,SAMPLE_TEXT,BLANK_TEXT,editableShape,validateReport,numericText};
}));
