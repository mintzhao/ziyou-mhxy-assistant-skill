"""Read-only, edition-scoped repair guidance from dated official evidence.

No network, game control, purchases, automatic activation, or inferred current prices.
Full-server dates gate rollout; partial test announcements alone never enable rules.
"""
from pathlib import Path
import json
try:
    from . import decisions as d, resources
except ImportError:
    import decisions as d
    import resources

CHECKED = '2026-10-07'
EVIDENCE_PATH = Path(__file__).resolve().parents[1] / 'references/repair-route-sources.json'
EVIDENCE = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
SOURCES = {row['id']: row for row in EVIDENCE['sources']}
STONE_TYPES = {
    'damaged': ('破损的乾坤石', 80, 85, 10),
    'common': ('普通的乾坤石', 120, 125, 50),
    'luxury': ('奢华的乾坤石', 130, 135, 230),
    'warm': ('温润的乾坤石', 140, 145, 300),
    'refined': ('精致的乾坤石', 150, 145, 500),
    'exquisite': ('精美的乾坤石', 160, 145, 1000),
}

def integer(value, label, low=0, high=1000000000000):
    return resources._integer(value, label, low, high)

def optional_int(data, name, low=0, high=1000000000000):
    return None if data.get(name) is None else integer(data[name], name, low, high)

def state(data, name, allowed, default):
    value = data.get(name, default)
    if value not in allowed:
        raise ValueError(name + ' must be one of ' + '/'.join(allowed))
    return value

def citations(*ids):
    result=[]
    for key in dict.fromkeys(ids):
        s=SOURCES[key]
        result.append(dict(id=key,url=s['url'],published_on=s['publication_date'],
            effective_on=s['effective_test_date'], test_effective_on=s['effective_test_date'],
            all_server_effective_on=s['all_server_effective_date'],checked_date=s['retrieved_date'],
            edition_scope=s['edition_scope'],source_scope='official_with_full_release' if s['all_server_effective_date'] else 'historical_official_rule',
            snapshot_sha256=s['snapshot_sha256']))
    return result

def rollout(asof, test, full):
    return 'all_servers_released' if asof >= full else 'partial_server_test_only' if asof >= test else 'not_yet_effective'

