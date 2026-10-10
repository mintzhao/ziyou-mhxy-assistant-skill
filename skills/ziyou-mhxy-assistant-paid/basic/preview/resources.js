/* Original offline rule arithmetic. Provenance: references/resource-calculators.md. */
(function (root) {
  'use strict';
  const checkedDate = '2026-10-06';
  const sourceMap = {
    cultivation: {title: '官方：人物修炼', url: 'https://xyq.163.com/introduce/zd008.html'},
    gems: {title: '官方：宝石', url: 'https://xyq.163.com/introduce/dj008.html'},
    amendment: {title: '官方：2024-05-21 宝石合成调整', url: 'https://xyq.163.com/news/20240520/4999_1156134.html'}
  };
  const gemTypes = [
    {id:'radiance',name:'光芒石',stat:'hp',statLabel:'气血',perStep:'40',slots:['铠甲','腰带']},
    {id:'sun',name:'太阳石',stat:'damage',statLabel:'伤害属性',perStep:'8',slots:['武器','头盔']},
    {id:'moon',name:'月亮石',stat:'defense',statLabel:'防御',perStep:'12',slots:['铠甲','头盔']},
    {id:'black',name:'黑宝石',stat:'speed',statLabel:'速度',perStep:'8',slots:['腰带','鞋子']},
    {id:'agate',name:'红玛瑙',stat:'hit',statLabel:'命中',perStep:'25',slots:['武器','头盔']},
    {id:'relic',name:'舍利子',stat:'spirit',statLabel:'灵力',perStep:'6',slots:['铠甲','项链']},
    {id:'mystery',name:'神秘石',stat:'dodge',statLabel:'躲避',perStep:'20',slots:['武器','腰带','鞋子']},
    {id:'jade',name:'翡翠石',stat:'magic_defense',statLabel:'法术防御',perStep:'12',slots:['铠甲']}
  ];
  const extras = {12:[3,5,6],13:[9],14:[9,10],15:[9,12],16:[11,12,13],17:[15],18:[13,14,16],19:[15,16,17],20:[17,18,18]};
  const typeLabels = {attack:'攻击修炼',spell:'法术修炼',defense:'防御修炼',anti_spell:'抗法修炼',hunting:'猎术修炼'};
  const own = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
  function integer(value,label,min=0n,max=null) {
    if (!((typeof value === 'number' && Number.isSafeInteger(value)) || typeof value === 'string')) throw new Error(label+'必须是非负整数或整数字符串');
    const text = String(value).trim();
    if (!/^[0-9]{1,30}$/.test(text)) throw new Error(label+'必须是至多30位的非负整数');
    const result = BigInt(text);
    if (result < min || (max !== null && result > max)) throw new Error(label+'超出允许范围');
    return result;
  }
  function object(value,required,optional=[]) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('输入必须是对象');
    const unknown=Object.keys(value).filter(key=>!required.includes(key)&&!optional.includes(key));
    if(unknown.length) throw new Error('未知输入字段：'+unknown.sort().map(key=>"'"+key+"'").join(', '));
    const missing=required.filter(key=>!own(value,key));
    if(missing.length) throw new Error('缺少必填字段：'+missing.join(', '));
  }
  function sources(...names) { return names.map(name=>({...sourceMap[name],checkedDate})); }
  function stepXp(r) { return 10n*(r*r+3n*r+11n); }
  function cultivation(data) {
    object(data,['type','currentLevel','targetLevel','currentProgressXp','confirmedCap']);
    const kind = data.type;
    if (typeof kind!=='string' || !own(typeLabels,kind)) throw new Error('修炼类型无效');
    const limit = kind==='hunting' ? 20n : 25n;
    const current=integer(data.currentLevel,'当前修炼等级',0n,limit), target=integer(data.targetLevel,'目标修炼等级',0n,limit), cap=integer(data.confirmedCap,'已确认修炼上限',0n,limit);
    const progress=integer(data.currentProgressXp,'本级已有修炼经验');
    if (target<current) throw new Error('目标等级不能低于当前等级');
    if (current>cap || target>cap) throw new Error('当前或目标等级超过已确认上限；本工具不计算降修解锁路线');
    if ((current===limit && progress!==0n) || (current<limit && progress>=stepXp(current+1n))) throw new Error('本级已有经验必须小于下一等级所需经验；满级时填写0');
    let gross=0n; const steps=[];
    for(let r=current+1n;r<=target;r++) {const xp=stepXp(r);gross+=xp;steps.push({targetLevel:String(r),xp:String(xp)});}
    const applied=target>current?progress:0n,required=gross-applied,purchases=(required+9n)/10n,price=(kind==='defense'||kind==='anti_spell')?20000n:30000n;
    return {calculator:'normal_cultivation',scope:'梦幻西游电脑版时间服：普通帮派修炼',type:kind,typeLabel:typeLabels[kind],currentLevel:String(current),targetLevel:String(target),confirmedCap:String(cap),currentProgressXp:String(progress),grossXp:String(gross),progressAppliedXp:String(applied),requiredXp:String(required),purchases:String(purchases),purchasedXp:String(purchases*10n),surplusXp:String(purchases*10n-required),costPerPurchaseLiang:String(price),costLiang:String(purchases*price),materialsConsumed:String(purchases*5n),contributionConsumed:'0',requiredCharacterLevel:target?String(5n*target+20n):'0',requiredContributionExclusive:String(150n*target),requiredGuildMembershipDaysExclusive:'14',steps,
      explanations:['普通模式每次增加10点经验；金钱和帮派资材是消耗项，累计帮贡是门槛，不在本模式扣除。','官网表述为累计帮贡严格大于目标等级×150、入帮时间大于14天；还需本帮已开放对应修炼。','结果只适用于已确认上限内的普通修炼，不含快速兑换、租赁、降修、飞升、优惠或战斗效果。','多买的经验仅为算术余量；到上限时是否保留请以游戏内界面为准。'],citations:sources('cultivation'),checkedDate};
  }
  function gems(data) {
    object(data,['gemType','currentForge','targetForge'],['quotes']);
    const current=integer(data.currentForge,'当前锻炼等级',0n,20n),target=integer(data.targetForge,'目标锻炼等级',0n,20n);
    if(target<current) throw new Error('目标锻炼等级不能低于当前等级');
    const gem=gemTypes.find(x=>x.id===data.gemType);
    if(!gem) throw new Error('宝石类型无效');
    const quotes=own(data,'quotes')?data.quotes:{};
    if(!quotes || typeof quotes!=='object' || Array.isArray(quotes)) throw new Error('各级报价必须是对象');
    const parsed=Object.create(null);
    for(const [key,value] of Object.entries(quotes)) {const grade=String(integer(key,'报价等级',1n,20n));if(own(parsed,grade)) throw new Error('报价等级重复');parsed[grade]=integer(value,'宝石报价');}
    const units={1:1n};
    for(let g=2;g<=20;g++) units[g]=2n*units[g-1]+(extras[g]||[]).reduce((sum,x)=>sum+units[x],0n);
    let subtotal=0n,base=0n;const missing=[],steps=[];
    for(let g=current+1n;g<=target;g++) {const k=String(g),known=own(parsed,k);if(!known)missing.push(k);else subtotal+=parsed[k];base+=units[k];steps.push({grade:k,quoteLiang:known?String(parsed[k]):null,baseUnitsLowerBound:String(units[k])});}
    return {calculator:'ordinary_gems',scope:'梦幻西游电脑版时间服：普通宝石',gemType:gem.id,gemName:gem.name,currentForge:String(current),targetForge:String(target),addedForgeSteps:String(target-current),quoteTotalLiang:missing.length?null:String(subtotal),knownQuoteSubtotalLiang:String(subtotal),missingQuoteGrades:missing,baseUnitsLowerBound:String(base),targetStoneBaseUnitsLowerBound:target?String(units[String(target)]):'0',rawStatDelta:{key:gem.stat,label:gem.statLabel,value:String((target-current)*BigInt(gem.perStep)),unit:'原始装备属性'},allowedSlots:[...gem.slots],steps,
      explanations:['逐级镶嵌，每一级都需要对应等级的同类宝石；报价合计使用全部新增等级，不只取最高一级。','材料下限按普通宝石两颗同级合成及2024-05-21额外材料规则递推；不含失败损耗、体力、手续费或库存抵扣。','材料下限不是预计花费；最高等级单颗材料量与本次全部锻炼材料量分开显示。','属性变化仅为宝石增加的原始装备属性，不是角色最终面板、实战伤害、治疗或生存提升。','使用前核对装备部位、最多两种宝石、装备等级/10锻炼上限及无级别例外；此函数不判定装备可用性。','本次新增锻炼全部使用所选宝石；报价单位为游戏币两，未知报价不按0计算。'],citations:sources('gems','amendment'),checkedDate};
  }
  const api=Object.freeze({cultivation,gems,checkedDate,cultivationTypes:Object.freeze(Object.entries(typeLabels).map(([id,name])=>Object.freeze({id,name}))),gemTypes:Object.freeze(gemTypes.map(x=>Object.freeze({...x,slots:Object.freeze([...x.slots])})))});
  if(typeof module!=='undefined' && module.exports) module.exports=api;
  if(root) root.MHXYResources=api;
})(typeof window!=='undefined'?window:(typeof globalThis!=='undefined'?globalThis:null));
