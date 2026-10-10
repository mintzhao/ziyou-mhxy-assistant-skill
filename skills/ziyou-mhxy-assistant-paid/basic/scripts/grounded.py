"""Bounded, provenance-bearing guidance for public player failure cases.

Python standard library only. No client actions, runtime network, invented XP
formula, market ranking, or full inventory optimizer. Checked sources are fixed.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
try:
    from . import decisions as d, resources, routes
except ImportError:
    import decisions as d
    import resources, routes

CHECKED = '2026-10-07'
SOURCES = {
    'ordinary_repair': ('https://xyq.163.com/introduce/jn005.html', '2013-01-05', None, 'historical_official_rule'),
    'pet_repair': ('https://xyq.163.com/2007/fbcq/fbcq_02.html', None, None, 'historical_official_rule'),
    'qiankun': ('https://xyq.163.com/introduce/2013/1/28/5015_359141.html', '2012-12-28', None, 'historical_official_rule'),
    'pearl_preview': ('https://xyq.163.com/wh/20250606/4907_1238835.html', '2025-06-09', '2025-06-10', 'partial_server_test_only'),
    'xiuyedian_test': ('https://xyq.163.com/wh/20260531/4907_1302347.html', '2026-06-01', '2026-06-02', 'partial_server_prompt_test'),
    'xiuyedian_release': ('https://xyq.163.com/wh/20260604/4907_1302930.html', '2026-06-09', '2026-06-09', 'all_server_prompt_release'),
    'cage': ('https://xyq.163.com/introduce/2012/2/6/5014_262875.html', '2012-02-06', None, 'historical_official_rule'),
    'ordinary_gem': ('https://xyq.163.com/introduce/dj008.html', '2013-01-02', None, 'historical_official_rule'),
    'gem_synthesis_2024': ('https://xyq.163.com/news/20240520/4999_1156134.html', '2024-05-20', '2024-05-21', 'all_server_rule_amendment'),
    'gem_synthesis_release': ('https://xyq.163.com/wh/20240520/4907_1155726.html', '2024-05-20', '2024-05-21', 'all_server_release'),
}

def citations(*ids):
    return [dict(id=i, url=SOURCES[i][0], published_on=SOURCES[i][1], effective_on=SOURCES[i][2],
                 checked_date=CHECKED, source_scope=SOURCES[i][3]) for i in ids]

def scope(data):
    if data['ruleset'] != 'pc_time':
        raise ValueError('ruleset must be pc_time; no mobile or 畅玩服 rules')

def integer(value, label, low=0, high=1000000000000):
    return resources._integer(value, label, low, high)

def optional_int(data, name, low=0, high=1000000000000):
    return None if data.get(name) is None else integer(data[name], name, low, high)

def timestamp(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', value):
        raise ValueError(label + ' needs an ISO timestamp with seconds and explicit timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError(label + ' is not a valid timestamp') from None

def iso(value):
    return value.isoformat().replace('+00:00', 'Z')

def state(data, name, allowed, default):
    value = data.get(name, default)
    if value not in allowed:
        raise ValueError(name + ' must be one of ' + '/'.join(allowed))
    return value


def repair_guidance(data):
    """Versioned repair methods; implementation and evidence travel with the package."""
    try:
        from .repair_routes import repair_guidance as calculate_repair
    except ImportError:
        from repair_routes import repair_guidance as calculate_repair
    return calculate_repair(data)


def xiuyedian_guidance(data):
    """Check the 24-hour gate and one explicitly observed batch, never extrapolate XP."""
    d.fields(data, ('ruleset', 'target_pet_level', 'as_of'),
             ('pet_id', 'current_pet_level', 'character_level', 'current_xp', 'owned_points', 'objective',
              'acquisition_method', 'acquired_at', 'acquisition_source', 'other_eligibility', 'preview_batch'))
    scope(data)
    now = timestamp(data['as_of'], 'as_of')
    pet_id = None if data.get('pet_id') is None else d.text(data['pet_id'], 'pet_id', 200)
    target = integer(data['target_pet_level'], 'target_pet_level', 0, 180)
    current = optional_int(data, 'current_pet_level', 0, 180)
    if current is not None and target < current:
        raise ValueError('This leveling route cannot lower pet level')
    character = optional_int(data, 'character_level', 0, 175)
    xp = optional_int(data, 'current_xp')
    owned = optional_int(data, 'owned_points')
    objective = state(data, 'objective', ('points', 'cash', 'time', 'unknown'), 'unknown')
    acquisition = state(data, 'acquisition_method', ('trade', 'gift', 'stall', 'other', 'unknown'), 'unknown')
    other = state(data, 'other_eligibility', ('confirmed', 'unknown', 'ineligible'), 'unknown')
    acquired = None
    if data.get('acquired_at') is not None:
        acquired = timestamp(data['acquired_at'], 'acquired_at')
        if acquired > now:
            raise ValueError('Acquisition cannot be later than as_of')
        d.text(data.get('acquisition_source'), 'acquisition_source')
    elif data.get('acquisition_source') is not None:
        d.text(data['acquisition_source'], 'acquisition_source')
    applicable = now.date().isoformat() >= '2026-06-09'
    try:
        earliest = acquired + timedelta(hours=24) if acquired is not None and acquisition in ('trade', 'gift', 'stall') else None
    except OverflowError:
        raise ValueError('Acquisition date is outside supported 24-hour calculation range') from None
    gate = 'historical_rule_unconfirmed' if not applicable else 'unknown'
    if applicable and acquisition in ('trade', 'gift', 'stall') and earliest is not None:
        gate = 'blocked_under_24_hours' if now < earliest else '24_hour_gate_passed'
    elif applicable and acquisition == 'other':
        gate = 'named_acquisition_restriction_not_established_for_other_methods'
    questions = []
    if current is None:
        questions.append('宝宝现在多少级？')
    if acquisition == 'unknown':
        questions.append('这只宝宝是怎么取得的？')
    elif acquisition in ('trade', 'gift', 'stall') and acquired is None:
        questions.append('这只宝宝具体什么时候通过交易、给予或摆摊转入？')
    elif xp is None:
        questions.append('宝宝本级已有多少经验？')
    elif objective == 'unknown':
        questions.append('你最想省修业点、现金，还是时间？')
    preview = data.get('preview_batch')
    assessment = None
    if preview is not None:
        d.fields(preview, ('pet_id', 'character_level', 'owned_points', 'points', 'expected_xp', 'xp_remaining_to_target', 'target_pet_level', 'pet_level', 'current_xp', 'observed_at', 'source'))
        preview_id = d.text(preview['pet_id'], 'preview pet_id', 200)
        preview_character = integer(preview['character_level'], 'preview character_level', 0, 175)
        preview_owned = integer(preview['owned_points'], 'preview owned_points')
        points = integer(preview['points'], 'preview points', 1)
        gain = integer(preview['expected_xp'], 'preview XP', 1)
        remaining = integer(preview['xp_remaining_to_target'], 'confirmed remaining XP', 1)
        pt = integer(preview['target_pet_level'], 'preview target level', 0, 180)
        pl = integer(preview['pet_level'], 'preview pet level', 0, 180)
        pxp = integer(preview['current_xp'], 'preview current XP')
        observed = timestamp(preview['observed_at'], 'preview observed_at')
        d.text(preview['source'], 'preview source')
        if observed > now:
            raise ValueError('Preview cannot be in the future')
        matches = (current is not None and xp is not None and pet_id is not None and character is not None and owned is not None
                   and pl == current and pxp == xp and pt == target and preview_id == pet_id
                   and preview_character == character and preview_owned == owned)
        fresh = observed.date() == now.date()
        within = gain <= remaining
        sufficient = None if owned is None else owned >= points
        reasons = []
        if not matches: reasons.append('preview_state_missing_or_changed')
        if not fresh: reasons.append('preview_from_earlier_day')
        if earliest is not None and observed < earliest: reasons.append('preview_earlier_than_acquisition_gate')
        if not within: reasons.append('preview_exceeds_remaining_target_xp')
        if sufficient is not True: reasons.append('owned_points_unknown_or_insufficient')
        if gate != '24_hour_gate_passed': reasons.append('acquisition_gate_not_confirmed')
        if other != 'confirmed': reasons.append('other_client_eligibility_not_confirmed')
        if current == target: reasons.append('target_already_reached')
        assessment = dict(preview, provenance='user_observed_not_primary_xp_formula',
                          state_matches=matches, fresh_same_utc_day=fresh,
                          within_user_confirmed_target_xp=within, owned_points_sufficient=sufficient,
                          status='conditional_single_batch' if not reasons else 'do_not_commit_from_this_preview',
                          blockers=reasons, unspent_points_after_this_batch=None if owned is None or owned < points else str(owned-points))
    return {'calculator': 'xiuyedian_guidance', 'pet_id': pet_id, 'target_pet_level': str(target),
            'current_pet_level': None if current is None else str(current),
            'character_level': None if character is None else str(character), 'objective': objective,
            'acquisition_gate': gate, 'earliest_time_from_supplied_acquisition': None if earliest is None else iso(earliest),
            'acquisition_provenance': None if acquired is None else dict(method=acquisition, acquired_at=data['acquired_at'], source=data['acquisition_source']),
            'preview_assessment': assessment, 'optimal_start_level': None, 'total_points': None, 'total_cash': None,
            'next_questions': questions[:2],
            'guidance': ['修业点增加召唤兽等级经验，与宠物修炼/修炼果分开。目标等级不是当前等级。',
                         '交易、给予、摆摊取得不足24小时，先等到NPC提示的最早可用时间；满24小时只消除这一项限制。',
                         '先查看当前状态下可见的小批兑换预览；临近升级或目标时减量并重新预览。200点不是固定最佳批量。',
                         '若等级、经验、点数或目标发生变化，旧预览作废，记录实际结果再更新；不按单批比例外推跨级经验。',
                         '没有无消耗预览就停在待核实，不要求花点数试错；同一批预览不证明最低点数、最低现金或最快路线。'],
            'citations': citations('xiuyedian_test', 'xiuyedian_release'),
            'limits': ['2026年6月公告确认24小时限制提示及其全服放出，不提供完整兑换经验公式或批次更新公式。',
                       'as_of为用户指定比较时刻，不能自动改写为运行时间；历史日期早于2026-06-09时不套用后续公告。',
                       '预览经验及目标剩余经验均为具名用户输入；本工具不验证等级上限、NPC资格、取整或溢出保留。']}


def gem_operations(data):
    """Separate inlay from dated, grade-specific ordinary-gem synthesis guidance."""
    d.fields(data, ('ruleset', 'operation'), ('eligibility', 'target_grade', 'gem_type', 'as_of'))
    scope(data)
    operation = state(data, 'operation', ('inlay', 'synthesis', 'both'), 'both')
    gem_type = data.get('gem_type', 'ordinary')
    if gem_type not in ('ordinary', *(gem['id'] for gem in resources.GEM_TYPES)):
        raise ValueError('gem_type must be an ordinary gem; no 星辉石/玄灵珠/精魄灵石 recipes')
    asof = d.day(data.get('as_of', CHECKED), 'as_of').isoformat()
    target = optional_int(data, 'target_grade', 1, 20)
    if operation == 'inlay' and target is not None:
        raise ValueError('target_grade is a synthesis output grade, not an inlay forge level')
    eligibility = None if data.get('eligibility') is None else routes.gem_feasibility(data['eligibility'])
    synthesis = None
    questions = []
    if operation != 'inlay':
        applicable = '2024-05-21' <= asof <= CHECKED
        high = applicable and target is not None and 12 <= target <= 20
        low = applicable and target is not None and 2 <= target <= 11
        craftable = high or low
        extras = list(resources._EXTRAS.get(target, [])) if craftable else None
        skill = None if not craftable else str(min(7, target // 2 + 2))
        guidance = []
        if not applicable:
            status = 'historical_rule_unverified' if asof < '2024-05-21' else 'future_rule_unverified'
            guidance.append('指定日期不在本包2024-05-21全服调整至2026-10-07核验快照范围内；不把后续配方、必成或技能门槛倒推到过去，也不保证未来不变。请按当时服务器与公告核对。')
        elif target is None:
            status = 'needs_target_grade'
            guidance.append('普通宝石须按合成目标等级区分：2–11级沿用两颗前一级同类石的基础关系，旧页有失败描述，当前精确概率未核；12–20级另需同类低阶材料且本次高阶合成必成。')
            guidance.append('宝石工艺最低等级：目标2–3级需3，4–5级需4，6–7级需5，8–9级需6，10–20级需7。请给出目标等级后列具体材料，不能把两颗主料当所有等级的总投入。')
            questions.append('本次要合出几级普通宝石？')
        elif target == 1:
            status = 'grade_one_acquired_not_synthesized'
            guidance.append('1级普通宝石是基础取得材料，本接口不列由0级合成1级的配方；取得途径和价格另核。')
        else:
            status = 'dated_recipe_guidance'
            recipe = str(target - 1) + '级同类普通宝石2颗'
            if extras:
                counts = {grade: extras.count(grade) for grade in sorted(set(extras))}
                recipe += '，另加' + '、'.join(str(grade) + '级' + str(count) + '颗' for grade, count in counts.items()) + '同类宝石'
            guidance.append('合成' + str(target) + '级一颗：' + recipe + '；宝石工艺至少' + skill + '级。地点为打铁炉/缝纫台。')
            guidance.append('本次12–20级目标的高阶合成必定成功；不代表把全部低阶原料一路合上来也全程必成。' if high else '目标2–11级不在2024公告的12–20级必成范围内；旧官方页描述合成可能失败并损失一颗，当前精确成功率与技能对应概率未核，不给必成保证。')
        guidance.append('这些是合成规则，不能当作镶嵌失败或技能规则；低阶失败损耗、体力、手续费、库存和转服时间锁另核，材料下限不等于保证采购量。')
        synthesis = {
            'location': '打铁炉/缝纫台' if applicable else None,
            'status': status, 'target_grade': None if target is None else str(target),
            'input_count': None if not craftable else str(2 + len(extras)),
            'main_input_count': '2' if craftable else None,
            'main_input_grade': str(target - 1) if craftable else None,
            'main_inputs_same_kind_and_grade': True if craftable else None,
            'extra_same_kind_input_grades': None if extras is None else [str(g) for g in extras],
            'successful_output_count': '1' if craftable else None,
            'successful_output_grade_change': '1' if craftable else None,
            'guaranteed_success': True if high else None,
            'failure_possible_in_source': False if high else True if low else None,
            'failure_lost_input_count_in_source': '1' if low else None,
            'failure_source_scope': 'historical_low_grade_description_current_probability_unverified' if low else None,
            'minimum_baoshi_gongyi_level': skill,
            'skill_effect': '宝石工艺为按目标等级的最低资格门槛，不只是可选成功率提升；直接镶嵌技能仍未知。' if applicable else '指定日期的合成技能资格尚未核实。',
            'success_probability': '1' if high else None,
            'all_server_effective_on': '2024-05-21' if applicable else None,
            'guidance': guidance,
        }
    if operation != 'synthesis' and eligibility is None:
        questions.extend(['这件装备当前锻数是多少？', '本次要升到几锻？'])
    return {'calculator': 'ordinary_gem_operations', 'operation': operation, 'eligibility': eligibility,
            'gem_type': gem_type, 'rule_snapshot_date': asof, 'knowledge_checked_date': CHECKED,
            'direct_inlay': None if operation == 'synthesis' else {
                'location': '铁匠铺', 'materials': '要镶嵌的装备和宝石',
                'steps': ['先核对装备部位、原始等级、当前锻数、特效和已镶类型。',
                          '在铁匠铺相应打造操作中放入装备与宝石；新等级须为当前锻数+1。',
                          '逐级各用一颗相应等级宝石，核对当前客户端显示后再由玩家确认消耗。'],
                'guaranteed_success': None, 'skill_requirement': None,
                'failure_answer': '本包核验的官方页面没有明确写直接镶嵌是否会失败；不能把合成失败规则套过来，也不保证零风险。',
                'skill_answer': '宝石工艺最低等级及必成说明属于合成；已核来源未明确给出直接镶嵌的技能要求，不能据此要求练合成技能。'},
            'synthesis': synthesis, 'next_questions': questions[:2],
            'citations': citations('ordinary_gem') + ([] if operation == 'inlay' else citations('gem_synthesis_2024', 'gem_synthesis_release')),
            'limits': ['已买成品宝石的逐级镶嵌与自己合成材料是两项操作；高阶单次必成不消除上游低阶失败风险。',
                       '操作位置来自官方页面，不保证当前按钮文字；客户端出现不同限制时以实际提示补充核验。',
                       '普通宝石不混用玄灵珠、星辉石或精魄灵石配方；rawStatDelta不是最终人物面板收益。']}