def repair_guidance(data):
    d.fields(data, ('ruleset', 'equipment_kind', 'method'),
        ('equipment_id','equipment_level','equipment_slot','ordinary_skill_level','repair_failures',
         'material_id','material_level','current_durability','maximum_durability','observed_preview','as_of',
         'stone_state','stone_type','payment_preference'))
    if data['ruleset'] != 'pc_time':
        raise ValueError('ruleset must be pc_time; unknown/mobile/畅玩服 editions are not inferred')
    kind=state(data,'equipment_kind',('character','pet','unknown'),'unknown')
    method=state(data,'method',('ordinary','guild','pearl','heaven_bead','qiankun_stone','quick_repair','unknown'),'unknown')
    asof=d.day(data.get('as_of',CHECKED),'as_of').isoformat()
    equipment_id=None if data.get('equipment_id') is None else d.text(data['equipment_id'],'equipment_id',200)
    level=optional_int(data,'equipment_level',1,200)
    slot=state(data,'equipment_slot',('weapon','armor','helmet','boots','belt','accessory','unknown'),'unknown')
    own_skill=optional_int(data,'ordinary_skill_level',0,200)
    if slot!='unknown' and (kind!='character' or method not in ('ordinary','unknown')):
        raise ValueError('equipment_slot applies only to character ordinary repair or method comparison')
    if own_skill is not None and (kind!='character' or method!='ordinary'):
        raise ValueError('ordinary_skill_level applies only to character ordinary repair')
    skill_name={'weapon':'打造技巧','armor':'裁缝技巧','helmet':'裁缝技巧','boots':'炼金术','belt':'炼金术','accessory':'炼金术'}.get(slot)
    failures=optional_int(data,'repair_failures',0,3)
    material_id=None if data.get('material_id') is None else d.text(data['material_id'],'material_id',200)
    material=optional_int(data,'material_level',1,200)
    current=optional_int(data,'current_durability')
    maximum=optional_int(data,'maximum_durability')
    if current is not None and maximum is not None and current>maximum:
        raise ValueError('Current durability cannot exceed the supplied maximum')
    if (kind=='character' and method=='heaven_bead') or (kind=='pet' and method in ('ordinary','guild','quick_repair')):
        raise ValueError('This equipment/method combination has no verified rule in this tool')
    stone_state=state(data,'stone_state',('activated','raw','unknown','none'),'unknown')
    stone_type=state(data,'stone_type',tuple(STONE_TYPES)+('unknown',),'unknown')
    payment=state(data,'payment_preference',('allow_premium','game_currency_only','unknown'),'unknown')
    if (stone_state!='unknown' or stone_type!='unknown') and method not in ('ordinary','unknown','qiankun_stone'):
        raise ValueError('stone_state/stone_type require a stone method or comparison')
    if kind=='unknown' and (stone_state!='unknown' or stone_type!='unknown'):
        raise ValueError('Stone inputs require an equipment kind')
    pearl_live=asof>='2013-03-19'
    rightclick_live=asof>='2015-06-16'
    slots_live=asof>='2026-04-07'
    quick_live=asof>='2015-07-28'
    # Legacy stone page has mutable contents and uncertain revision dates.
    # Its URL is not an effective date: historical snapshots need separate evidence.
    stone_legacy=asof>=CHECKED
    blocked=nominal=threshold=material_ok=skill_threshold=None
    unknowns=[];facts=[];selected=[];questions=[]
    ordinary_workflow=None;workflow=None;choices=[]
    def add(method_id,label,status,steps,requirements,cost,limits,source_ids,**extra):
        row=dict(method=method_id,label=label,status=status,steps=steps,requirements=requirements,cost=cost,
                 limitations=limits,citations=citations(*source_ids),**extra)
        choices.append(row)
        selected.extend(source_ids)
        return row
    no_purchase='只提供手动指引；不购买、激活、扣款或操作游戏。'
    cap_note='受装备耐久上限限制；不知道当前/最大耐久时不预测最终耐久。'
    if kind=='unknown':
        questions.append('这是人物装备还是召唤兽装备？');unknowns.append('equipment_kind')
    elif kind=='character':
        selected=['H01','H09']
        facts.extend(['人物普通修理累计失败3次后不能再走普通修理；不能扩大为所有补耐久方法都失效。',
                      '普通修理可能失败；帮派福利总管路线不要求相应修理技能，但消耗帮贡。'])
        if method in ('ordinary','guild'):
            blocked=None if failures is None else failures>=3
            if method=='ordinary' and level is not None:skill_threshold=str((level+1)//2)
            facts.append('武器自行修理用打造技巧，铠甲/头盔用裁缝技巧，靴子/腰带/饰品用炼金术，至少装备等级的一半（向上取整）。')
            unknowns.extend(['success_probability','failure_other_side_effects','actual_durability_restored'])
        elif method=='pearl':
            unknowns.extend(['character_pearl_formula','character_pearl_level_rule','pearl_three_failure_eligibility'])
            facts.append('人物珍珠恢复量不能套宠装200点；20%或最低100公式未获本包完整主源验证。')
        if method=='ordinary':
            skill_ok=None if own_skill is None or level is None or skill_name is None else own_skill>=(level+1)//2
            status=('blocked_by_three_failures' if blocked is True else 'self_repair_skill_too_low' if skill_ok is False else
                    'known_prerequisites_met_not_success_guaranteed' if blocked is False and skill_ok is True else 'check_missing_prerequisites')
            ordinary_workflow=dict(location='铁匠铺',location_source='H01',equipment_slot=slot,required_skill=skill_name,
                provided_self_repair_skill=None if own_skill is None else str(own_skill),provided_self_repair_skill_meets_threshold=skill_ok,
                status=status,guild_required=False,steps=[
                    '先查看本件人物装备等级、部位和累计失败次数；普通修理失败累计3次就停用此方法。',
                    '前往铁匠铺；旧官方页明确此地点，但没有当前修理NPC、坐标或精确菜单路径的实测证据。',
                    '核对本部位对应的自身修理技能，至少装备等级的一半（向上取整）。',
                    '在当前客户端修理入口选择本件装备，核对体力消耗与条件；接受可能失败后再手动操作。',
                    '查看实际耐久和失败次数；条件不符就停下，改看下方可选方法。'],
                alternative_boundary='自行普通修理门槛不表示必须先练技能；可选择下方快捷修理、已有已激活乾坤石，或玩家修理服务。费用与材料条件分别核对。',
                exact_current_menu_verified=False)
            unknowns.extend(['exact_current_repair_menu','repair_stamina_cost'])
            if slot=='unknown' and failures!=3:questions.append('这件人物装备是什么部位？')
            if failures!=3 and own_skill is None and skill_name is not None:questions.append('如果打算自行普通修理，你的'+skill_name+'多少级？')
        if method in ('ordinary','unknown','quick_repair'):
            historical_quick_price=next((price for upper,price in ((80,10),(120,50),(130,230),(140,300),(150,500),(160,1000)) if level is not None and level<=upper),None)
            historical_quick_cost=('按本件输入的'+str(level)+'级，2015官方历史表对应每次'+str(historical_quick_price)+'仙玉、增加100耐久。' if historical_quick_price is not None else
                '2015官方表按装备等级列仙玉费用和每次增加100耐久；本件等级未提供或超出已核表范围，不猜所需仙玉。')
            quick_status=('not_all_servers_released_at_snapshot' if not quick_live else 'declined_premium_cost' if payment=='game_currency_only' else
                'durability_above_entry_threshold' if current is not None and current>10 else 'current_durability_unknown' if current is None else 'entry_condition_met_choose_cost')
            quick=add('quick_repair','人物快捷修理（有仙玉成本）',quick_status,
                [] if not quick_live else ['打开这件装备所在的物品/装备栏；耐久≤10时，点击装备图标右下角的“修理”按钮，进入快捷修理。',
                    '先看游戏当前显示的仙玉费用和限制；愿意支付才按游戏提示手动完成，再检查耐久。'],
                ['当前耐久≤10；若为0耐久就满足入口条件。','独立快捷修理规则不以本人普通修理技能或帮派为所列前提；这是有界推断。'],
                '有仙玉成本；'+historical_quick_cost+'这些是历史列价，不是2026现价承诺。'+
                ('2024-05-21起免费仙玉不可用于快捷修理或购买乾坤石。' if asof>='2024-05-21' else '本快照不套用2024免费仙玉调整。'),
                [no_purchase,'最终按钮与当前实际收费以游戏显示为准；未确认三失败快捷修理资格，不作为该特殊状态保底。'],
                ['H06','H07']+(['H08'] if asof>='2024-05-21' else []),
                rollout=rollout(asof,'2015-07-21','2015-07-28'),current_price_xianyu=None,
                historical_price_xianyu=None if historical_quick_price is None else str(historical_quick_price),
                historical_nominal_durability='100',entry_durability_eligible=None if current is None else current<=10)
            if method=='quick_repair':
                workflow=quick
                nominal='100' if quick_live else None
                unknowns.extend(['current_quick_repair_price','quick_three_failure_eligibility'])
                if current is None:questions.append('这件人物装备当前多少耐久？')
        if method in ('ordinary','unknown'):
            service={'weapon':'打造类修理','armor':'裁缝类修理','helmet':'裁缝类修理','boots':'炼金类修理','belt':'炼金类修理','accessory':'炼金类修理'}.get(slot)
            target_level='本件'+str(level)+'级装备' if level is not None else '本件装备（等级未提供，先核实际等级）'
            service_step=('本件应找'+service+'；' if service is not None else '装备部位未提供，先核部位再选对应服务：武器用打造，铠甲/头盔用裁缝，靴子/腰带/饰品用炼金；')
            service_step+='核对摊主服务是否适用于'+target_level+'及其当前报价。体力不足导致灰显时可换可用摊位。'
            own_skill_requirement='本件普通修理失败次数少于3；使用摊主对应修理能力，本人不必先练'+(skill_name if skill_name is not None else '对应修理技能')+'。'
            stall=add('player_stall','玩家摊位修理服务（游戏币路线）',
                'blocked_by_three_failures' if failures==3 else 'check_service_and_price' if asof>='2024-04-09' else 'historical_final_buyer_ui_unverified',
                ['找提供对应制造类修理服务的玩家摊位，右键摊位招牌进入服务。',
                 service_step,
                 '当前买方修理选档及最后按钮未完整核实，按实际界面核对，不拿卖方“下架”或打造书铁截图冒充修理操作。'] if asof>='2024-04-09' else [],
                [own_skill_requirement],
                '游戏币价格由当前可用摊位决定，未提供当前报价；不保证最便宜或成功。',
                ['不能保证现在有可用摊位；没有当前买方最终按钮的完整证据。',no_purchase],['H01','H02','H03','H04','H05'],equipment_slot=slot,equipment_level=None if level is None else str(level),required_service=service,exact_current_buyer_menu_verified=False)
    else:
        selected=['P01','P02']
        facts.append('宠装天眼珠累计失败3次后受阻；其等级、类型与灵气规则不等于珍珠规则。')
        if pearl_live:
            facts.extend(['官方明确：失败三次的召唤兽装备仍允许使用珍珠；2013-03-12测试、2013-03-19全服。',
                          '珍珠等级+5≥宠装等级，名义补200耐久，受耐久上限影响；不能据此声称清除失败次数或提高耐久上限。'])
        else: facts.append('本快照早于2013-03-19全服，不能将后来珍珠资格规则追溯为当时全服已开放。')
        if method=='heaven_bead':
            blocked=None if failures is None else failures>=3
            threshold=level;material_ok=None if material is None or level is None else material>=level
            unknowns.extend(['success_probability','actual_durability_restored'])
        if method in ('pearl','unknown'):
            pearl_status='published_method_available' if pearl_live else 'not_all_servers_released_at_snapshot'
            pearl_steps=[]
            if rightclick_live:
                pearl_steps=['选用珍珠等级+5≥宠装等级的珍珠；例如105级宠装可用100级珍珠。','右键珍珠打开“使用珍珠”界面。']
                if slots_live:pearl_steps.append('宠装穿在召唤兽上就切到“召唤兽装备栏”；在背包就切到它所在的“道具”或“行囊”栏。')
                else:pearl_steps.append('在当时界面选择目标宠装；本快照不能套用2026新增的栏位切换。')
                pearl_steps.append('选择目标宠装，核对材料与目标，再按游戏提示完成使用；最终消费按钮名称/位置未实测，不承诺某个预览。')
            elif pearl_live:pearl_steps=['珍珠资格已全服开放；2015右键优化尚未全服，本包不编此前精确操作入口。']
            pearl=add('pearl','召唤兽装备珍珠修复',pearl_status,pearl_steps,
                ['珍珠等级+5≥宠装等级；三失败资格官方已明确，不用再找未证实的资格预览。'] if pearl_live else ['等待该快照下的区服开放证据。'],
                '消耗一颗适用珍珠；库存与当前购买价格未提供，不认定新增现金为0。',
                [cap_note,'右键路线不要求跑铁匠铺；不套用畅玩服“先选宠物自动定位”细节。',no_purchase],
                ['P01','P02']+(['P03','P04'] if rightclick_live else [])+(['P05','P06'] if slots_live else []),
                rollout=rollout(asof,'2013-03-12','2013-03-19'),right_click_all_server_effective_on='2015-06-16',slot_switch_all_server_effective_on='2026-04-07')
            if method=='pearl':
                workflow=pearl
                blocked=False if pearl_live else None
                nominal='200' if pearl_live else None
                threshold=max(1,level-5) if pearl_live and level is not None else None
                material_ok=None if not pearl_live or material is None or level is None else material+5>=level
                if material_ok is False:pearl['status']='material_level_too_low'
                if not pearl_live:unknowns.append('historical_pearl_rule_not_all_servers_released')
                if level is None:questions.append('这件召唤兽装备多少级？')
                if material is None:questions.append('准备使用的珍珠多少级？')
    if kind!='unknown' and method in ('ordinary','unknown','qiankun_stone'):
        available=slots_live if kind=='pet' else stone_legacy
        stone=STONE_TYPES.get(stone_type)
        cap=None if stone is None else stone[2 if kind=='pet' else 1]
        # Legacy material_level remains a declared applicable maximum for human stones.
        # Pet stones require named types because their caps do not use human ranges.
        if cap is None and kind=='character':cap=material
        if stone is not None and material is not None and material!=stone[1]:
            raise ValueError('material_level must equal the named stone human range maximum; use stone_type alone for pet caps')
        stone_ok=None if cap is None or level is None else level<=cap
        three_ok=False if kind=='character' and available else False if kind=='pet' and available and failures is not None and failures<3 else None
        status=(('not_all_servers_released_at_snapshot' if kind=='pet' else 'historical_legacy_revision_unverified') if not available else 'stone_level_too_low' if stone_ok is False else
                'no_owned_stone' if stone_state=='none' else ('declined_premium_activation' if payment=='game_currency_only' else 'activation_requires_premium_choice') if stone_state=='raw' else
                'activation_unknown' if stone_state=='unknown' else 'three_failure_pet_stone_unverified' if kind=='pet' and failures in (None,3) else
                'check_material_level' if stone_ok is None else 'known_requirements_met_not_executed')
        row=add('qiankun_stone','已有已激活乾坤石',status,
            [] if not available else ['先核对石头类型和“已激活”状态；未激活石需要仙玉激活，不能当成已有免费可用材料。',
                '右键已有已激活乾坤石，打开使用界面。']+
                (['按目标所在位置切到人物装备/召唤兽装备或道具/行囊栏，选择目标装备。'] if slots_live else ['选择这件适用等级的人物装备；不套用后来新增的切栏界面。'])+
                ['核对石头与目标后按游戏提示使用，再看实际耐久；未核最终按钮名。'],
            ['必须已激活；人物适用上限依类型为80/120/130/140/150/160级。' if kind=='character' else
             '必须已激活；宠装上限依破损/普通/奢华/温润/精致/精美类型为85/125/135/145/145/145级。',
             '人物三失败可以使用。' if kind=='character' else '三失败宠装乾坤石资格仍缺直接证据，三失败优先已明确的珍珠路线。'],
            '已有已激活材料无需本工具安排激活；会消耗材料且有机会成本。未激活石激活要仙玉，历史破损石10仙玉不是现价保证。'+
            ('免费仙玉不能购买乾坤石。' if asof>='2024-05-21' else ''),
            [cap_note,'2013“只允许人物装备”已被2026-04-07时间服宠装补丁覆盖；宠装不是召唤兽饰品。' if slots_live else '按本快照区分已开放与后续补丁。',no_purchase],
            (['H09','P05','P06'] if kind=='pet' else ['H09'])+(['P05','P06'] if kind=='character' and slots_live else [])+(['H08'] if asof>='2024-05-21' else []),
            stone_state=stone_state,stone_type=stone_type,provided_material_level_eligible=stone_ok,
            maximum_equipment_level=None if cap is None else str(cap),nominal_durability_restored=('200' if kind=='pet' else '100') if available else None,
            current_activation_price_xianyu=None,historical_activation_price_xianyu=None if stone is None else str(stone[3]),
            blocked_by_three_failures=three_ok,
            rollout=rollout(asof,'2026-03-31','2026-04-07') if kind=='pet' else 'legacy_source_revision_date_uncertain')
        if method=='qiankun_stone':
            workflow=row;blocked=three_ok;material_ok=stone_ok if available else None
            nominal=row['nominal_durability_restored'];threshold=level if available and kind=='character' else None
            if stone_state!='activated':unknowns.append('activated_stone_required')
            if kind=='pet' and failures in (None,3):unknowns.append('pet_stone_three_failure_eligibility')
            if not available:unknowns.append('stone_rule_not_released_for_snapshot' if kind=='pet' else 'historical_legacy_source_revision_unverified')
            if stone_type=='unknown' and (kind=='pet' or material is None):questions.append('这颗乾坤石是哪一种？')
            if stone_state=='unknown':questions.append('它现在已激活还是未激活？')
    if method=='unknown':
        questions.append('想选哪种修复方法？');unknowns.append('repair_method')
    elif kind!='unknown' and failures is None and method in ('ordinary','guild','heaven_bead'):
        questions.insert(0,'这件装备累计修理失败几次？')
    if method=='ordinary' and own_skill is not None and level is not None and own_skill<(level+1)//2:
        questions=[q for q in questions if '自行普通修理' not in q and '累计修理失败' not in q]
    if asof>CHECKED:unknowns.append('rules_after_knowledge_checked_date_not_audited')
    actual = None
    preview = data.get('observed_preview')
    preview_out = None
    source_conflicts = []
    asof = None if data.get('as_of') is None else d.day(data['as_of'], 'as_of')
    if preview is not None:
        if method not in ('pearl', 'qiankun_stone'):
            raise ValueError('Observed restoration previews are supported only for pearl/qiankun, not stochastic repair methods')
        if kind == 'unknown' or method == 'unknown':
            raise ValueError('An observed preview must name its equipment class and method')
        d.fields(preview, ('restored_durability', 'equipment_id', 'equipment_level', 'current_durability', 'maximum_durability', 'repair_failures', 'material_id', 'material_level', 'equipment_kind', 'method', 'observed_on', 'source'))
        if preview['equipment_kind'] != kind or preview['method'] != method:
            raise ValueError('Preview belongs to a different equipment class or repair method')
        amount = integer(preview['restored_durability'], 'observed restoration')
        observed_id = d.text(preview['equipment_id'], 'preview equipment_id', 200)
        observed_level = integer(preview['equipment_level'], 'preview equipment_level', 1, 200)
        observed_current = integer(preview['current_durability'], 'preview current_durability')
        observed_material_id = d.text(preview['material_id'], 'preview material_id', 200)
        observed_material = optional_int(preview, 'material_level', 1, 200)
        observed_failures = optional_int(preview, 'repair_failures', 0, 3)
        observed_maximum = optional_int(preview, 'maximum_durability')
        matches = (equipment_id is not None and level is not None and current is not None and material_id is not None
                   and observed_id == equipment_id and observed_level == level and observed_current == current
                   and material is not None and failures is not None and maximum is not None
                   and observed_material_id == material_id and observed_material == material
                   and observed_failures == failures and observed_maximum == maximum)
        day = d.day(preview['observed_on'], 'preview observation date')
        d.text(preview['source'], 'preview source')
        if asof is None or day > asof:
            raise ValueError('Preview needs as_of on or after its observation date')
        if observed_maximum is not None and observed_current + amount > observed_maximum:
            raise ValueError('Observed preview contradicts its recorded maximum durability')
        if blocked is True:
            raise ValueError('Observed preview conflicts with verified method block; recheck method/state')
        preview_out = dict(preview, provenance='user_observed_not_primary_formula', stale=day < asof, state_matches=matches)
        if nominal is not None and amount > int(nominal):
            source_conflicts.append('observed_preview_exceeds_published_nominal_restoration; verify current rule, item and method')
        actual = str(amount) if day == asof and matches and material_ok is not False and not source_conflicts else None
        if not matches:
            unknowns.append('matching_item_preview_state')
        if day < asof:
            unknowns.append('fresh_preview')
    # as_of is validated above and preview freshness still requires explicit user clock.
    capped=None
    if nominal is not None and current is not None and maximum is not None and material_ok is True and blocked is False:
        if method=='pearl' or (method=='qiankun_stone' and stone_state=='activated'):
            capped=str(min(int(nominal),maximum-current))
    conditional_restoration=None
    if kind=='character' and method=='qiankun_stone' and stone_legacy and stone_state!='raw' and stone_state!='none' and current is not None and maximum is not None and material_ok is not False:
        conditional_restoration=str(min(100,maximum-current))
    if method=='qiankun_stone' and (stone_state!='activated' or blocked is not False or material_ok is not True):
        actual=None
    if kind=='character' and method=='pearl' and actual is None:
        questions.append('若当前客户端在消耗前显示恢复预览，具体增加多少耐久？')
    result_citations=citations(*selected)
    if kind=='pet':
        result_citations.insert(0,dict(id='pet_heaven_bead_legacy',url='https://xyq.163.com/2007/fbcq/fbcq_02.html',published_on=None,effective_on=None,all_server_effective_on=None,checked_date=CHECKED,source_scope='historical_official_rule'))
    if kind=='character' and method=='pearl':
        result_citations.append(dict(id='pearl_preview',url='https://xyq.163.com/wh/20250606/4907_1238835.html',published_on='2025-06-09',effective_on='2025-06-10',all_server_effective_on=None,checked_date=CHECKED,source_scope='partial_server_test_only'))
    return dict(calculator='repair_guidance',equipment_kind=kind,method=method,
        rule_snapshot_date=data.get('as_of',CHECKED),knowledge_checked_date=CHECKED,edition='pc_time',
        blocked_by_three_failures=blocked,nominal_durability_restored=nominal,
        minimum_material_level_from_verified_rule=None if threshold is None else str(threshold),
        provided_material_level_eligible=material_ok,ordinary_repair_skill_minimum=skill_threshold,
        ordinary_repair_workflow=ordinary_workflow,repair_workflow=workflow,method_choices=choices,
        restoration_under_verified_cap=capped,restoration_from_matching_preview=actual,observed_preview=preview_out,
        source_conflicts=source_conflicts,conditional_qiankun_restoration_if_legacy_rule_applies=conditional_restoration,
        facts=facts,unknowns=list(dict.fromkeys(unknowns)),next_questions=list(dict.fromkeys(questions))[:2],citations=result_citations,
        limits=['资格、条件算术和实际修复分开；通过等级门槛不表示已完成修复或取得材料。',
                '人物珍珠预览只核到2025部分服测试；不保证全服存在，不要求消耗道具试修。',
                '知识核验日不同于发布时间、测试/全服生效日或实机验证日；历史价格不是当前报价。',
                '日期粒度按当日维护后解释；未提供测试服身份时，只用全服日期启用新规则。',no_purchase])
