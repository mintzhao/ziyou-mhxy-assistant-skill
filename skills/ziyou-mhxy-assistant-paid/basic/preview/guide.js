/* Bounded offline text patterns, not general NLP. Only explicit, reviewable values cross pages. */
(function(root,factory){'use strict';if(typeof module==='object'&&module.exports)module.exports=factory(require('./resources.js'),require('./intake.js'));else{root.MHXYGuide=factory(root.MHXYResources,root.MHXYIntake);if(root.document)root.MHXYGuide.mount(root.document);}}(typeof globalThis!=='undefined'?globalThis:this,function(Resources,Intake){
'use strict';
const routes={
 xiuyedian:{title:'修业点练宠：先看24小时资格，再看兑换预览',href:'../references/grounded-player-guidance.md#xiuyedian',label:'查看修业点分批办法',advice:[],questions:[],reference:'../references/grounded-mechanics.md'},
 cage_factors:{title:'炼兽笼经验：双倍无效，精修有效',href:'../references/pet-maintenance-and-leveling.md',label:'查看炼兽笼现行条件',advice:[],questions:[],reference:'../references/pet-maintenance-and-leveling.md'},
 scene_leveling:{title:'宝宝场景练级：先核等级区间，再比较带练成本',href:'../references/pet-maintenance-and-leveling.md',label:'查看场景分段与条件',advice:[],questions:[],reference:'../references/grounded-mechanics.md'},
 repair:{title:'装备修理：先分人物与召唤兽，再选修复方法',href:'../references/grounded-player-guidance.md#repair',label:'查看分方法修理指引',advice:[],questions:[],reference:'../references/grounded-mechanics.md'},
 crafting:{title:'玄灵珠：20格问题的条件容量安排',href:'../references/crafting-planner.md',label:'查看条件手工规划器用法',advice:[],questions:[],reference:'../references/crafting-planner.md'},
 gem_operations:{title:'普通宝石：直接镶嵌与自行合成分开回答',href:'planning.html#gem_upgrade',label:'打开完整宝石计划',advice:[],questions:[],reference:'../references/grounded-player-guidance.md#gem-operations'},
 gem:{title:'普通宝石：先核资格，再列齐每个新增等级',href:'planning.html#gem_upgrade',label:'打开完整宝石计划',advice:['新增段数要逐级各备一颗同级石；只算最高级一颗会漏材料。已有同级库存和新买材料分开计。','成品目标要核对底子、套装与特效；旧物还没卖掉，卖价不能当现在能花的现金。'],questions:['现在是什么装备部位、等级和锻数？','这次想升到几段？'],reference:'../references/whole-plan-workflow.md'},
 training:{title:'修炼：区分普通购买与经验道具',href:'planning.html#training_mix',label:'打开混合修炼计划',advice:['先按已确认的上限算还差多少经验，再比较整颗道具与普通10经验购次。','没有确认每颗道具经验或混用资格时，只能给条件比较；不要把网上金丹品质假定成经验。'],questions:['哪种修炼，从几级到几级？','本级已经有多少经验？'],reference:'../references/whole-plan-workflow.md'},
 portfolio:{title:'一笔预算：先列这次真正要完成的目标',href:'planning.html#portfolio',label:'打开共同预算计划',advice:['先保留不动用的余额，再比较能达到目标的整项方案；没有效果依据的方案先待核实。','已经做完的项目不该再扣钱或库存。表单里的预算和库存应填当前余额，而不是上次计划前的数字。'],questions:['这次最想解决哪个实际问题？','这次可新增投入多少、用哪种货币？'],reference:'../references/whole-plan-workflow.md'},
 equipment:{title:'装备取舍：比较同状态人物面板',href:'equipment.html',label:'打开装备取舍',advice:['可先选最低成本达标或Pareto取舍，无需填写偏好权重。','只有同状态的整个人物实测面板或相对现装备的净变化才可相加；装备白字不能直接当作人物面板。'],questions:['最想改善哪项面板或实际问题？','这次准备花多少？'],reference:'../references/input-format.md'},
 replace:{title:'保留、自升、换成品：分开现金与净成本',href:'decision.html',label:'打开自升 / 替换比较',advice:['先确认两条路线能达到同一目标，再分别记新支出、自有材料机会成本和有条件卖旧。','先买后卖要备足购买现金；历史买入价是沉没成本，不重复扣一次。'],questions:['想达到什么共同目标？','已经找到的成品总价是多少？'],reference:'../references/decision-calculators.md'},
 host:{title:'这类问题由 Skill 宿主结合资料回答',href:'../SKILL.md',label:'查看 Skill 入口与能力范围',advice:['网页没有离线聊天模型；完整自然语言判断由支持本地 Skill 与Python的宿主完成。','可以把问题、目前已知情况和手工报价直接交给宿主，不必自己写JSON。没有核验的机制或价格应保留未知。'],questions:['你现在具体要做哪一个决定？','有什么已经确认的现状或报价？'],reference:'../references/player-workflows.md'}
};
const LABELS={type:'修炼类型',currentLevel:'当前修炼等级',targetLevel:'目标修炼等级',currentProgressXp:'本级已有经验',confirmedCap:'已确认修炼上限',gemType:'新增宝石类型',currentForge:'当前锻数',targetForge:'目标锻数',slot:'装备部位',equipmentLevel:'装备原始等级',characterLevel:'人物等级',budget:'本次预算',currency:'货币',reserve:'必须预留'};
for(let grade=1;grade<=20;grade++)LABELS['gradeQuote'+grade]=grade+'级宝石报价（两）';
const NUMBER='[+＋−－﹣–—-]?(?:\\d[\\d.,]*(?:[eE][+-]?\\d+)?|\\.\\d+)';
const END='(?![0-9A-Za-z_.,/])';
const TYPES=[['attack','攻击修炼|攻修'],['spell','法术修炼|法修'],['defense','防御修炼|防修'],['anti_spell','法术防御修炼|抗法修炼|抗法'],['hunting','猎术修炼|猎术']];
const SLOT_ALIASES={武器:'武器',头盔:'头盔',帽子:'头盔',铠甲:'铠甲',衣服:'铠甲',腰带:'腰带',鞋子:'鞋子',鞋:'鞋子',项链:'项链'};
const SLOTS='武器|头盔|帽子|铠甲|衣服|腰带|鞋子|鞋|项链';
function number(raw,key){
 const limits={currentLevel:25,targetLevel:25,confirmedCap:25,currentForge:20,targetForge:20,equipmentLevel:160,characterLevel:175};
 if(!/^[0-9]{1,16}$/.test(raw))throw new Error(LABELS[key]+'必须是完整的非负整数，不接受小数、负数、千位分隔或科学计数');
 const n=BigInt(raw);if(n>9007199254740991n||(Object.hasOwn(limits,key)&&n>BigInt(limits[key])))throw new Error(LABELS[key]+'超出支持范围');
 if(key==='equipmentLevel'&&n%10n!==0n)throw new Error('装备原始等级必须为10的倍数');
 return String(n);
}
function amount(raw,unit){
 if(!/^(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$/.test(raw))throw new Error('金额只接受非负十进制数，最多6位小数，不接受分隔符或科学计数');
 const [whole,part='']=raw.split('.'),factor=unit==='亿'?100000000n:unit==='万'?10000n:1n;
 const micro=(BigInt(whole)*1000000n+BigInt(part.padEnd(6,'0')))*factor;
 if(micro>1000000000000000000n)throw new Error('金额不能超过1万亿');
 const tail=String(micro%1000000n).padStart(6,'0').replace(/0+$/,'');return String(micro/1000000n)+(tail?'.'+tail:'');
}
function currency(s){return /两|游戏币|梦幻币/.test(s)?'两':'人民币元';}
function extract(question,route){
 const q=question, candidates=[], issues=[], seenIssues=new Set();
 function issue(code,message){if(!seenIssues.has(code)){seenIssues.add(code);issues.push({code,message});}}
 const contextual=/[“”‘’「」『』"'`]|(?:例如|比如|举例|示例|例子|假设|假如|如果|他(?:人)?说|她说|朋友说|别人说|据说|听说|原文|示范|假定|例\s*[:：])/.test(q);
 const uncertain=/(?:不是|并非|不要|别算|别升|而非|不(?:升|到|打|算|用|确定|确认|足|够|超过|等于)|没(?:有|到|确认)|未(?:知|确认|到|达)|无需|不需要|尚未|还是|或者|也许|可能|好像|似乎|应该|估计|大概|预计|或)/.test(q);
 if(contextual)issue('context','文字含引用、例子或假设，不能当作已陈述的当前情况。请单独写本次要采用的一组信息，或直接打开空白工具。');
 if(uncertain)issue('uncertain','文字含否定、不确定或备选说法，暂不选取其中的数值。请明确本次采用哪一项。');
 function add(key,value,start,end){
  if(end-start>120){issue('long_source','某个字段的原文过长，请缩短该字段的表述后重试。');return;}
  candidates.push({key,label:LABELS[key],value,source:{start,end,text:q.slice(start,end)},scope:contextual?'hypothetical':'stated'});
 }
 function numeric(key,raw,start,end){try{add(key,number(raw,key),start,end);}catch(e){issue('invalid_'+key,'这组等级或数值暂不能计算：'+e.message+'。');}}
 // Longest aliases win at the same character offset, avoiding 法术防御修炼 => 防御修炼.
 const typeMatches=[...q.matchAll(new RegExp(TYPES.flatMap(x=>x[1].split('|')).sort((a,b)=>b.length-a.length).join('|'),'g'))];
 for(const m of typeMatches){const type=TYPES.find(x=>x[1].split('|').includes(m[0]));add('type',type[0],m.index,m.index+m[0].length);}
 const gems=Resources?Resources.gemTypes:[];
 for(const m of q.matchAll(new RegExp(gems.map(x=>x.name).join('|')||'(?!)','g')))add('gemType',gems.find(x=>x.name===m[0]).id,m.index,m.index+m[0].length);
 const types=new Set(candidates.filter(x=>x.key==='type').map(x=>x.value)),gemKinds=new Set(candidates.filter(x=>x.key==='gemType').map(x=>x.value));
 if(types.size&&gemKinds.size&&route!=='portfolio')issue('multiple_systems','同时出现修炼与宝石，请先明确这次要计算哪一个系统。');
 // The outer lookahead intentionally retains overlapping/chained intervals for ambiguity detection.
 const ranges=[...q.matchAll(new RegExp('(?=((?:^|[^0-9A-Za-z_.,/\\+＋−－﹣–—-])('+NUMBER+')\\s*(?:级|段|锻)?\\s*(?:升到|到|→|->|升|至)\\s*('+NUMBER+')'+END+'\\s*(?:级|段|锻)?))','g'))];
 if(ranges.length>1)issue('multiple_ranges','发现多个或连续等级区间，请只保留本次的一组当前等级和目标等级。');
 else if(ranges.length===1&&(route==='training'||route==='gem')){
  const m=ranges[0],offset=m[1].indexOf(m[2]),start=m.index+offset,end=m.index+m[1].length;
  if(/价格|预算|花费|成本|单价|经验|库存/.test(q.slice(Math.max(0,start-8),start))||/^(?:万|亿|两|元|经验)/.test(q.slice(end))||(route==='training'&&/[段锻]/.test(m[1])))issue('range_context','这组数字区间可能是金额、经验或其他单位，不能当作当前与目标等级；请把等级单独写清。');
  else{numeric(route==='training'?'currentLevel':'currentForge',m[2],start,end);numeric(route==='training'?'targetLevel':'targetForge',m[3],start,end);}
 }
 function scan(pattern,fn){for(const m of q.matchAll(new RegExp(pattern,'g')))fn(m);}
 if(route==='training'){
  scan('(?:当前(?:修炼)?(?:等级)?|现在(?:修炼)?(?:等级)?|修炼当前等级)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*级',m=>numeric('currentLevel',m[1],m.index,m.index+m[0].length));
  scan('(?:目标(?:修炼)?(?:等级)?|修炼目标等级|想升到|要升到|升到|想升至)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*级',m=>numeric('targetLevel',m[1],m.index,m.index+m[0].length));
  scan('(?:本级|当前修炼)(?:已经|已有|已获|获得|有)?\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(?:点?经验|XP|xp)',m=>numeric('currentProgressXp',m[1],m.index,m.index+m[0].length));
  scan('(?:本级|当前修炼|当前)(?:已经|已有|已获|获得|有)?经验\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'(?:\\s*(?:点?经验|XP|xp))?',m=>numeric('currentProgressXp',m[1],m.index,m.index+m[0].length));
  scan('(?:(?:已确认|确认)(?:的)?\\s*)?(?:修炼)?上限\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*级?',m=>numeric('confirmedCap',m[1],m.index,m.index+m[0].length));
  for(const m of q.matchAll(/本级|当前(?:修炼)?经验|已有经验|现有经验|修炼经验|上限/g)){
   const key=m[0]==='上限'?'confirmedCap':'currentProgressXp';
   if(!candidates.some(f=>f.key===key&&f.source.start<=m.index&&f.source.end>=m.index+m[0].length))issue('unparsed_'+key,'提到了“'+m[0]+'”，但无法可靠读出唯一完整数值。请明确写为“本级经验123，上限4级”这样的字段。');
  }
 }
 if(['gem','equipment','replace'].includes(route)){
  scan(SLOTS,m=>add('slot',SLOT_ALIASES[m[0]],m.index,m.index+m[0].length));
  scan('(?:^|[^0-9A-Za-z_.,/\\+＋−－﹣–—-])('+NUMBER+')'+END+'\\s*级\\s*('+SLOTS+')',m=>{const start=m.index+m[0].indexOf(m[1]);numeric('equipmentLevel',m[1],start,m.index+m[0].length);});
  scan('装备(?:原始)?(?:要求)?等级\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*级?',m=>numeric('equipmentLevel',m[1],m.index,m.index+m[0].length));
  scan('人物等级\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*级?',m=>numeric('characterLevel',m[1],m.index,m.index+m[0].length));
  if(route==='gem'){
   scan('当前(?:锻数|锻炼等级|段数)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(?:锻|段)?',m=>numeric('currentForge',m[1],m.index,m.index+m[0].length));
   scan('目标(?:锻数|锻炼等级|段数)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(?:锻|段)?',m=>numeric('targetForge',m[1],m.index,m.index+m[0].length));
  }
 }
 const moneyUnit='两|游戏币|梦幻币|人民币元|人民币|元(?!宝)|RMB(?![A-Za-z])|CNY(?![A-Za-z])';
 scan('(?:总预算|本次预算|可用预算|现金预算|预算)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(万|亿)?\\s*('+moneyUnit+')?',m=>{try{add('budget',amount(m[1],m[2]),m.index,m.index+m[0].length);if(m[3])add('currency',currency(m[3]),m.index,m.index+m[0].length);}catch(e){issue('invalid_budget',e.message+'。');}});
 scan('(?:货币|金额单位)\\s*(?:为|是|[:：])?\\s*('+moneyUnit+')',m=>add('currency',currency(m[1]),m.index,m.index+m[0].length));
 scan('(?:必须预留|预留|保留余额)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(万|亿)?\\s*('+moneyUnit+')?',m=>{try{add('reserve',amount(m[1],m[2]),m.index,m.index+m[0].length);if(m[3])add('currency',currency(m[3]),m.index,m.index+m[0].length);}catch(e){issue('invalid_reserve',e.message+'。');}});
 if(/(?:美元|美金|欧元|港币|港元|日元|USD|EUR|JPY|元宝|金币|银币|点券|点卡|仙玉)/.test(q)&&/预算|预留|保留余额/.test(q))issue('unsupported_currency','预算或预留提到了尚不支持的货币；请明确使用游戏币两或人民币元，不能自动换算。');
 for(const m of q.matchAll(/(?:总预算|本次预算|可用预算|现金预算|预算)|(?:必须预留|预留|保留余额)/g)){
  const k=/预留|保留余额/.test(m[0])?'reserve':'budget';
  if(!candidates.some(f=>f.key===k&&f.source.start<=m.index&&f.source.end>=m.index+m[0].length)&&new RegExp('^'+m[0]+'\\s*(?:为|是|[:：])?\\s*[0-9+＋−－﹣–—.-]').test(q.slice(m.index)))issue('unparsed_'+k,'提到了“'+m[0]+'”，但金额格式尚不能可靠识别。请写完整数字、万或亿单位，并明确货币。');
 }
 if(route==='gem'){
  const matchedQuotes=[];
  scan('(?:^|[^0-9A-Za-z_.,/\\+＋−－﹣–—-])('+NUMBER+')级(?:(?:宝石)|(?:'+gems.map(g=>g.name).join('|')+'))?(?:报价|单价|价格)\\s*(?:为|是|[:：])?\\s*('+NUMBER+')'+END+'\\s*(万|亿)?\\s*('+moneyUnit+')?',m=>{
   const start=m.index+m[0].indexOf(m[1]),end=m.index+m[0].length;matchedQuotes.push({start,end});
   if(!/^[0-9]{1,2}$/.test(m[1])||BigInt(m[1])<1n||BigInt(m[1])>20n){issue('invalid_quote_grade','报价等级只支持1–20级的完整整数，请核对这条报价。');return;}
   if(!m[4]||currency(m[4])!=='两'){issue('quote_currency','逐级宝石报价必须逐项明确使用游戏币两；货币缺失或不同的报价暂不携带，也不作自动换算。');return;}
   try{add('gradeQuote'+String(BigInt(m[1])),amount(m[2],m[3]),start,end);add('currency','两',start,end);}catch(error){issue('invalid_quote_amount',error.message+'。');}
  });
  for(const m of q.matchAll(/(?:报价|单价|价格)/g)){
   if(!matchedQuotes.some(f=>f.start<=m.index&&f.end>=m.index+m[0].length)&&/^[^，。；\n]{0,20}[0-9]/.test(q.slice(m.index+m[0].length)))issue('unparsed_quote','提到了具体宝石价格，但无法确认对应等级、完整金额和货币。请写为“9级报价100两”这样的逐项格式。');
  }
 }
 const fields=[];
 for(const key of Object.keys(LABELS)){
  const options=candidates.filter(x=>x.key===key),values=new Set(options.map(x=>x.value));
  if(values.size>1)issue('conflict_'+key,'“'+LABELS[key]+'”有多个不同值（'+[...values].join(' / ')+'），请明确本次采用哪个值。');
  else if(options.length)fields.push(options[0]);
 }
 const allowed=route==='training'?['type','currentLevel','targetLevel','currentProgressXp','confirmedCap','budget','currency','reserve']:route==='gem'?['gemType','currentForge','targetForge','slot','equipmentLevel','characterLevel','budget','currency',...Object.keys(LABELS).filter(k=>/^gradeQuote/.test(k))]:route==='portfolio'?['budget','currency','reserve']:['slot','equipmentLevel','characterLevel','budget','currency'];
 const budgetPhrase=candidates.find(f=>f.key==='budget');
 const budgetCurrencyConfirmed=!budgetPhrase||candidates.some(f=>f.key==='currency'&&((f.source.start===budgetPhrase.source.start&&f.source.end===budgetPhrase.source.end)||/^(?:货币|金额单位)/.test(f.source.text)));
 return {fields:fields.filter(x=>allowed.includes(x.key)),candidates:candidates.filter(x=>allowed.includes(x.key)),issues,budgetCurrencyConfirmed};
}
// Field-local hints only remove redundant questions. They never create owned facts.
// Ambiguity, quotations, denials and conflicting values keep the question open.
const HINT_CONTEXT=/[“”‘’「」『』"'`]|例如|比如|举例|示例|假设|假如|如果|假定|朋友|别人|据说|听说|原文/;
const HINT_UNCERTAIN=/不是|并非|不确定|不知道|不清楚|不详|不确认|不足|不到|未确认|没确认|未知|待确认|是否|能否|是不是|会不会|还是|或者|也许|可能|好像|似乎|大概|估计|预计|或|吗|[?？]/;
function affirmativeHint(q,pattern,topic){
 if(HINT_CONTEXT.test(q))return null;
 const clauses=q.split(/[，,。；;\n]/).filter(c=>topic.test(c));
 if(clauses.some(c=>HINT_UNCERTAIN.test(c)||/[0-9]+级\s*(?:[\/、]|和|到|至|→|->)\s*[0-9]+级/.test(c)))return null;
 const values=[];
 for(const clause of clauses){
  // A negated method elsewhere must not invalidate an independent affirmative field.
  if(/不|未|没|非|别/.test(clause))continue;
  for(const match of clause.matchAll(new RegExp(pattern.source,'g')))values.push(match[1]);
 }
 return values.length&&new Set(values).size===1?values[0]:null;
}
// Capture the complete raw token before validation. Never discard a bad later
// declaration and then treat an earlier valid one as the sole current fact.
const HINT_RAW_NUMBER='[+＋−－﹣–—-]?(?:[0-9０-９][0-9０-９A-Za-z_.,/＋+−－﹣–—-]*|[零〇一二三四五六七八九十百千万亿两]+)';
const HINT_NUMBER_BOUNDARY='(?:^|[^0-9０-９A-Za-z_.,/＋+−－﹣–—零〇一二三四五六七八九十百千万亿两-])';
function boundedNumericHint(q,patterns,topic,maximum,aliases={}){
 if(!Array.isArray(patterns))patterns=[patterns];
 const parse=value=>{
  if(Object.hasOwn(aliases,value))return aliases[value];
  if(!/^(?:0|[1-9][0-9]*)$/.test(value))return null;
  const n=BigInt(value);return n<=BigInt(maximum)?String(n):null;
 };
 const raw=patterns.flatMap(p=>[...q.matchAll(new RegExp(p.source,'g'))].map(m=>m[1]));
 const parsed=raw.map(parse);
 if(!raw.length||parsed.some(v=>v===null)||new Set(parsed).size!==1)return null;
 const affirmed=patterns.map(p=>affirmativeHint(q,p,topic)).filter(v=>v!==null).map(parse);
 return affirmed.length&&affirmed.every(v=>v===parsed[0])?parsed[0]:null;
}
function methodExclusionAnalysis(q,name){
 // Scope uncertainty to the exclusion phrase. "不用X怎么练宠？" excludes X;
 // the unrelated final question mark must not erase that explicit constraint.
 const direct=q.replace(/“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|"[^"]*"|'[^']*'|`[^`]*`/g,' ');
 const clauses=direct.split(/[，,。；;\n]/).filter(c=>c.includes(name)&&!HINT_CONTEXT.test(c));
 const before=new RegExp('(?:不考虑|不打算|不想(?:用|吃|靠)?|不能(?:使用|用|吃|兑换)|不(?:再)?(?:使用|用|吃|靠|走)|不要(?:用|吃)?|排除|别(?:用|吃))\\s*(?:再|先|使用|用|吃|兑换|消耗|通过|靠){0,2}\\s*(?:(?:修业点|月华露|炼兽笼)(?:和|、|及|与|以及))*'+name,'g');
 const after=new RegExp(name+'\\s*(?:(?:和|、|及|与|以及)(?:修业点|月华露|炼兽笼))*\\s*(?:都|均|也|先|暂时|暂)?\\s*(?:不考虑|不用|不要|排除|不吃)','g');
 let uncertain=false;
 const excluded=clauses.length>0&&clauses.every(clause=>{
  const spans=[...clause.matchAll(before),...clause.matchAll(after)].filter(m=>{
   const prefix=clause.slice(Math.max(0,m.index-14),m.index);
   const suffix=clause.slice(m.index+m[0].length);
   const unsurePrefix=/(?:不|没|未|别|不能|不想|不愿|不考虑|不打算|不要|无意|不是|并非|是否|是不是|能否|会不会|不确定|不知道|没确认|未确认|可能|也许|好像|似乎)(?:要|该|应该|可以|选择|真的|就|先|再|打算|\s)*$/.test(prefix);
   const unsureSuffix=/^\s*(?:吗|么|[?？]|是否|是不是|不确定|不知道|未知|待确认)/.test(suffix);
   if(unsurePrefix||unsureSuffix)uncertain=true;
   return !unsurePrefix&&!unsureSuffix;
  });
  return [...clause.matchAll(new RegExp(name,'g'))].every(m=>spans.some(span=>span.index<=m.index&&span.index+span[0].length>=m.index+name.length));
 });
 return {excluded,uncertain};
}
function methodExcluded(q,name){return methodExclusionAnalysis(q,name).excluded;}

// These display-only hints never create account facts or a calculator handoff.
// A quoted, uncertain, conflicting or malformed level cannot become a target tier.
function humanRepairItemHint(q){
 const aliases={武器:['武器','打造'],铠甲:['铠甲','裁缝'],衣服:['铠甲','裁缝'],头盔:['头盔','裁缝'],帽子:['头盔','裁缝'],靴子:['靴子','炼金'],鞋子:['靴子','炼金'],腰带:['腰带','炼金'],项链:['饰品','炼金'],饰品:['饰品','炼金']};
 const kinds=Object.keys(aliases).join('|'),topic=new RegExp(kinds+'|人物装备|人装|装备(?:原始)?等级');
 const itemText=q.replace(/(?:没有|没|无)耐久(?:度)?/g,'').replace(/(?:怎么|如何|怎样|去哪(?:里)?|哪里|在哪(?:里)?)(?:找(?:玩家)?摊位|操作|修理|修复|修|补耐久)[?？]?/g,'');
 const matches=[...itemText.matchAll(new RegExp(kinds,'g'))].map(m=>aliases[m[0]]);
 const unique=new Set(matches.map(x=>x[0]));
 const clauses=itemText.split(/[，,。；;\n]/).filter(c=>topic.test(c));
 const clear=!HINT_CONTEXT.test(itemText)&&!clauses.some(c=>HINT_UNCERTAIN.test(c));
 const category=clear&&unique.size===1?matches[0]:null;
 const patterns=[new RegExp(HINT_NUMBER_BOUNDARY+'('+HINT_RAW_NUMBER+')级(?:人物)?(?:'+kinds+'|装备)'),new RegExp('(?:'+kinds+'|人物装备|装备)(?:原始)?(?:等级)?\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级')];
 const levelMatches=patterns.flatMap(p=>[...itemText.matchAll(new RegExp(p.source,'g'))]);
 const unmatchedLevelLabel=[...itemText.matchAll(new RegExp('(?:'+kinds+'|人物装备|装备)(?:原始)?等级','g'))].some(m=>!levelMatches.some(v=>v.index<=m.index&&v.index+v[0].length>=m.index+m[0].length));
 const rawLevel=clear&&unique.size<=1&&!unmatchedLevelLabel?boundedNumericHint(itemText,patterns,topic,160):null;
 const level=rawLevel!==null&&Number(rawLevel)%10===0?rawLevel:null;
 return {name:category?category[0]:'人物装备',skill:category?category[1]:null,level};
}

// A synthesis output grade is not an owned/source grade. This is bounded guidance,
// not inventory extraction: explicit output roles win; source-only inputs stay unknown.
function ordinarySynthesisIntent(q){return /合成(?!费)|合到|合出|合至|合为|合\s*(?:一颗|1颗)?\s*[0-9一二两三四五六七八九十]+级/.test(q);}
function ordinarySynthesisTarget(q){
 // A deliberately small grammar: named objects, source/target roles, grade tokens,
 // quantity markers and list continuations. No inventory quantities are imported.
 if(/[“”‘’「」『』"'`]|例如|比如|举例|示例|假设|假如|如果|假定|朋友|别人|据说|听说|原文|不是|并非|不要|别算|不确定|未确认|没确认|未知|也许|可能|好像|似乎|大概/.test(q))return null;
 const malformed=/[0-9０-９+＋−－﹣–—-][0-9０-９A-Za-z_.,/＋+−－﹣–—-]*级/.test(q.replace(/(?:^|[^0-9０-９A-Za-z_.,/＋+−－﹣–—-])[1-9][0-9]?级/g,''));
 if(malformed)return null;
 const gemNames='黑宝石|光芒石|太阳石|月亮石|红玛瑙|舍利子|神秘石|翡翠石|普通宝石(?!工艺)|宝石(?!工艺)';
 const otherNames='宝石工艺|技能|打造技巧|裁缝技巧|炼金术|人物|角色|装备';
 const sourceNames='已有|现有|我有|只有|当前|现在|手上|手里|库存|原料|材料|用|拿|从|买了|已买好|买好|持有|有';
 const targetNames='合成到|合成|合到|合出|合至|合为|合|目标等级|目标|产物等级|产物|成品等级';
 const joinNames='或者|或是|还是|以及|和|或|、';
 const quantity='(?:[0-9]+|[一二两三四五六七八九十]+)\\s*(?:颗|个|枚)';
 const token=new RegExp(otherNames+'|'+gemNames+'|'+targetNames+'|'+sourceNames+'|'+joinNames+'|升到|到|至|→|'+quantity+'|[0-9]{1,3}(?:\\s*级)?','g');
 const gem=new RegExp('^(?:'+gemNames+')$'),other=new RegExp('^(?:'+otherNames+')$'),source=new RegExp('^(?:'+sourceNames+')$'),target=new RegExp('^(?:'+targetNames+')$'),join=new RegExp('^(?:'+joinNames+')$'),qty=new RegExp('^(?:'+quantity+')$');
 const candidates=[];
 let previous={role:null,object:null};
 for(const clause of q.split(/[，,。；;\n！？!?]/)){
  if(!clause.trim())continue;
  const tokens=[...clause.matchAll(token)],rows=[];
  let role=null,object=null;
  const bareContinuation=tokens.length&&(gem.test(tokens[0][0])||/^[0-9]/.test(tokens[0][0])||qty.test(tokens[0][0]))&&!tokens.some(t=>target.test(t[0])||source.test(t[0]));
  if(tokens.length&&(join.test(tokens[0][0])||(bareContinuation&&['source','other'].includes(previous.role))))({role,object}=previous);
  for(let i=0;i<tokens.length;i++){
   const m=tokens[i],word=m[0];
   if(other.test(word)){object='other';continue;}
   if(gem.test(word)){object='gem';continue;}
   if(target.test(word)){role='target';if(/^合/.test(word)&&object!=='other')object='gem';continue;}
   if(source.test(word)){role='source';continue;}
   if(join.test(word))continue; // The whole list keeps its current source/target/object role.
   if(/^(?:升到|到|至|→)$/.test(word)){role='target';continue;}
   if(qty.test(word)){
    if(role!=='target'){
     role='source';
     if(rows.length&&rows[rows.length-1].role===null)rows[rows.length-1].role='source';
    }
    continue;
   }
   const raw=word.replace(/\s*级$/,''),before=clause.slice(0,m.index),after=clause.slice(m.index+word.length);
   const isGrade=/级$/.test(word)||/^(?:\s*)(?:到|至|→|升到)/.test(after)||/(?:到|至|→|升到)\s*$/.test(before);
   if(!isGrade)continue;
   if(!/^[1-9][0-9]?$/.test(raw))return null;
   let itemObject=object;
   if(new RegExp('^\\s*(?:的)?(?:'+otherNames+')').test(after))itemObject='other';
   else if(new RegExp('^\\s*(?:的)?(?:'+gemNames+')').test(after))itemObject='gem';
   const itemEnd=after.replace(new RegExp('^\\s*(?:'+gemNames+')'),'');
   const ownedSuffix=/^\s*(?:(?:是|作为|当作)\s*(?:我)?(?:已有|现有|当前|持有|原料|材料|库存)|(?:已有|现有|已买好|买好)|(?:各)?有\s*(?:[0-9]+|[一二两三四五六七八九十]+)\s*(?:颗|个|枚)|在(?:包里|背包|仓库|手里|手上)|(?:的)?(?:我)?(?:已经)?有(?:了|的))/.test(itemEnd);
   const itemRole=itemObject==='other'?'other':role===null&&ownedSuffix?'source':role;
   rows.push({value:Number(raw),role:itemRole,object:itemObject,index:m.index});
  }
  // Earlier unlabeled inputs in "11级石合到12级" become sources. Otherwise a
  // bare grade in this gem-synthesis clause names a requested product. Quantities,
  // ownership predicates and named non-gem objects were classified above.
  for(const row of rows){
   if(row.role===null)row.role=rows.some(next=>next.role==='target'&&next.index>row.index)?'source':'target';
   if(row.role==='target')candidates.push(row.value);
  }
  if(rows.length){const last=rows[rows.length-1];previous={role:last.role,object:last.object};}
  else if(role!==null||object!==null)previous={role,object};
 }
 const targets=new Set(candidates);
 return targets.size===1?[...targets][0]:null;
}

// These are dated, static rules and conditional methods, not extracted account facts or new calculators.
function groundedGuidance(key,q,out){
 const cite=(title,url)=>({title,url,checkedDate:'2026-10-07'});
 // Only suppress redundant questions for simple affirmative labels; do not persist or calculate these hints.
 const plain=!/[“”‘’「」『』"'`]|例如|比如|举例|示例|假设|假如|如果|假定|朋友|别人|据说|听说|原文|不是|并非|不要|别算|不确定|未确认|没确认|未知|还是|或者|也许|可能|好像|似乎|大概|(?:当前|现在)[^，。；\n]*(?:当前|现在)|本级[^。；\n]*本级|(?:空位|空格)[^。；\n]*(?:空位|空格)/.test(q);
 if(key==='xiuyedian'){
  out.advice=[
   '修业点用于增加召唤兽等级经验，不能套宠修或修炼果公式。通过交易、给予或摆摊购买取得不足24小时的召唤兽，不能立即用修业点加经验；可先看NPC提示的最早可兑换时间。该提示2026年6月2日测试，6月9日全服放出。',
   '若当前兑换界面能在扣点前预览经验，先记录当前等级、本级经验和目标，再用小批点数预览；临近目标时缩小批量。确认一次后按实际等级和经验重算下一批，跨级后不要沿用上一批兑换率。没有无消耗预览时，不为测试公式而消耗点数。',
   '本页不能证明哪个等级最省点、最低现金或最快到目标：兑换基础公式、取整和跨级批次更新仍未核实，也不会把“目标139”当成当前139级。自有点与买点的成本需要分开。'
  ];
  const currentKnown=plain&&/(?:宝宝|召唤兽)?(?:当前等级|现在等级|当前|现在)\s*[:：为是]?\s*[0-9]{1,3}级(?![0-9A-Za-z_.,/])/.test(q);
  const xpKnown=plain&&/(?:本级(?:已有|已经)?经验\s*[:：为是]?\s*[0-9]+(?![0-9A-Za-z_.,/])|本级(?:已有|已经)\s*[0-9]+(?:点)?经验)/.test(q);
  out.questions=[];
  if(!currentKnown||!xpKnown)out.questions.push(currentKnown?'宝宝本级经验是多少？':xpKnown?'宝宝当前等级是多少？':'宝宝当前等级和本级经验是多少？');
  out.questions.push('游戏内是否允许现在兑换，或提示最早什么时间可兑换？');
  if(methodExclusionAnalysis(q,'修业点').uncertain){out.questions.unshift('你想排除修业点，还是保留它作为备选？');out.questions=out.questions.slice(0,2);}
  out.citations=[cite('2026年6月2日维护：修业点24小时提示','https://xyq.163.com/wh/20260531/4907_1302347.html'),cite('2026年6月9日维护：提示全服放出','https://xyq.163.com/wh/20260604/4907_1302930.html')];
 }else if(key==='repair'){
  const pet=/宠装|宝宝装备|召唤兽装备|宠物装备/.test(q),human=/人物装备|人装/.test(q)||(!pet&&/武器|铠甲|衣服|头盔|帽子|靴子|腰带|项链|鞋子|饰品/.test(q));
  const noGuild=/(?:不能|不用|不走|没有|不想|无法).{0,4}帮派/.test(q);
  const methods=['珍珠','普通修理','天眼珠','乾坤石','快捷修理'].filter(x=>q.includes(x));
  out.advice=[];
  if(pet||!human){
   out.advice.push('召唤兽装备修理失败3次仍然可以用珍珠，这是2013-03-12官方明文规则，2013-03-19已全服放出。珍珠等级+5≥宠装等级；名义补充200点耐久，受装备耐久上限限制。不能据此说一定回满、提高耐久上限或清除失败次数，也不把200点套到人物装备。');
   out.advice.push('电脑版时间服步骤：准备等级合适的珍珠→右键珍珠打开“使用珍珠”界面→宠装穿在召唤兽身上时切到“召唤兽装备栏”，在背包时切到所在的“道具”或“行囊”栏→选择目标宠装，按当前游戏提示完成使用。无须先找NPC或炉子。右键入口2015-06-09测试、2015-06-16全服；栏位切换2026-03-31测试、2026-04-07全服。当前最终消费按钮文字与位置未实测，不写死按钮名，也不保证有数值预览。');
   out.advice.push('天眼珠另有等级、类型和灵气规则，失败3次后不能再用天眼珠。2026-04-07起，时间服已全服支持已激活乾坤石给适用召唤兽装备补200耐久，类型和等级上限须按2026表核对，不能照搬人物装备范围；三失败宠装用乾坤石的资格仍未直接核实，这个状态优先采用已有明确证据的珍珠路线。');
  }
  if(human||!pet){
   const item=human&&!pet?humanRepairItemHint(q):{name:'人物装备',skill:null,level:null};
   const target=(item.level!==null?item.level+'级':'')+item.name;
   out.advice.push('人物装备修理失败3次的限制要分方法看，不能直接说整件装备报废。三失败的快捷修理资格本轮未另核，不作为这个状态的保底；三失败人物装备可用适用且已激活乾坤石有官方明文。愿意用仙玉时，可选快捷修理：装备耐久≤10，打开其所在物品／装备栏，点击装备图标右下角的“修理”按钮，再按游戏当前显示的费用和提示决定是否完成；0耐久已满足入口条件。该入口2015-07-21测试、2015-07-28全服。它是独立修理入口，可作为不依赖帮派或本人修理技能的替代；这项独立性是规则范围推断，不是原公告逐字保证。');
   const priceTier=item.level===null?null:[[80,10],[120,50],[130,230],[140,300],[150,500],[160,1000]].find(([maximum])=>Number(item.level)<=maximum);
   const historicalPrice=priceTier?'2015历史官方列价按本件'+item.level+'级对应每次'+priceTier[1]+'仙玉、增加100耐久':'本件等级未可靠识别或超出已核表，2015历史官方列价按装备等级另核，不猜所需仙玉';
   out.advice.push('快捷修理有仙玉成本，只在你愿意承担时选用。'+historicalPrice+'，未独立复核2026现价，实际费用以当前界面为准。2024-05-21起，免费仙玉不能用于角色／宠装快捷修理或购买乾坤石；不为验证价格先购买或消费。');
   const stoneRange=item.level!==null&&Number(item.level)<=80?'旧官方表中破损乾坤石适用于0–80级人物装备，可覆盖所填等级；':'按石头类型核对能否覆盖'+(item.level!==null?'本件'+item.level+'级':'本件实际等级')+'；';
   const stoneHistoricalCost=item.level!==null&&Number(item.level)<=80?'旧10仙玉激活价不作2026现价':'旧表激活价格是历史列价，不作2026现价';
   out.advice.push('已有适用且已激活乾坤石时：右键乾坤石→切到目标装备所在的装备栏、道具或行囊栏→选择目标人物装备，按游戏提示补耐久。所选石头须适用本件等级；'+stoneRange+'补100且受最大耐久限制，三失败人物装备也可用。未激活石仍要消耗仙玉激活；'+stoneHistoricalCost+'，已有未激活石不等于免费修理。');
   const stallCategory=item.skill?'按'+target+'对应的'+item.skill+'类别查找制造类修理服务':'按目标装备的实际部位查找对应制造类修理服务；武器对应打造，铠甲/头盔对应裁缝，靴子/腰带/饰品对应炼金，当前不替你选类别';
   const stallLevel=item.level!==null?'目标等级按你提供的'+item.level+'级核对':'目标等级未可靠识别，按本件实际等级核对';
   out.advice.push('想用游戏币找玩家修理服务，可右键玩家摊位招牌，'+stallCategory+'；'+stallLevel+'。上述是修理技能类别，不保证现行菜单逐字如此。人物普通修理仍需本件失败次数少于3，使用的是摊主修理能力，本人不必先练'+(item.skill||'相应技能')+'。官方确认服务存在，修理概率等同摊主在铁匠铺／布店自行修理，不保证成功。2024-04-09全服规则中，制造者体力不足会使相关制造／修理服务选项置灰，可另找可用摊位。当前具体摊位、目标等级的选档方式和最终买方按钮未完整核实，不编造精确菜单、价格或坐标。');
   const selfThreshold=item.skill&&item.level!==null?target+'自行普通修理需'+item.skill+'至少'+Math.ceil(Number(item.level)/2)+'级':'本件部位或等级未可靠识别，先核对再确定自行普通修理的技能门槛';
   out.advice.push('如果选择自行普通修理，可去铁匠铺。旧官方页（2013-01-05）要求相应技能≥装备等级的一半且失败次数少于3；武器对应打造，铠甲/头盔对应裁缝，靴子/腰带/饰品对应炼金。'+selfThreshold+'。普通修理有失败可能，完整失败后果和当前成功率未核实。');
   out.advice.push('自行普通修理的手动核对顺序：查看本件等级、部位和累计失败数→前往铁匠铺→核对自行修理技能→在当前界面找到相应修理入口并选本件装备，确认体力消耗与条件→接受失败风险后再手动操作→查看实际耐久和失败次数。累计失败3次或自身技能不足就停止这条自行普通修理路线；旧页未说明精确NPC、坐标或当前菜单名。技能不足不等于必须先练技能，可改选上面的适用路线。');
   if(!noGuild)out.advice.push('帮派福利总管路线不要求技能，但消耗帮贡。');
   out.advice.push('人物珍珠的精确恢复公式仍未知，不能直接套固定100、200或20%。若客户端已提供不消耗物品的修理确认预览，记录本次实际增加耐久再比较报价；2025年6月10日公告只核到该预览的部分服测试。旧乾坤石人物规则与2026新增宠装规则分开使用，不外推所有装备。');
  }
  out.questions=[];
  if(!pet&&!human)out.questions.push('这是人物装备还是召唤兽装备？');
  if(human&&!pet&&!noGuild&&methods.length===0)out.questions.push('准备使用珍珠、普通修理、乾坤石还是快捷修理？');
  if(!pet&&!human&&methods.length!==1)out.questions.push('准备使用珍珠、普通修理、天眼珠、乾坤石还是快捷修理？');
  if(pet&&!human&&!methods.includes('乾坤石')&&!methods.includes('天眼珠')&&/[0-9]+|我的|这件|能用|能不能|合适/.test(q)){
   // An action question such as “110级珍珠能用吗” does not question the stated
   // level; a level question, malformed token, quote or conflicting label still does.
   const levelText=q.replace(/(?:能不能用|能用吗|可以用吗|能否使用|能否用|可以使用吗|能用|合适吗)[?？]?/g,'').replace(/(?:怎么|如何|怎样)(?:使用|用|操作|修理|修复|补耐久)[?？]?/g,'');
   const petName='(?:宠装|宝宝装备|召唤兽装备|宠物装备)';
   const petLevel=boundedNumericHint(levelText,[new RegExp(HINT_NUMBER_BOUNDARY+'('+HINT_RAW_NUMBER+')级'+petName),new RegExp(petName+'(?:等级)?\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级')],/宠装|宝宝装备|召唤兽装备|宠物装备/,200);
   const pearlLevel=boundedNumericHint(levelText,[new RegExp(HINT_NUMBER_BOUNDARY+'('+HINT_RAW_NUMBER+')级珍珠'),new RegExp('珍珠(?:等级)?\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级')],/珍珠/,200);
   if(petLevel===null||pearlLevel===null)out.questions.push(petLevel!==null?'准备用的珍珠是多少级？':pearlLevel!==null?'召唤兽装备的等级是多少？':'召唤兽装备和准备用的珍珠分别是多少级？');
  }
  if(human&&!pet&&methods.length===1&&methods[0]==='珍珠')out.questions.push('装备当前耐久与界面显示的本次增加值是多少？');
  // Self-skill is relevant only when the user explicitly chooses ordinary repair.
  // No-guild alternatives above can be explained without that extra prerequisite.
  if(human&&!pet&&methods.includes('普通修理')&&!methodExcluded(q,'普通修理')){
   const failurePatterns=[new RegExp('失败(?:次数)?\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')次'),new RegExp(HINT_NUMBER_BOUNDARY+'('+HINT_RAW_NUMBER+')次(?:修理)?失败')];
   const failureCount=boundedNumericHint(q,failurePatterns,/失败/,3,{零:'0',〇:'0',一:'1',二:'2',两:'2',三:'3'});
   if(failureCount===null)out.questions.push('如果选择普通修理，这件装备累计修理失败几次？');
   const requiredSkill=/武器/.test(q)&&!/铠甲|衣服|头盔|帽子|靴子|腰带|项链|鞋子|饰品/.test(q)?'打造':/铠甲|衣服|头盔|帽子/.test(q)&&!/武器|靴子|腰带|项链|鞋子|饰品/.test(q)?'裁缝':/靴子|腰带|项链|鞋子|饰品/.test(q)&&!/武器|铠甲|衣服|头盔|帽子/.test(q)?'炼金':'打造|裁缝|炼金';
   const skillRaw=boundedNumericHint(q,new RegExp('(?:'+requiredSkill+')(?:技巧|技能|术)?\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级(?![0-9A-Za-z_.,/])'),/打造|裁缝|炼金|技能/,200);
   // A supplied shortfall answers this branch without asking for an exact level.
   // Match the whole threshold and reject other skill declarations or uncertainty.
   const shortfallPattern=/(?:本人|我的|我|自己)?打造(?:技巧|技能|术)?\s*(?:不足|不到|低于|小于|<|＜)\s*40(?:级)?(?![级0-9０-９A-Za-z_.,/＋+−－﹣–—-])/g;
   const skillClauses=q.split(/[，,。；;\n]/).filter(c=>/打造|裁缝|炼金|技能/.test(c));
   const weaponLevel=boundedNumericHint(q,[new RegExp(HINT_NUMBER_BOUNDARY+'('+HINT_RAW_NUMBER+')级(?:人物)?武器'),new RegExp('(?:武器(?:等级)?|装备(?:原始)?等级)\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级')],/武器|装备(?:原始)?等级/,160);
   const suppliedShortfall=requiredSkill==='打造'&&weaponLevel!==null&&Number(weaponLevel)>=80&&!HINT_CONTEXT.test(q)&&skillClauses.length>0&&skillClauses.every(c=>{
    const matches=[...c.matchAll(shortfallPattern)];
    const remainder=c.replace(shortfallPattern,'');
    return matches.length===1&&!HINT_UNCERTAIN.test(remainder)&&!/打造|裁缝|炼金|技能|不|未|没|非|别|(?:和|到|至|→|->|、)\s*[0-9０-９]/.test(remainder);
   });
   if(!noGuild&&failureCount!=='3'&&skillRaw===null&&!suppliedShortfall)out.questions.push('如果打算自行普通修理，你对应的打造/裁缝/炼金技能多少级？');
  }
  out.questions=out.questions.slice(0,2);
  out.citations=[];
  if(pet||!human)out.citations.push(
   cite('官方召唤兽装备：天眼珠修理条件','https://xyq.163.com/2007/fbcq/fbcq_02.html'),
   cite('2013-03-12测试：三失败宠装可用珍珠、等级及耐久上限','https://xyq.163.com/2013/3/11/4907_363789.html'),
   cite('2013-03-19：宠装修理规则全服放出','https://xyq.163.com/2013/3/18/4907_364597.html'),
   cite('2015-06-09测试：右键珍珠给指定装备补耐久','https://xyq.163.com/2015/6/6/4905_529431.html'),
   cite('2015-06-16：右键珍珠全服放出','https://xyq.163.com/2015/6/15/4907_531671.html'));
  if(human||!pet)out.citations.push(
   cite('官方打造、缝纫与炼金：装备修理（2013-01-05）','https://xyq.163.com/introduce/jn005.html'),
   cite('2015-07-21测试：快捷修理入口与历史仙玉列价','https://xyq.163.com/2015/7/17/4907_542189.html'),
   cite('2015-07-28：快捷修理全服放出','https://xyq.163.com/2015/7/27/4907_545465.html'),
   cite('2024-05-21：免费仙玉不能用于快捷修理或购买乾坤石','https://xyq.163.com/wh/20240520/4907_1155726.html'),
   cite('旧官方乾坤石说明（页面日期2012-12-28）','https://xyq.163.com/introduce/2013/1/28/5015_359141.html'),
   cite('官方摆摊：右键摊位招牌与制造类服务','https://xyq.163.com/introduce/sys/sy001.html'),
   cite('2008-11-11测试：玩家摆摊修理服务与失败风险','https://xyq.163.com/2008/11/10/4907_194633.html'),
   cite('2024-04-02测试：制造者体力不足时修理服务置灰','https://xyq.163.com/wh/20240401/4907_1146535.html'),
   cite('2024-04-09：制造及修理服务调整全服放出','https://xyq.163.com/wh/20240408/4907_1147836.html'),
   cite('2025年6月10日维护：珍珠修理预览测试','https://xyq.163.com/wh/20250606/4907_1238835.html'));
  out.citations.push(
   cite('2026-03-31测试：珍珠／乾坤石切换栏位及乾坤石宠装适用表','https://xyq.163.com/wh/20260327/4907_1293452.html'),
   cite('2026-04-07：珍珠／乾坤石调整全服放出','https://xyq.163.com/wh/20260403/4907_1294544.html'));
 }else if(key==='scene_leveling'){
  out.advice=[
   '按官网宝宝练级表（2023-03-06），蓬莱仙岛的宝宝获经验等级为109–159、满经验为129–139；若宝宝当前35级，它不在蓬莱的表列经验区间，有大龙也不能据此当作合适起点。这不是说不能进入、不能出战或任何活动都无经验。',
   '35级起步可先核大雁塔六层（满经验28–38）或海底迷宫二层（35–45）。之后按宝宝等级换满经验区间；如地狱迷宫三层46–56、北俱芦洲54–64等可衔接，后段可看蓬莱129–139、墨家禁地140–150。宿主的scene_leveling接口能展开完整等级覆盖示例，本网页仅给指引，不是练级计算表单。',
   '表内“玩家等级”是另外的条件，不能拿宝宝35级去选青丘等动态场景的低人物档。队伍按队长、最高或平均等级选档，原表未说明；先核实际场景进入/队伍条件与人物携带上限，不把表列区间当成全资格通过。',
   '低费用选择先看大龙是否收费，再比较同条件下各段净经验、有效时间、补给和点卡。免费带练也有可能产生其他成本；没有实测速度、总经验和费用，就不能报告35→150最快、最省或总小时数。',
   '炼兽笼只能作为有条件备选：宝宝至少30级，想用笼子到150人物至少140；已有笼子不重买。只为150这个阶段上限判断不用再问飞升/渡劫，各已核阶段上限都至少150。修业点的24小时取得限制、当前资格和兑换量另核，不能默认必用或最便宜。'
  ];
  if(methodExcluded(q,'修业点')){out.advice[4]=out.advice[4].split('修业点的24小时')[0];out.advice.push('已保留不考虑修业点的要求，不把它加入当前练级路线。');}
  if(methodExcluded(q,'月华露'))out.advice.push('已保留不考虑月华露的要求，不把它加入购买或使用方案。');
  const characterRaw=boundedNumericHint(q,new RegExp('(?:人物(?:等级)?|角色等级)\\s*[:：为是]?\\s*('+HINT_RAW_NUMBER+')级(?![0-9A-Za-z_.,/])'),/人物|角色/,175);
  const characterKnown=characterRaw!==null;
  const escortRaw=affirmativeHint(q,/(?:大龙|带练)(?:目前|现在|已经|明确|确定|已确认|确认|是|为)?\s*(免费|收费)/,/大龙|带练|费用|价格|收费|免费/);
  const escortKnown=escortRaw!==null;
  out.questions=[];
  if(!characterKnown)out.questions.push('你的人物多少级？这会影响能否把宝宝继续练到目标。');
  if(!escortKnown)out.questions.push('现有大龙带练免费还是收费？若收费，按什么方式、多少钱？');
  out.citations=[cite('官方宝宝练级地点表（2023-03-06）','https://xyq.163.com/introduce/cy008.html'),cite('官方炼兽笼（2012-02-06）','https://xyq.163.com/introduce/2012/2/6/5014_262875.html'),cite('2026年6月9日：修业点提示全服放出','https://xyq.163.com/wh/20260604/4907_1302930.html')];
 }else if(key==='crafting'){
  out.advice=[
   '玄灵珠不是普通宝石的2合1。官方基础说明为3颗同效果珠合成成功后得到高一级、最高8级；2024年5月21日调整明确制作4–8级必成，5/6/7/8级还分别额外消耗同类型2/3/4/5级珠1颗。等级配方由基础关系与公告组合推导，投入前仍需核对当前界面的材料要求。',
   '条件解法：如果从空散珠库存做一颗6级、配方相符、每珠一格且另留一个输出格，按完成一个子材料再做下一个的顺序，峰值11+1=12格，因此20格在这个模型里足够。宿主/CLI规划器可展开逐步清单；本网页没有合成输入表单。当前占格/材料可用和补料路径未确认时只给条件演示，不能说现在必可照做。',
   '先把最终目标所需的附加低阶珠单独留住；例如6级这一步需保留额外3级珠。只有在库存、占格和材料要求已确认时，才按“补下一次合成的缺料→手动合成一次→记录实际产物和空位→再补料”的顺序分批，避免先把所有低阶材料用尽。',
   '可以从已有中间珠核算4–8级的确定性部分；2/3级当前是否必成、堆叠/输出占格、费用、仓库可用性和批量按钮未核实。本页不输出从一级珠起算的确定购买数、最少往返或20格必可执行的完整路线。低阶实际结果改变时须从剩余库存重算。',
   '先区分“合出一颗散珠”与“逐级镶嵌到目标等级”：后者还要各前级对应效果，不能只买最高级一颗；旧页说明取出只返还当前最高级。'
  ];
  const capacityKnown=plain&&/(?:^|[^0-9A-Za-z_.,/＋+−－﹣–—-])(?:[0-9]{1,3}(?:个)?(?:空位|空格)|(?:可用空位|可用空格|空位|空格)\s*[:：为是]?\s*[0-9]{1,3}(?:个|格)?(?![0-9A-Za-z_.,/]))/.test(q);
  out.questions=['要合出一颗散珠，还是把装备上的珠升到目标等级？',capacityKnown?'现有各级玄灵珠的数量是多少？':'现有各级珠数量和合成界面实际可用空位是多少？'];
  out.citations=[cite('官方资料片：玄灵珠获得与合成（2023-12-12）','https://xyq.163.com/2024/hjzlp/'),cite('2024年5月21日高阶合成调整','https://xyq.163.com/news/20240520/4999_1156134.html')];
 }else if(key==='cage_factors'){
  out.advice=[
   '电脑版时间服炼兽笼获得的召唤兽经验不再受双倍时间影响，仍受精修时间影响；不用为炼兽笼专门领取双倍。',
   '这项调整2015-06-09仅部分服务器测试，2015-06-16全服放出。2026-01-27测试、2026-02-03全服的精修生效状态显示是后续界面佐证，不是恢复双倍加成。',
   '宝宝至少30级才可入笼，等级上限和庭院/笼子资格另核；没有已核每次经验与间隔，不据此计算总经验、总小时或总费用。需要比较效率时只补精修等相关条件，不追问双倍是否领取。'
  ];
  out.questions=[];
  out.citations=[cite('2015-06-09维护：炼兽笼调整部分服测试','https://xyq.163.com/2015/6/6/4905_529431.html'),cite('2015-06-16维护：炼兽笼调整全服放出（发布2015-06-15）','https://xyq.163.com/2015/6/15/4907_531671.html'),cite('2026-02-03维护：精修生效状态显示全服放出','https://xyq.163.com/wh/20260202/4907_1284942.html')];
 }else if(key==='gem_operations'){
  const synthesisOnly=ordinarySynthesisIntent(q)&&!/镶嵌|怎么打|哪里打|自己打|打宝石|锻|段/.test(q);
  out.advice=[
   '直接镶嵌：旧官方宝石页给出的地点是铁匠铺，按打造式操作放入装备和要镶嵌的宝石。已有目标等级石，就不需要为了镶嵌再合成一次；但仍要先核部位、原装备等级、当前锻数、精致/无级别特效和已有宝石类型。每次按当前锻数+1逐级追加，不能跳级。',
   '是否失败、是否要生活技能：已读的官方页没有明确写直接镶嵌的失败概率或技能门槛，所以这两项保留未核实，不能保证“不失败/无需技能”，也不能把打造装备的技能要求套过来。先查看游戏内对应操作提示，不为验证而消耗物品。'
  ];
  const grade=ordinarySynthesisTarget(q,plain);
  const extras={12:[3,5,6],13:[9],14:[9,10],15:[9,12],16:[11,12,13],17:[15],18:[13,14,16],19:[15,16,17],20:[17,18,18]};
  let synthesis;
  if(grade!==null&&grade>=2&&grade<=20){
   const extra=extras[grade]||[],counts=[...new Set(extra)].map(g=>g+'级'+extra.filter(v=>v===g).length+'颗').join('、');
   synthesis='自行合成'+grade+'级普通宝石：'+(grade-1)+'级同类宝石2颗'+(extra.length?'，另加'+counts+'同类宝石':'')+'；宝石工艺至少'+Math.min(7,Math.floor(grade/2)+2)+'级，在打铁炉/缝纫台操作。'+(grade>=12?'本次高阶合成必定成功；从低阶原料一路合上来仍可能有低阶失败损耗。':'2–11级不在2024公告的12–20级必成范围；旧页描述合成可能失败并损失一颗，当前精确成功率未核，不给必成保证。');
  }else if(grade===1){
   synthesis='1级普通宝石是基础取得材料，不列由0级合成1级的配方；取得途径和价格另核。';
  }else{
   synthesis='自行合成须按目标等级区分：2–11级使用两颗前一级同类普通宝石的基础关系，旧页有失败描述，当前精确概率未核；12–20级还需额外低阶同类材料且本次高阶合成必成。宝石工艺最低等级为：目标2–3级需3、4–5级需4、6–7级需5、8–9级需6、10–20级需7。';
  }
  synthesis+=' 这项调整2024-05-21全部服务器放出。以上是合成规则，不能当作镶嵌失败或技能规则；高阶单次必成不等于一级起算的保证采购数。';
  if(synthesisOnly)out.advice=[synthesis,'直接镶嵌与自行合成分开。铁匠铺镶嵌的失败/技能明文仍未核实：已读的官方页没有明确写直接镶嵌的失败概率或技能门槛。'];
  else out.advice.push(synthesis,'普通80级腰带通常上限8锻，精致多1锻；无级别需另核。普通100级鞋从8到10须9级、10级黑宝石各1颗。比较自升与换成品时，用两颗报价及费用对比等效成品总价减旧装条件净回收，未成交卖价不能算可用现金。');
  out.questions=[];
  if(synthesisOnly){if(grade===null||grade<1||grade>20)out.questions.push('本次要合出几级普通宝石？本入口核对1–20级。');}
  else{
   if(/[0-9]+|这件|我的/.test(q)&&!/精致|无级别/.test(q))out.questions.push('这件装备是否有精致或无级别限制特效？');
   if(/[0-9]+|这件|我的/.test(q)&&!/武器|头盔|帽子|铠甲|衣服|腰带|鞋子|项链/.test(q))out.questions.push('装备部位和原始等级是什么？');
  }
  out.citations=[cite('官方宝石：镶嵌与旧合成分项规则','https://xyq.163.com/introduce/dj008.html'),cite('2024-05-20公布：普通宝石分等级合成调整','https://xyq.163.com/news/20240520/4999_1156134.html'),cite('2024-05-21维护：调整全部服务器放出','https://xyq.163.com/wh/20240520/4907_1155726.html'),cite('官方工具箱：精致上限说明','https://xyq.163.com/tools/index.html')];
 }else return false;
 out.links[0].label=routes[key].label;
 out.status='guidance_only';
 return true;
}
function analyze(question){
 if(typeof question!=='string'||question.trim().length===0)return {title:'先说一句你想解决的问题',advice:['例如：防御修炼从2级到4级，本级已经123经验，上限4级，需要多少？'],questions:[],links:[],citations:[],fields:[],missing:[],issues:[],status:'empty'};
 if(question.length>4000)throw new Error('问题请控制在4000字以内，保留本次要做的决定即可。');
 const q=question;
 const repairIntent=/珍珠|乾坤石|天眼珠|修理|修复|耐久|三修(?:理)?失败|三失败/.test(q);
 const freshRuleIntent=/炼兽笼|宝石|光芒石|太阳石|月亮石|红玛瑙|舍利子|神秘石|翡翠石/.test(q);
 const scopedHost=(title,advice,questions=[])=>({route:'host',title,advice,questions,links:[{href:'../SKILL.md',label:'查看适用范围与宿主核对入口'}],citations:[],fields:[],missing:[],issues:[],status:'needs_verification',handoff:null});
 if((repairIntent||freshRuleIntent)&&/(?:不知道|不确定|不清楚|未确认|没确认|尚未确认).{0,12}(?:服制|版本|什么服|哪种服|哪个服|时间服)|(?:服制|游戏版本|服务器版本|什么服|哪种服|哪个服).{0,6}(?:未知|不明|未确认|没确认|不确定|不知道|不清楚)|时间服(?:吗|[?？])/.test(q))return scopedHost('先确认服制，再套用规则',['你明确表示服制尚未确认。当前离线规则只覆盖电脑版时间服，不能替你认定版本或直接套用当前规则。'],['实际玩的是电脑版时间服、畅玩服，还是其他版本？']);
 if(repairIntent&&/(?:召唤兽|宝宝|宠物)\s*(?:的\s*)?(?:饰品|装饰)/.test(q))return scopedHost('召唤兽饰品需要单独核对',['召唤兽饰品／装饰与召唤兽装备是不同类别。当前装备修理指引不覆盖饰品修复，不能把人物或宠装的补耐久数值、等级范围和三失败资格套到这里；应按饰品界面显示的玄天灵力等属性与对应服制规则核对。'],['这件召唤兽饰品的完整名称是什么？']);
 const datedRepair=repairIntent&&q.match(/(?:^|[^0-9０-９A-Za-z_+＋−－﹣–—-])((?:19|20)[0-9]{2}(?:年[0-9]{1,2}月[0-9]{1,2}日|-[0-9]{1,2}-[0-9]{1,2}|\/[0-9]{1,2}\/[0-9]{1,2}))(?![0-9０-９A-Za-z_.,/])/);
 if(datedRepair&&!/^2026(?:年10月7日|-10-0?7|\/10\/0?7)$/.test(datedRepair[1]))return scopedHost('指定日期的修理规则需要按当时范围核对',['你提到了'+datedRepair[1]+'。本入口提供的是截至2026-10-07核对的时间服指引，不能把后续开放的功能倒推到该日期，也不能把部分服务器测试当作当日全服开放。请由宿主按指定日期、服务器和当时官方公告单独核实；这里不继续给出当前点击路线。'],['需要核对的具体服务器名称是什么？']);
 const datedFreshRule=freshRuleIntent&&q.match(/(?:^|[^0-9０-９A-Za-z_+＋−－﹣–—-])((?:19|20)[0-9]{2}(?:年(?:[0-9]{1,2}月(?:[0-9]{1,2}日)?)?|-[0-9]{1,2}-[0-9]{1,2}|\/[0-9]{1,2}\/[0-9]{1,2}))/);
 if(datedFreshRule&&!/^2026(?:年10月7日|-10-0?7|\/10\/0?7)$/.test(datedFreshRule[1]))return scopedHost('指定日期的规则需要按当时范围核对',['你提到了'+datedFreshRule[1]+'。当前指引截至2026-10-07核验；不能把后续修改倒推到当时，也不能把部分服务器测试当全服发布。请按该日期、服务器和对应公告单独核对。'],['需要核对的具体服务器名称是什么？']);
 if(/手游|畅玩服|怀旧服|口袋版/.test(q))return {title:'先核对版本，不能套用时间服规则',advice:['本工具的已核验游戏规则适用于梦幻西游电脑版时间服。你提到了其他版本，当前不计算资源数或给购买建议。'],questions:['你实际要比较的是电脑版时间服吗？'],links:[{href:'../SKILL.md',label:'查看适用范围'}],citations:[],fields:[],missing:[],issues:[],status:'out_of_scope'};
 let key='host',hostRef=null;
 if(/修业点/.test(q)&&!methodExcluded(q,'修业点'))key='xiuyedian';
 else if(/玄灵珠/.test(q))key='crafting';
 else if(/星辉石|精魄灵石/.test(q))hostRef='verified-routes.md';
 else if(/值多少钱|估价|涨价/.test(q)&&!/恢复|修复|修理|耐久|失败/.test(q))hostRef='grounded-player-guidance.md#market-evidence';
 else if(/珍珠|乾坤石|天眼珠|修理|修复|耐久|三修(?:理)?失败|三失败/.test(q))key='repair';
 else if(/炼兽笼/.test(q)&&/双倍|精修|三倍|吃双|领双/.test(q))key='cage_factors';
 else if(/练宠|宝宝练级|召唤兽练级|炼兽笼/.test(q)||(/宝宝|召唤兽|宠物/.test(q)&&/烧双|蓬莱|升级|练级|级.{0,10}(?:到|至|→|升)/.test(q)))key='scene_leveling';
 else if(/宝石|黑宝石|光芒石|太阳石|月亮石|红玛瑙|舍利子|神秘石|翡翠石/.test(q)&&(ordinarySynthesisIntent(q)||/镶嵌|怎么打|哪里打|自己打|打宝石|失败|技能/.test(q)))key='gem_operations';
 else if(/神兽|命魂玉|灵尘|魔王|火云术|三昧真火|飞砂走石|宠装|珍珠|炼兽笼|强身|仙露|灵性|专注|花果|凌波|藏宝阁|值多少钱|购号|买号|收益|赚|回本|星辉|宠修|修炼果|降修|飞升/.test(q)){
  if(/神兽/.test(q))hostRef='beast-purchase-decisions.md';else if(/命魂玉|灵尘/.test(q))hostRef='jade-decision-boundaries.md';else if(/魔王|火云术|三昧真火|飞砂走石/.test(q))hostRef='beginner-demon-guide.md';else if(/宠装|珍珠|炼兽笼/.test(q))hostRef='pet-maintenance-and-leveling.md';else if(/星辉|宠修|修炼果|降修|飞升|金丹/.test(q))hostRef='verified-routes.md';else if(/藏宝阁|值多少钱|购号|买号|收益|赚|回本/.test(q))hostRef='decision-calculators.md';else hostRef='current-game-decisions.md';
 }else if(/同时|跨系统|多个目标|下一笔|先花|先升|先做|整体预算|分配预算/.test(q))key='portfolio';
 else if(/宝石|黑宝石|光芒石|太阳石|月亮石|红玛瑙|舍利子|神秘石|翡翠石/.test(q))key='gem';
 else if(/修炼|点修|攻修|法修|防修|抗法|猎术/.test(q))key='training';
 else if(/成品|卖旧|替换|自升|自己升|自己打|换成/.test(q))key='replace';
 else if(/装备|面板|配装|速度|法伤|伤害|鞋子|武器|项链/.test(q))key='equipment';
 else if(/总预算|预算|预留/.test(q))key='portfolio';
 if(key==='host'&&/金丹/.test(q)&&!hostRef)hostRef='verified-routes.md';
 const r=routes[key],out={route:key,title:r.title,advice:[...r.advice],questions:[],links:[{href:r.href,label:'不携带字段，'+r.label},{href:hostRef?'../references/'+hostRef:r.reference,label:'查看本地用法与边界'}],citations:[],fields:[],missing:[],issues:[],status:'guided',handoff:null};
 if(groundedGuidance(key,q,out))return out;
 if(key==='host'){out.questions=[...r.questions];out.advice.unshift(hostRef?'已找到相关的包内资料。先读适用条件；它不代表当前所有机制都已验证。':'暂时无法可靠识别这个问题的计算路径。下方仍可直接选择工具，不根据关键词替你编造建议。');if(/魔王|火云术|三昧真火|飞砂走石/.test(q))out.questions=['火云术现在多少级？','正在做什么任务？'];return out;}
 if(key==='training'&&/金丹|道具/.test(q))out.advice.push('你还提到了经验道具。本页只先算普通修炼基准；道具经验、价格与混用资格未自动提取。继续普通表单后，可主动切换混用路线并逐项核对这些信息。');
 const extracted=extract(q,key);out.fields=extracted.fields;out.candidates=extracted.candidates;out.issues=extracted.issues;
 const values=Object.fromEntries(out.fields.map(f=>[f.key,f.value]));out.budgetCurrencyUnknown=!!values.budget&&!extracted.budgetCurrencyConfirmed;out.untransferredKeys=out.budgetCurrencyUnknown&&values.currency?['budget']:[];
 const required=key==='training'?['type','currentLevel','targetLevel','currentProgressXp','confirmedCap']:key==='gem'?['gemType','currentForge','targetForge','slot','equipmentLevel']:key==='portfolio'?['budget','currency','reserve']:[];
 out.missing=required.filter(k=>!Object.hasOwn(values,k));if(['training','gem'].includes(key)&&values.budget&&!values.currency)out.missing.push('currency');
 function ask(keys,message){if(keys.some(k=>out.missing.includes(k)))out.questions.push(message);}
 if(key==='training'){
  ask(['type'],'这次采用哪一种普通修炼？');ask(['currentLevel','targetLevel'],out.missing.includes('currentLevel')&&out.missing.includes('targetLevel')?'当前修炼等级与目标等级分别是多少？':out.missing.includes('currentLevel')?'当前修炼等级是多少？':'目标修炼等级是多少？');
  ask(['currentProgressXp'],'本级已经有多少经验？没有也请明确填写0。');ask(['confirmedCap'],'游戏内已确认的修炼上限是多少？');
 }else if(key==='gem'){
  ask(['gemType'],'这次新增哪一种宝石？');ask(['currentForge','targetForge'],out.missing.includes('currentForge')&&out.missing.includes('targetForge')?'当前锻数与目标锻数分别是多少？':out.missing.includes('currentForge')?'当前锻数是多少？':'目标锻数是多少？');
  ask(['slot','equipmentLevel'],out.missing.includes('slot')&&out.missing.includes('equipmentLevel')?'装备部位和装备原始等级是什么？':out.missing.includes('slot')?'装备部位是什么？':'装备原始等级是多少？');
 }else if(key==='portfolio'){
  ask(['budget','currency'],out.missing.includes('budget')&&out.missing.includes('currency')?'这次已经可用的预算是多少，用哪种货币？':out.missing.includes('budget')?'这次已经可用的总预算是多少？':'这笔预算用哪种货币？');ask(['reserve'],'必须保留多少余额？没有预留也请明确填写0。');out.questions.push('这次有哪些要达到的明确目标？');
 }else out.questions=[...r.questions].filter(x=>!(/花多少/.test(x)&&values.budget));
 if(['training','gem'].includes(key)&&values.budget&&!values.currency)out.questions.push('这笔预算用哪种货币？未确认前不比较能否负担。');
 if(out.budgetCurrencyUnknown&&values.currency){out.questions.push('这笔预算本身用哪种货币？宝石报价或预留的货币不能自动当作预算货币。');out.advice.push('预算金额已识别，但其货币尚未确认，所以暂不携带预算金额，也不比较预算是否足够；明确给出的报价或预留货币仍按原文保留。');}
 if(out.issues.length){out.status=out.issues.some(x=>x.code.startsWith('invalid_'))?'needs_correction':'needs_review';out.advice.unshift(...out.issues.map(x=>x.message));out.questions=out.issues.map(x=>x.message);return out;}
 try{
  if(key==='training'&&['type','currentLevel','targetLevel','currentProgressXp','confirmedCap'].every(k=>Object.hasOwn(values,k))&&Resources){
   const v=Resources.cultivation(Object.fromEntries(['type','currentLevel','targetLevel','currentProgressXp','confirmedCap'].map(k=>[k,values[k]])));out.result=v;out.citations=v.citations;out.status='conditional_result';
   out.advice.unshift('按你提供的信息：'+v.typeLabel+' '+v.currentLevel+' → '+v.targetLevel+'级，本级已有 '+v.currentProgressXp+'经验，上限 '+v.confirmedCap+'级。尚需 '+v.requiredXp+'经验，普通购买 '+v.purchases+'次，游戏币 '+v.costLiang+'两，资材 '+v.materialsConsumed+'。','这只计算普通修炼规则费用；角色与帮派资格仍需在游戏内核对。不会推定道具经验、市场价或混用资格。');
  }else if(key==='training'){out.status='needs_information';out.advice.unshift('已提供的字段如下；缺项保持空白。未给出本级经验或上限时，不用0经验或目标等级代替，也不先报费用。');}
  if(key==='gem'&&['gemType','currentForge','targetForge'].every(k=>Object.hasOwn(values,k))&&Resources){
   const v=Resources.gems({gemType:values.gemType,currentForge:values.currentForge,targetForge:values.targetForge,quotes:{}});out.result=v;out.citations=v.citations;out.status='conditional_result';out.advice.unshift('按这一组宝石与锻数做材料试算：'+v.gemName+' '+v.currentForge+' → '+v.targetForge+'段，各新增等级需一颗对应等级石；合计一级材料下限 '+v.baseUnitsLowerBound+' 颗。目标等级单颗下限为 '+v.targetStoneBaseUnitsLowerBound+' 颗。','这只是材料下限，不含合成损耗、费用、库存抵扣或市场价格，也不证明装备可以镶嵌。');
  }
 }catch(error){out.advice.unshift('这组等级暂不能计算：'+error.message);out.status='needs_correction';out.issues.push({code:'calculator',message:error.message});return out;}
 if(key==='gem'&&out.result&&out.fields.some(f=>/^gradeQuote/.test(f.key))){
  const micros=x=>{const[a,b='']=x.split('.');return BigInt(a)*1000000n+BigInt(b.padEnd(6,'0'));},show=n=>{const tail=String(n%1000000n).padStart(6,'0').replace(/0+$/,'');return String(n/1000000n)+(tail?'.'+tail:'');};
  let total=0n;const missingGrades=[];
  for(let g=Number(values.currentForge)+1;g<=Number(values.targetForge);g++){const k='gradeQuote'+g;if(Object.hasOwn(values,k))total+=micros(values[k]);else missingGrades.push(String(g));}
  const adjustmentReview=/库存|自有材料|(?:已?有|现有|自有).{0,12}(?:颗|枚|宝石|材料)|手上.{0,12}(?:颗|枚|宝石)|仓库|合成费|手续费|额外费|加工费|体力费|损耗/.test(q);
  out.gemQuoteComparison={currency:'两',total:missingGrades.length||adjustmentReview?null:show(total),knownSubtotal:show(total),missingGrades,requiresInventoryFeeReview:adjustmentReview};
  if(adjustmentReview)out.advice.push('你还提供了库存或费用信息，这个入口尚未提取其抵扣和费用明细，因此不报这次需要新增多少现金。已识别的逐级报价仍会携带；请在下一页核对库存与费用后再算。');
  else out.advice.push(missingGrades.length?'已提供的新增等级报价小计 '+show(total)+'两；还缺 '+missingGrades.join('、')+'级报价，总价保持未知。':'按你逐项给出的报价，全部新增等级各买1颗合计 '+show(total)+'两。');
  out.advice.push('该报价算术未抵已有库存，也未加合成、手续等费用；报价的区服、观察日期和具体来源仍需在下一页核对，不代表已核验的当前市价。');
 }
 if(key==='training'&&out.result&&values.budget){
  if(values.currency==='两'&&!out.budgetCurrencyUnknown){
   const micros=x=>{const[a,b='']=x.split('.');return BigInt(a)*1000000n+BigInt(b.padEnd(6,'0'));},cash=micros(values.budget),cost=micros(out.result.costLiang),hasReserve=Object.hasOwn(values,'reserve'),reserve=hasReserve?micros(values.reserve):null,available=reserve===null?cash:cash-reserve,diff=available-cost;
   const show=x=>{const n=x<0n?-x:x,tail=String(n%1000000n).padStart(6,'0').replace(/0+$/,'');return (x<0n?'-':'')+String(n/1000000n)+(tail?'.'+tail:'');};
   out.budgetComparison={currency:'两',budget:values.budget,cost:out.result.costLiang,reserve:hasReserve?values.reserve:null,available:show(available),withinBudget:diff>=0n,difference:show(diff<0n?-diff:diff)};
   if(reserve!==null&&reserve>cash)out.advice.push('预算 '+values.budget+'两，明确预留 '+values.reserve+'两；预留已超过预算，无法安排这笔修炼支出，请核对预算或预留。');
   else out.advice.push((hasReserve?'总预算 '+values.budget+'两，扣除明确预留 '+values.reserve+'两，可动用 '+show(available)+'两。':'仅按给出的总预算 '+values.budget+'两作算术比较；未提供预留金额，以下余款不代表可自由支配现金。')+(diff>=0n?'普通修炼费用可被这笔金额覆盖，扣除后剩 '+show(diff)+'两。':'普通修炼费用还差 '+show(-diff)+'两。'));
  }else out.advice.push(out.budgetCurrencyUnknown?'预算货币未确认，不根据报价或预留单位推定预算币种，也不判断能否负担。':values.currency?'你的预算以'+values.currency+'计，修炼规则费用以游戏币两计；不自动换算，也不判断预算是否足够。':'已识别预算金额 '+values.budget+'，货币未提供；不判断能否负担，也不把金额默认当作游戏币。');
 }
 if(out.status==='conditional_result')out.advice.push('计算只使用上方文字中明确提供的字段；没有将它保存为已独立核实的账号事实。');
 const hunting=key==='training'&&values.type==='hunting';
 if(hunting){out.links[0]={href:'equipment.html#resources-section',label:'不携带字段，打开普通资源工具'};out.advice.push('猎术使用普通资源工具；预算和预留只在本页展示，不传入普通资源表单。');}
 if(['training','gem','portfolio'].includes(key)&&out.fields.length&&Intake){
  try{const transferFields=hunting?out.fields.filter(f=>['type','currentLevel','targetLevel','currentProgressXp','confirmedCap'].includes(f.key)):out.fields.filter(f=>!out.untransferredKeys.includes(f.key)),payload=Intake.create(hunting?'resources':key==='portfolio'?'budget':key,transferFields.map(({key,value,source,scope})=>({key,value,source,scope})));out.handoff={payload,url:Intake.toURL(payload),label:hunting?'核对以上修炼字段，继续填写普通资源':key==='training'?'核对以上字段，继续填写普通修炼':key==='gem'?'核对以上字段，继续填写宝石计划':'核对以上字段，继续填写共同预算'};}
  catch(error){out.advice.push('字段暂不能携带到表单：'+error.message);out.status='needs_correction';out.issues.push({code:'handoff',message:error.message});}
 }
 return out;
}
function mount(doc){
 const input=doc.getElementById('question'),result=doc.getElementById('guide-result');if(!input||!result)return null;
 const el=(tag,text)=>{const n=doc.createElement(tag);n.textContent=text;n.className='';return n;};
 function show(){
  result.textContent='';let r;try{r=analyze(input.value);}catch(error){result.append(el('p',error.message));return;}
  result.append(el('h3',r.title));r.advice.forEach(x=>result.append(el('p',x)));
  const fields=r.issues.length&&r.candidates?r.candidates:r.fields;
  if(fields.length||r.missing.length){const review=el('section','');review.className='guide-review';review.append(el('h4',r.issues.length?'候选字段：有歧义，暂不携带':'先核对从原文识别的字段'));const list=el('ul','');
   fields.forEach(f=>{const row=el('li','');row.append(el('strong',f.label+'：'+displayValue(f)+(r.untransferredKeys&&r.untransferredKeys.includes(f.key)?'（货币未确认，暂不携带）':'')));const source=el('span','原文：'+f.source.text+'（第 '+(f.source.start+1)+'–'+f.source.end+' 字符）');source.className='guide-source';row.append(source);list.append(row);});
   r.missing.forEach(k=>{const row=el('li',LABELS[k]+'：未提供，表单保持空白');row.className='guide-missing';list.append(row);});review.append(list);result.append(review);
  }
  if(r.handoff){const privacy=el('p','继续只把上面列出的字段和短原文片段放入本地页面链接片段，不发送网络请求，也不写入本地存储。链接可能留在浏览器历史中；复制或分享链接会包含这些字段。下一页仍需确认应用；不想携带可用下方普通链接。');privacy.className='guide-privacy';result.append(privacy);if(r.route==='training'&&r.handoff.payload.route!=='resources')result.append(el('p','继续时选择“只算普通修炼”工作流；这是本次工具选择，不是从原文推断出的账号事实。'));const a=el('a',r.handoff.label);a.href=r.handoff.url;a.className='guide-link guide-continue';result.append(a);}
  if(r.questions.length){result.append(el('strong',r.issues.length?'请先明确：':'还需要补充：'));const list=el('ol','');r.questions.forEach(x=>list.append(el('li',x)));result.append(list);}
  const links=el('p','');r.links.forEach(x=>{const a=el('a',x.label);a.href=x.href;a.className='guide-link';links.append(a);});result.append(links);
  r.citations.forEach(c=>{if(!/^https:\/\/xyq\.163\.com\//.test(c.url))return;const p=el('p',''),a=el('a',c.title+'（点击联网查看）');a.href=c.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);p.append(el('span',' · 包内核对日 '+c.checkedDate));result.append(p);});return r;
 }
 doc.getElementById('guide-submit').addEventListener('click',show);doc.getElementById('guide-clear').addEventListener('click',()=>{input.value='';result.textContent='';input.focus();});input.addEventListener('input',()=>{result.textContent='问题已变化，请重新识别并核对字段。';});return{show};
}
function displayValue(field){if(field.key==='type'){const t=Resources.cultivationTypes.find(x=>x.id===field.value);if(t)return t.name;}if(field.key==='gemType'){const t=Resources.gemTypes.find(x=>x.id===field.value);if(t)return t.name;}return field.value;}
return {analyze,extract,mount,routes};
}));
