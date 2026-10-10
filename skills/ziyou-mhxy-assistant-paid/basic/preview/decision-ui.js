/* Original offline, blank-first decision UI. No implicit market prices. */
(function(root,factory){
  'use strict';
  if(typeof module==='object'&&module.exports)module.exports=factory(require('./decisions.js'),require('./engine.js'));
  else {root.MHXYDecisionUI=factory(root.MHXYDecisions,root.MHXYEngine);if(root.document)root.MHXYDecisionUI.mount(root.document,root);}
}(typeof globalThis!=='undefined'?globalThis:this,function(Decision,Engine){
  'use strict';
  const FORMAT='mhxy-decision-draft';
  const MODES=['unknown','none','details'];
  const kinds=[['','请选择报价类型'],['asking','卖方挂牌 / 要价'],['sold','已成交记录'],['user_quote','人工询价记录'],['estimate','明确假设 / 估计']];
  const eligibility=[['unknown','尚未核对资格与目标'],['confirmed','已核对资格，并能达到同一目标'],['ineligible','不满足资格或目标']];
  const clone=v=>JSON.parse(JSON.stringify(v));
  const record=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  function dateToday(){const d=new Date();return[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
  const newQuote=()=>({amount:'',source:'',observed_on:'',kind:'',server:'',currency:''});
  const newLine=label=>({label,quantity:'1',quote:newQuote()});
  function blank(){return{format:FORMAT,version:'1',mode:'real',target:'',context:{server:'',currency:'',as_of:dateToday(),max_age_days:'7'},self:{eligible:'unknown',purchases:[newLine('升级材料合计')],purchasesMode:'details',feesMode:'unknown',fees:[newLine('自升额外费用')],ownedMode:'unknown',owned:[newLine('自有材料机会成本')]},replacement:{eligible:'unknown',purchase:newQuote(),feesMode:'unknown',fees:[newLine('购入额外费用')],resaleMode:'unknown',resale:newQuote(),resaleFeesMode:'unknown',resaleFees:[newLine('旧物出售费用')]},sunk_cost:'',notes:''};}
  function demo(){const d=blank();d.mode='demo';d.target='纯合成：两条路线均达到我指定的相同装备目标';d.context={server:'纯合成演示区',currency:'演示单位',as_of:'2026-10-06',max_age_days:'7'};const q=(amount,kind='estimate')=>({amount,source:'纯合成教学数字，不是真实报价',observed_on:'2026-10-06',kind,server:d.context.server,currency:d.context.currency});d.self.eligible='confirmed';d.replacement.eligible='confirmed';d.self.purchases=[{label:'合成新增材料',quantity:'1',quote:q('800.25')}];d.self.feesMode='details';d.self.fees=[{label:'合成加工费用',quantity:'1',quote:q('20')}];d.self.ownedMode='details';d.self.owned=[{label:'合成已有材料其他用途价值',quantity:'1',quote:q('120')}];d.replacement.purchase=q('1250.75','asking');d.replacement.feesMode='details';d.replacement.fees=[{label:'合成购入费用',quantity:'1',quote:q('30')}];d.replacement.resaleMode='conditional';d.replacement.resale=q('400','asking');d.replacement.resaleFeesMode='details';d.replacement.resaleFees=[{label:'合成出售费用',quantity:'1',quote:q('20')}];d.sunk_cost='2000';d.notes='此例用于区分现金与经济成本。旧物尚未卖出，不能拿假定卖出收入抵购入前备款。';return d;}
  function keys(o,required){if(!record(o)||Object.keys(o).length!==required.length||required.some(k=>!Object.hasOwn(o,k)))throw new Error('草稿结构不匹配，请打开本工具保存的草稿');}
  function str(v,max=1000){if(typeof v!=='string'||v.length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v))throw new Error('草稿文字格式无效或过长');}
  function validateDraft(d){
    keys(d,['format','version','mode','target','context','self','replacement','sunk_cost','notes']);
    if(d.format!==FORMAT||d.version!=='1'||!['demo','real'].includes(d.mode))throw new Error('不是支持的自升 / 替换草稿，原输入未改变');
    str(d.target);str(d.notes,3000);str(d.sunk_cost,32);
    keys(d.context,['server','currency','as_of','max_age_days']);for(const k of Object.keys(d.context))str(d.context[k],k==='server'?100:k==='currency'?40:10);
    const q=v=>{keys(v,['amount','source','observed_on','kind','server','currency']);for(const k of Object.keys(v))str(v[k],k==='amount'?32:k==='observed_on'?10:k==='server'?100:k==='currency'?40:1000);if(!['',...kinds.slice(1).map(x=>x[0])].includes(v.kind))throw new Error('草稿报价类型无效');};
    const lines=v=>{if(!Array.isArray(v)||v.length>200)throw new Error('每组最多 200 行');for(const x of v){keys(x,['label','quantity','quote']);str(x.label);str(x.quantity,32);q(x.quote);}};
    keys(d.self,['eligible','purchases','purchasesMode','feesMode','fees','ownedMode','owned']);keys(d.replacement,['eligible','purchase','feesMode','fees','resaleMode','resale','resaleFeesMode','resaleFees']);
    for(const route of[d.self,d.replacement])if(!eligibility.some(x=>x[0]===route.eligible))throw new Error('草稿资格状态无效');
    for(const m of[d.self.purchasesMode,d.self.feesMode,d.self.ownedMode,d.replacement.feesMode,d.replacement.resaleFeesMode])if(!MODES.includes(m))throw new Error('草稿费用状态无效');
    if(!['unknown','conditional','settled'].includes(d.replacement.resaleMode))throw new Error('草稿出售状态无效');
    for(const l of[d.self.purchases,d.self.fees,d.self.owned,d.replacement.fees,d.replacement.resaleFees])lines(l);
    for(const[o,m,a]of[[d.self,'purchasesMode','purchases'],[d.self,'feesMode','fees'],[d.self,'ownedMode','owned'],[d.replacement,'feesMode','fees'],[d.replacement,'resaleFeesMode','resaleFees']])if(o[m]==='details'&&!o[a].length)throw new Error('已展开的明细组不能为空；没有费用时请明确选择“确认没有”');
    q(d.replacement.purchase);q(d.replacement.resale);return d;
  }
  function buildInput(d){
    validateDraft(d);
    function need(v,label){if(!v.trim())throw new Error('请填写'+label);if(/[\x00-\x1f]/.test(v))throw new Error(label+'不能包含换行或控制字符');return v;}
    function decimal(v,label){if(!/^-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?$/.test(v))throw new Error(label+'请填写普通非负十进制数，最多 6 位小数；不要用逗号、指数或单位');if(v.startsWith('-')&&!/^-0(?:\.0+)?$/.test(v))throw new Error(label+'不能为负数');const [a,b='']=v.replace('-','').split('.');if(BigInt(a)*1000000n+BigInt(b.padEnd(6,'0'))>1000000000000000000n)throw new Error(label+'不能超过 1,000,000,000,000');return v;}
    function validDate(v,label){need(v,label);if(!/^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(v)||Number.isNaN(Date.parse(v+'T00:00:00Z'))||new Date(v+'T00:00:00Z').toISOString().slice(0,10)!==v)throw new Error(label+'必须是真实的 YYYY-MM-DD 日期');return v;}
    need(d.target,'本次共同目标');need(d.context.server,'统一比较区服');need(d.context.currency,'统一比较货币');validDate(d.context.as_of,'比较基准日期');
    if(!/^(?:0|[1-9][0-9]{0,2})$/.test(d.context.max_age_days)||BigInt(d.context.max_age_days)>365n)throw new Error('报价有效天数请填写 0–365 的整数');
    const ctx={...d.context,max_age_days:parseInt(d.context.max_age_days,10)};
    function quote(q,label){if(q.amount.trim()==='')return null;decimal(q.amount,label+'金额');for(const[k,l]of[['source','来源'],['observed_on','观察日期'],['kind','类型'],['server','所属区服'],['currency','货币']])need(q[k],label+l);validDate(q.observed_on,label+'观察日期');if(q.observed_on>ctx.as_of)throw new Error(label+'观察日期晚于比较基准日，请核对');if(q.server!==ctx.server)throw new Error(label+'区服与本次比较不同，请核对；不会自动改写旧报价');if(q.currency!==ctx.currency)throw new Error(label+'货币与本次比较不同，请分别建立草稿');return clone(q);}
    const line=(l,i,label)=>({label:need(l.label,label+'第 '+(i+1)+' 行名称'),quantity:decimal(need(l.quantity,label+'数量'),label+'数量'),quote:quote(l.quote,l.label)});
    function group(mode,lines,label){if(mode==='none')return[];if(mode==='unknown')return[{label,quantity:'1',quote:null}];return lines.map((l,i)=>line(l,i,label));}
    const s=d.self,r=d.replacement;
    let sale=null;if(r.resaleMode!=='unknown'){const q=quote(r.resale,'旧物卖出价');if(!q)throw new Error('选择了条件出售 / 已结算，请填写卖出价；未知请切回“卖出金额未知”');if(r.resaleMode==='settled'&&q.kind!=='sold')throw new Error('已结算出售必须使用“已成交记录”，挂牌不是已收到的钱');sale={quote:q,status:r.resaleMode,fees:group(r.resaleFeesMode,r.resaleFees,'旧物出售费用')};}
    return{context:ctx,self_upgrade:{eligible:s.eligible,purchases:group(s.purchasesMode,s.purchases,'新增材料费用'),fees:group(s.feesMode,s.fees,'自升额外费用'),owned_materials:group(s.ownedMode,s.owned,'自有材料机会成本')},replacement:{eligible:r.eligible,purchase:quote(r.purchase,'成品购入报价'),fees:group(r.feesMode,r.fees,'购入额外费用'),old_item_resale:sale},sunk_cost:d.sunk_cost.trim()===''?null:decimal(d.sunk_cost,'历史投入')};
  }
  function dateContext(d,today=dateToday()){
    if(d.mode==='demo'||d.context.as_of===today)return '';
    return '本档案按 '+d.context.as_of+' 核价，今天是 '+today+'。这是历史或指定日期的条件结果；用于今天采购前，请先将核价日更新到今天并重新比较，原报价日期不会自动改写。';
  }
  function summary(result,input,d){
    const mode=d.mode==='demo'?'【纯合成演示 · 不是真实市价】':'【我的手动数据 · 未经独立核验】';
    const lines=[mode,'本次目标：'+d.target,'说明：资格与达到同一目标均为用户声明，不代表工具验证。'];
    if(!result.eligibility_confirmed)lines.push('资格或同一目标尚未确认：以下仅作费用算术，不能据此推荐路线。');
    lines.push(Decision.reportText(result,input));
    const calendar=dateContext(d);if(calendar)lines.unshift(calendar);
    if(d.notes)lines.push('我的备注：'+d.notes);
    lines.push('决定前请核实：同一目标与资格、报价有效性、全部必要费用，以及旧物能否按条件卖出。','不同区服、货币不得混算；未列费用、未来行情和战斗效果不在计算范围。');return lines.join('\n\n');
  }
  function mount(doc,env){
    env=env||globalThis;if(!Decision||!Engine)return null;
    let data=blank(),result=null,input=null,dirty=false,generation=0,calendarNotice=null;const controls=new Map();
    const $=id=>doc.getElementById(id);
    const n=(tag,text,cls)=>{const e=doc.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
    const clear=e=>{e.textContent='';};
    const status=(id,t,error=false)=>{const e=$(id);e.textContent=t;e.className='status'+(error?' error':'');};
    const button=(t,fn,cls)=>{const e=n('button',t,cls);e.type='button';e.addEventListener('click',fn);return e;};
    function changed(){dirty=true;generation++;result=null;input=null;$('decision-results').hidden=true;status('decision-live','输入已改变，请重新比较');status('decision-error','');status('decision-export-status','');}
    function field(label,o,k,path,opts={}){const w=n('label',label);const e=n(opts.choices?'select':opts.multiline?'textarea':'input');if(opts.choices){for(const[v,t]of opts.choices){const op=n('option',t);op.value=v;e.append(op);}}else{e.type=opts.type||'text';if(opts.numeric)e.setAttribute('inputmode','decimal');e.setAttribute('autocomplete','off');if(opts.placeholder)e.placeholder=opts.placeholder;}e.value=o[k];e.id='field-'+path.replace(/[^a-z0-9]/gi,'-');e.setAttribute('data-path',path);controls.set(path,e);w.append(e);if(opts.help)w.append(n('small',opts.help));e.addEventListener(opts.choices?'change':'input',()=>{o[k]=e.value;e.removeAttribute('aria-invalid');changed();if(opts.update){opts.update();if(opts.choices){const fresh=controls.get(path);if(fresh){let p=fresh.parentNode;while(p){if(String(p.tagName).toLowerCase()==='details')p.open=true;p=p.parentNode;}fresh.focus();}}}});return w;}
    function details(title,parent,open=false){const d=n('details');d.open=open;d.append(n('summary',title));const body=n('div');d.append(body);parent.append(d);return body;}
    function quoteFields(q,label,path,parent){
      parent.append(field(label,q,'amount',path+'.amount',{numeric:true,placeholder:'未知留空；确认免费才填 0',update:()=>{for(const key of['server','currency'])if(q.amount.trim()&&!q[key]){q[key]=data.context[key];const e=controls.get(path+'.'+key);if(e)e.value=q[key];}}}));
      const quoteComplete=!!(q.amount&&q.source&&q.observed_on&&q.kind&&q.server&&q.currency);
      const evidenceTitle='报价依据：来源、日期、类型与区服（有价格时必填）';
      const b=details(evidenceTitle,parent,!!q.amount&&!quoteComplete),g=n('div',undefined,'grid');
      g.append(field('报价类型',q,'kind',path+'.kind',{choices:kinds}),field('报价观察日期',q,'observed_on',path+'.observed_on',{type:'date'}),field('具体来源 / 明确假设',q,'source',path+'.source',{placeholder:'如商品编号、聊天记录日期或假设说明'}),field('报价所属区服',q,'server',path+'.server',{help:'录入金额时复制本次区服；之后不自动改写'}),field('报价货币',q,'currency',path+'.currency',{help:'与本次比较货币完全一致'}));b.append(g);
    }
    function linesEditor(parent,arr,path,baseLabel){
      arr.forEach((l,i)=>{const card=n('div',undefined,'line'),head=n('div',undefined,'line-head');head.append(n('span',l.label||baseLabel+' '+(i+1)));if(arr.length>1)head.append(button('移除此项',()=>{if(!env.confirm('移除此项及报价？'))return;arr.splice(i,1);changed();render();},'small remove'));card.append(head);quoteFields(l.quote,'金额 / 单价（数量 '+l.quantity+'）',path+'.'+i+'.quote',card);const b=details('名称与数量：合计金额按 1 份填写',card),g=n('div',undefined,'grid');g.append(field('项目名称',l,'label',path+'.'+i+'.label'),field('数量',l,'quantity',path+'.'+i+'.quantity',{numeric:true,help:'合计填 1；单价则填数量，不重复算整组材料'}));b.append(g);parent.append(card);});
      const a=n('div',undefined,'actions');const add=button('＋ 再加一项',()=>{if(arr.length>=200)return;arr.push(newLine(baseLabel+' '+(arr.length+1)));changed();render();const fresh=controls.get(path+'.'+(arr.length-1)+'.quote.amount');if(fresh)fresh.focus();},'small');add.disabled=arr.length>=200;a.append(add);parent.append(a);
    }
    function group(parent,route,modeKey,arrayKey,path,title,labels){
      parent.append(field(title,route,modeKey,path+'.'+modeKey,{choices:[['unknown',labels.unknown],['none',labels.none],['details',labels.details]],update:render}));
      if(route[modeKey]==='details')linesEditor(parent,route[arrayKey],path+'.'+arrayKey,title);
      else parent.append(n('p',route[modeKey]==='none'?'已明确确认本组不计新增金额。':'本组仍未知，相关总额会保留未知。','muted'));
    }
    const feeLabels={unknown:'尚未核对额外费用',none:'我确认本路线没有额外费用',details:'有费用，逐项填写'};
    function refreshCalendarWarning(){
      if(!calendarNotice)return;clear(calendarNotice);const calendar=dateContext(data);calendarNotice.hidden=!calendar;
      if(calendar){calendarNotice.append(n('p',calendar));calendarNotice.append(button('以今天为核价日重新比较',()=>{data.context.as_of=dateToday();changed();render();calculate();},'small'));}
    }
    function render(){
      controls.clear();for(const id of['decision-context','decision-self','decision-replacement','decision-extra'])clear($(id));
      $('decision-mode').textContent=data.mode==='demo'?'纯合成演示 · 修改后仍为演示':'我的手动数据';
      $('decision-mode-note').textContent=data.mode==='demo'?'价格、目标和资格为构造示例，请勿用于购买':'报价由你提供，未独立核实；关闭前请保存草稿';
      let p=$('decision-context');p.append(field('共同目标',data,'target','target',{placeholder:'如同底子项链达到指定段数，并保留我需要的属性',help:'请描述两条路线都要达到的同一目标；修改目标后，两条路线须重新核对',update:()=>{for(const route of ['self','replacement']){data[route].eligible='unknown';const c=controls.get(route+'.eligible');if(c)c.value='unknown';}status('decision-live','共同目标已变化，原报价保留，但两条路线的资格与达标声明已改为待核对。');}}));
      calendarNotice=n('div',undefined,'notice');p.append(calendarNotice);refreshCalendarWarning();
      const g=n('div',undefined,'grid');g.append(field('本次比较区服',data.context,'server','context.server',{placeholder:'请填写具体区服'}),field('本次统一货币 / 单位',data.context,'currency','context.currency',{placeholder:'如人民币元、梦幻币两（不要混用）'}));p.append(g);const c=details('比较日期与报价有效天数',p),cg=n('div',undefined,'grid');cg.append(field('比较基准日期',data.context,'as_of','context.as_of',{type:'date',update:refreshCalendarWarning}),field('报价有效天数',data.context,'max_age_days','context.max_age_days',{numeric:true,help:'0–365；这是你的核价窗口，不代表价格保证'}));c.append(cg);
      p=$('decision-self');p.append(field('A 路线资格与目标',data.self,'eligible','self.eligible',{choices:eligibility}));group(p,data.self,'purchasesMode','purchases','self','新增购买材料',{unknown:'材料费用暂不清楚',none:'我确认不需要新购材料',details:'填写材料合计 / 分项报价'});const sf=details('补充：加工、手续费等额外支出',p,data.self.feesMode==='details');group(sf,data.self,'feesMode','fees','self','自升额外费用',feeLabels);const so=details('补充：会用到已经拥有的材料吗？',p,data.self.ownedMode==='details');so.append(n('p','自有材料不会再收一次现金。经济成本需考虑它可用于别处的价值；不清楚就留空。','muted'));group(so,data.self,'ownedMode','owned','self','自有材料机会成本',{unknown:'还没核对自有材料的机会成本',none:'我确认不耗用自有材料 / 机会成本为零',details:'填写耗用自有材料的其他用途价值'});
      p=$('decision-replacement');p.append(field('B 路线资格与目标',data.replacement,'eligible','replacement.eligible',{choices:eligibility}));const rc=n('div',undefined,'line');quoteFields(data.replacement.purchase,'成品购入价格','replacement.purchase',rc);p.append(rc);const rf=details('补充：购入时还需要哪些费用？',p,data.replacement.feesMode==='details');group(rf,data.replacement,'feesMode','fees','replacement','购入额外费用',feeLabels);const rs=details('补充：旧物出售与回收款',p,data.replacement.resaleMode!=='unknown');rs.append(n('p','不出售或卖出金额未知时，保留未知回收款。若明确打算保留旧物，请比较购入前备款，勿把它当成出售后的净成本。','muted'));rs.append(field('旧物卖出状态',data.replacement,'resaleMode','replacement.resaleMode',{choices:[['unknown','卖出金额未知 / 暂不出售'],['conditional','条件出售：尚未收到款'],['settled','已成交并结算']],update:render}));if(data.replacement.resaleMode!=='unknown'){quoteFields(data.replacement.resale,'旧物卖出总价（未扣费用）','replacement.resale',rs);group(rs,data.replacement,'resaleFeesMode','resaleFees','replacement','旧物出售费用',feeLabels);}
      p=$('decision-extra');const e=details('记录以前投入的钱与备注（选填，不计入本次成本）',p,!!data.sunk_cost||!!data.notes);e.append(field('历史投入 / 沉没成本',data,'sunk_cost','sunk_cost',{numeric:true,help:'仅留存记录，不重新计费，不当成旧物能卖出的价格'}),field('给自己的备注',data,'notes','notes',{multiline:true,placeholder:'例如还要核对什么，哪些费用不在这份比较里'}));
    }
    function mayReplace(){return !dirty||env.confirm('当前未保存输入会被替换。建议先保存草稿，确定继续吗？');}
    function replace(next){data=next;dirty=false;generation++;result=null;input=null;$('decision-results').hidden=true;render();status('decision-error','');status('decision-live','填写后点击比较；未知不会自动变成 0');status('decision-export-status','');}
    function revealRequired(){
      let first=null;const required=['target','context.server','context.currency','context.as_of'];
      for(const [path,e]of controls){e.removeAttribute('aria-invalid');if(path.endsWith('.amount')&&e.value.trim())for(const key of['source','observed_on','kind','server','currency'])required.push(path.slice(0,-6)+key);}
      for(const path of required){const e=controls.get(path);if(e&&!e.value.trim()){e.setAttribute('aria-invalid','true');if(!first)first=e;let p=e.parentNode;while(p){if(String(p.tagName).toLowerCase()==='details')p.open=true;p=p.parentNode;}}}return first;
    }
    function calculate(){
      const firstMissing=revealRequired();result=null;input=null;$('decision-results').hidden=true;
      try{input=buildInput(data);result=Decision.compareUpgrade(input);renderResult();status('decision-error','');status('decision-live',data.mode==='demo'?'演示计算完成，不是购买建议':'计算完成，请核对结果里的条件与未知项');$('decision-results').focus();if($('decision-results').scrollIntoView)$('decision-results').scrollIntoView({block:'start',behavior:'smooth'});return result;}
      catch(e){input=null;result=null;status('decision-error','暂不能比较：'+e.message+'。修正后重新点击比较，输入会保留。',true);if(firstMissing)firstMissing.focus();else $('decision-error').focus();return null;}
    }
    function renderResult(){
      const p=$('decision-result-body');clear(p);const r=result,unit=' '+r.currency,amount=v=>v===null?'未知':v+unit;
      p.append(n('div',data.mode==='demo'?'纯合成演示：所有金额与判断条件都为教学构造。':'手动输入结果：报价与资格尚未经独立核验。','notice info'));
      p.append(n('p','本次共同目标：'+data.target,'target-card'));
      const cards=n('div',undefined,'result-grid');
      for(const[title,value,help,cls]of[['A · 自升新增现金',r.self_upgrade.cash_outlay,'材料新购 + 自升费用，不含已购材料的历史花费',''],['B · 购入前需备现金',r.replacement.upfront_cash_required,'购入价格 + 购入费用；不预扣尚未卖出的旧物收入','tint'],['A · 计入机会成本后',r.self_upgrade.economic_cost,'新增现金 + 本次耗用的自有材料机会成本',''],['B · 旧物卖出后的条件净成本',r.replacement.net_cost_if_resale_occurs,'仅当卖出总价、出售费用与成交条件均成立','']]){const m=n('article',undefined,'metric '+cls);m.append(n('small',title),n('strong',amount(value)),n('p',help));cards.append(m);}p.append(cards);
      const warnings=[];const calendar=dateContext(data);if(calendar)warnings.push(calendar);if(!r.eligibility_confirmed)warnings.push('资格或同一目标尚未确认：以下仅作费用算术，不能据此推荐路线。');if(r.comparison_has_stale_quotes)warnings.push('有报价超出本次有效窗口，请先重新核价。');if(r.replacement.resale_status!=='settled')warnings.push('旧物尚未结算：卖出价是条件或未知，不能抵购入前的备款。');if(r.unknowns.length)warnings.push('仍需补齐：'+r.unknowns.map(x=>x==='replacement purchase'?'成品购入报价':x==='net old-item resale'?'旧物净回收款':x).join('、'));
      if(warnings.length){const w=n('div',undefined,'notice');warnings.forEach(t=>w.append(n('p',t)));p.append(w);}
      const ranking={self_upgrade:'自升的费用更低',replacement:'替换的费用更低',tie:'两条路线费用相同',unknown:'资料不足，暂不能比较'};
      const verdict=n('div',undefined,'panel');verdict.append(n('h3','在同一目标且出售条件成立的前提下'),n('p','按新增现金净成本：'+ranking[r.cash_cost_comparison_if_resale_occurs]),n('p','计入机会成本：'+ranking[r.economic_cost_comparison_if_resale_occurs]));
      if(r.replacement_purchase_break_even_cash!==null)verdict.append(n('p','按现金口径，成品购入价 ≤ '+amount(r.replacement_purchase_break_even_cash)+' 时，替换成本不高于自升。','muted'));
      if(r.replacement_purchase_break_even_economic!==null)verdict.append(n('p','计入机会成本后，成品购入价界线为 '+amount(r.replacement_purchase_break_even_economic)+'。','muted'));
      verdict.append(n('p','界线已经考虑输入的购入费用与旧物净回收款；它不是市场估值或建议出价。','muted'));p.append(verdict);
      const evidence=details('展开完整决策说明、报价明细与风险',p);const text=n('pre',summary(r,input,data),'summary');evidence.append(text);$('decision-results').hidden=false;
    }
    function download(content,name,type){const blob=new env.Blob([content],{type}),url=env.URL.createObjectURL(blob),a=n('a');a.href=url;a.download=name;doc.body.append(a);a.click();a.remove();env.setTimeout(()=>env.URL.revokeObjectURL(url),1000);}
    function save(){try{validateDraft(data);const text=JSON.stringify(data,null,2)+'\n';Engine.parse(text,1000000);download(text,'mhxy-decision-'+data.mode+'-draft.json','application/json;charset=utf-8');dirty=false;status('decision-file-status','已生成草稿下载，请确认文件已保存在本地；草稿包含来源与备注。');return text;}catch(e){status('decision-file-status','草稿未生成：'+e.message,true);return false;}}
    function load(raw,name,skipConfirm=false){try{if(raw.length>1000000)throw new Error('草稿超过 1 MB');const parsed=Engine.parse(raw,1000000);const next=validateDraft(parsed);if(!skipConfirm&&!mayReplace())return false;replace(clone(next));status('decision-file-status','已打开 '+name+'；保持原有演示 / 我的数据标记');return true;}catch(e){status('decision-file-status','草稿未打开：'+e.message+'。当前输入保持不变。',true);return false;}}
    function exportResult(kind){if(!result||!input){status('decision-export-status','请先重新比较，不能导出过期结果。',true);return false;}try{const content=kind==='text'?summary(result,input,data):JSON.stringify({format:'mhxy-decision-report',version:'1',mode:data.mode,target:data.target,input,result,notes:data.notes},null,2);download(content,'mhxy-decision-'+data.mode+(kind==='text'?'.txt':'.json'),kind==='text'?'text/plain;charset=utf-8':'application/json;charset=utf-8');status('decision-export-status','已生成决策说明下载；请一并保留报价依据。');return content;}catch(e){status('decision-export-status','文件未生成：'+e.message+'。当前输入与结果保持不变，可以重试或保存草稿。',true);return false;}}
    $('decision-demo').addEventListener('click',()=>{if(mayReplace()){replace(demo());status('decision-file-status','已载入纯合成演示；改动它仍保留演示标记。');}});
    $('decision-blank').addEventListener('click',()=>{if(mayReplace()){replace(blank());status('decision-file-status','已从空白开始；没有复制演示价格。');}});
    $('decision-save').addEventListener('click',save);for(const id of['decision-calculate','decision-calculate-bottom'])$(id).addEventListener('click',calculate);
    for(const kind of['text','json'])$('decision-export-'+kind).addEventListener('click',()=>exportResult(kind));
    $('decision-import').addEventListener('change',event=>{const file=event.target.files&&event.target.files[0],selection=++generation;event.target.value='';if(!file)return;if(file.size>1000000){status('decision-file-status','文件超过 1 MB，未读取；当前输入保持不变。',true);return;}if(!mayReplace())return;const token=selection,reader=new env.FileReader();reader.onload=()=>{if(token!==generation){status('decision-file-status','读取期间输入已改变，未覆盖当前草稿。请重新打开。',true);return;}load(String(reader.result),file.name,true);};reader.onerror=()=>{if(token===generation)status('decision-file-status','读取失败，当前输入保持不变；请重新选择文件。',true);};reader.readAsText(file,'UTF-8');});
    if(env.addEventListener)env.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
    render();$('decision-startup').hidden=true;
    return{getData:()=>data,getControls:()=>controls,getResult:()=>result,getState:()=>({dirty,generation}),calculate,save,load,exportResult,render};
  }
  return{blank,demo,buildInput,validateDraft,dateContext,summary,mount};
}));
