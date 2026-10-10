"""Offline pet scene-range checks, not a speed/cost or client-access optimizer."""
from __future__ import annotations
import json
from pathlib import Path
try:
    from . import decisions as d, grounded as g
except ImportError:
    import decisions as d
    import grounded as g

TABLE_PATH = Path(__file__).resolve().parents[1] / 'references' / 'pet-scene-ranges.json'


def scene_leveling(data):
    d.fields(data, ('ruleset', 'current_pet_level', 'target_pet_level'),
             ('character_level', 'scene', 'escort_cost', 'exclude_yuehua'))
    g.scope(data)
    current = g.integer(data['current_pet_level'], 'current_pet_level', 0, 180)
    target = g.integer(data['target_pet_level'], 'target_pet_level', 0, 180)
    if target < current:
        raise ValueError('Scene leveling cannot lower pet level')
    character = g.optional_int(data, 'character_level', 0, 175)
    escort = g.state(data, 'escort_cost', ('free', 'paid', 'unknown'), 'unknown')
    exclude_yuehua = data.get('exclude_yuehua', False)
    if type(exclude_yuehua) is not bool:
        raise ValueError('exclude_yuehua must be a boolean')
    requested = None if data.get('scene') is None else d.text(data['scene'], 'scene', 60)
    table = json.loads(TABLE_PATH.read_text(encoding='utf-8'))
    rows = table['rows']
    if requested is not None and requested not in {r['scene'] for r in rows}:
        raise ValueError('Unknown scene name; use the exact official scene name from pet-scene-ranges.json')

    def assessment(row):
        lo, hi = row['player_level_range']
        # The source never defines a team leader selector. Variable rows are
        # conditional even when the owner's level matches the printed band.
        universal = [lo, hi] == [0, 175]
        player_match = True if universal else None if character is None else lo <= character <= hi
        full = row['full_xp_pet_level_range'][0] <= current <= row['full_xp_pet_level_range'][1]
        xp = row['xp_pet_level_range'][0] <= current <= row['xp_pet_level_range'][1]
        return dict(row, player_level_matches_input=player_match,
                    player_band_scope='all_supported_player_levels' if universal else 'conditional_player_band_team_interpretation_unverified',
                    pet_level_in_full_xp_range=full, pet_level_in_xp_range=xp,
                    verdict=('player_band_does_not_match_input' if player_match is False else
                             'outside_listed_pet_xp_range' if not xp else
                             'within_listed_full_xp_range' if full else 'within_listed_xp_range_below_full'),
                    client_scene_access_verified=False, actual_xp_rate=None)

    checks = [assessment(r) for r in rows]
    requested_checks = [c for c in checks if c['scene'] == requested] if requested else []
    current_options = [c for c in checks if c['player_level_range'] == [0, 175] and c['pet_level_in_full_xp_range']]
    conditional_options = [c for c in checks if c['player_level_range'] != [0, 175]
                           and c['player_level_matches_input'] is not False and c['pet_level_in_full_xp_range']]
    # A deterministic coverage illustration, not a route score. Avoid variable
    # player bands, travel assumptions and unverified team selector rules.
    route, uncovered = [], []
    cursor = current
    fixed = [r for r in rows if r['player_level_range'] == [0, 175]]
    while cursor <= target and current < target:
        choices = [r for r in fixed if r['full_xp_pet_level_range'][0] <= cursor <= r['full_xp_pet_level_range'][1]]
        if not choices:
            start = cursor
            while cursor <= target and not any(r['full_xp_pet_level_range'][0] <= cursor <= r['full_xp_pet_level_range'][1] for r in fixed):
                cursor += 1
            uncovered.append([start, cursor - 1])
            continue
        selected = max(choices, key=lambda r: r['full_xp_pet_level_range'][1])
        end = min(target, selected['full_xp_pet_level_range'][1])
        route.append(dict(scene=selected['scene'], row_id=selected['id'], pet_level_segment=[cursor, end],
                          source_full_xp_pet_level_range=selected['full_xp_pet_level_range'],
                          player_level_range=selected['player_level_range']))
        cursor = end + 1
    questions = []
    if current < target:
        if character is None:
            questions.append('你的人物多少级？人物等级与宝宝等级分开核对，先确认能否继续练到目标。')
        if escort == 'unknown':
            questions.append('现有大龙带练免费还是收费？若收费，按什么方式、多少钱？')
    guidance = [
        '先按宝宝当前等级核对场景经验区间，再确认人物携带/练级上限、场景进入条件和队伍适用方式；有大龙不能跳过这些条件。',
        '下列分段只示范表列满经验区间如何衔接；到交界等级重查宝宝等级和实际经验，不代表最快、最便宜或最少跑图。',
        '比较带练时只用同条件实测：记录各段净经验、有效战斗时间、补给/带练费与点卡。免费带练也不能把全部成本视为零。未测经验速度，不推算总时长或总价。',
        '炼兽笼另核资格：宝宝至少30级；若目标150，人物至少140级是必要条件。已有庭院/笼子不重复算购置；目标150无需只为笼子的阶段上限重问飞升/渡劫，因为各已核阶段上限均至少150。',
        '修业点只能列为另核候选；现有24小时取得限制、实际资格和兑换量必须另查，不能断言必用或最省钱。']
    if exclude_yuehua:
        guidance.append('已保留不考虑月华露的要求；本结果不列月华露购买或使用方案。')
    return dict(calculator='pet_scene_leveling', current_pet_level=str(current), target_pet_level=str(target),
                character_level=None if character is None else str(character), escort_cost=escort,
                exclude_yuehua=exclude_yuehua, requested_scene=requested,
                requested_scene_checks=requested_checks, current_full_xp_options=current_options,
                conditional_full_xp_options=conditional_options,
                level_coverage_example=route, uncovered_pet_level_ranges=uncovered,
                coverage_status='target_already_reached' if current == target else 'full_xp_table_ranges_cover_request' if not uncovered else 'table_coverage_has_gaps',
                route_basis='fixed_player_band_full_xp_interval_coverage_only_not_optimized',
                target_level_reachable=None, optimal_route=None, total_time_hours=None, total_cash=None,
                next_questions=questions[:2], guidance=guidance, citations=[table['source']] + g.citations('cage', 'xiuyedian_test', 'xiuyedian_release'),
                unknowns=['current_client_scene_access', 'mixed_team_player_band_selection', 'leader_level_requirement',
                          'character_pet_level_cap', 'battle_xp_rate', 'total_required_xp', 'travel_time', 'total_cost'],
                limits=table['limits'] + ['经验区间通过不等于当前人物可把宝宝练到目标。范围外仅指该表普通场景经验，不能推断不能进入、不能出战或任何活动均无经验。',
                                        '表列满经验只比较等级范围；尚未验证双/三倍、队伍组成、收费及战斗效率，不输出全局最优路线。'])
