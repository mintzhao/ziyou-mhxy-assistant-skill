"""Exact offline routes for PC time-server resources; see verified-routes.md.

Original implementation. No network, client control, prices or third-party code.
All numeric results are decimal strings. Unknown rules remain explicit.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from fractions import Fraction
import heapq
import json
from pathlib import Path
import sys

try:
    from . import resources
except ImportError:  # Direct script invocation.
    import resources

CHECKED_DATE = "2026-10-06"
RULE_VERSION = "pc-time-routes-2026-10-06"
SOURCE_FILE = Path(__file__).resolve().parents[1] / "references" / "rule-sources.json"
ASCENSION = {13: (12, 21), 14: (12, 22), 15: (13, 22), 16: (13, 23),
             17: (14, 23), 18: (14, 24), 19: (15, 24), 20: (15, 25)}
STAR_EXTRAS = {9: (5,), 10: (6, 7), 11: (9,)}
CUMULATIVE_PET_XP = (0, 150, 360, 650, 1040, 1550, 2200, 3010, 4000, 5190,
                     6600, 8250, 10160, 12350, 14840, 17650, 20800, 24310,
                     28200, 32490, 37200, 42350, 47960, 54050, 60640, 67750)


def _i(value, label, low=0, high=None):
    return resources._integer(value, label, low, high)


def _fields(data, required, optional=()):
    resources._object(data, required, optional)


def _text(value, label, max_length=500):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(label + "必须是非空文本")
    return value.strip()


def _enum(value, allowed, label):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(label + "无效")
    return value


def _fraction(value, label, positive=False):
    # Explicit rational syntax rather than floating-point or Decimal rounding.
    if isinstance(value, str) and "/" in value:
        parts = value.split("/")
        if len(parts) != 2:
            raise ValueError(label + "必须是整数或分数字符串")
        result = Fraction(_i(parts[0], label), _i(parts[1], label + "分母", 1))
    else:
        result = Fraction(_i(value, label))
    if positive and result <= 0:
        raise ValueError(label + "必须大于0")
    return result


def _s(value):
    return str(value)


def _ceil(value):
    return -(-value.numerator // value.denominator)


def _meta(kind, rule_ids):
    manifest = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    rules = {r["id"]: r for r in manifest["rules"]}
    sources = {s["id"]: s for s in manifest["sources"]}
    source_ids = sorted({sid for rid in rule_ids for sid in rules[rid]["sources"]})
    return {"calculator": kind, "scope": "梦幻西游电脑版时间服",
            "checkedDate": CHECKED_DATE, "ruleVersion": RULE_VERSION,
            "ruleIds": rule_ids,
            "citations": [{"id": sid, "title": sources[sid]["title"],
                           "url": sources[sid]["url"], "checkedDate": CHECKED_DATE}
                          for sid in source_ids]}


def _date(value, label):
    text = _text(value, label)
    try:
        if date.fromisoformat(text).isoformat() != text:
            raise ValueError()
    except ValueError:
        raise ValueError(label + "必须为有效YYYY-MM-DD") from None
    return date.fromisoformat(text)


def _quote(value):
    if value is None:
        return None
    _fields(value, ("unitPrice", "server", "date", "currency", "source", "kind"), ("asOf", "maxAgeDays"))
    amount = _i(value["unitPrice"], "单价")
    server = _text(value["server"], "报价服务器")
    when = _date(value["date"], "报价日期")
    as_of = _date(value.get("asOf", datetime.now(timezone.utc).date().isoformat()), "价格核对日")
    if when > as_of:
        raise ValueError("报价日期不能晚于价格核对日asOf")
    max_age = _i(value.get("maxAgeDays", 7), "报价最长有效天数", 0, 36500)
    currency = _enum(value["currency"], ("两",), "报价货币（只接受游戏币两）")
    source = _text(value["source"], "人工报价来源")
    kind = _enum(value["kind"], ("asking", "sold", "user_quote", "estimate"), "报价口径")
    age = (as_of - when).days
    stale = age > max_age
    warnings = ["人工输入报价，非实时市场核验；不保证货源、数量或实际成交价。"]
    if kind == "asking":
        warnings.append("asking是挂牌价，不是成交价。")
    elif kind == "sold":
        warnings.append("sold是历史成交记录，不保证现在可按此价购买。")
    elif kind == "estimate":
        warnings.append("estimate是估计值，不是已观察到的市场报价。")
    if stale:
        warnings.append("报价已过期；金额仅保留条件算术，不据此认定当前更便宜路线。")
    return {"unitPrice": str(amount), "server": server, "date": when.isoformat(),
            "currency": currency, "source": source, "kind": kind,
            "asOf": as_of.isoformat(), "maxAgeDays": str(max_age), "ageDays": str(age),
            "stale": stale, "freshness": "stale" if stale else "fresh",
            "warnings": warnings, "retrieval": "manual_input"}


def _range(data, max_level=25):
    current = _i(data["currentLevel"], "当前等级", 0, max_level)
    target = _i(data["targetLevel"], "目标等级", current, max_level)
    cap = _i(data["confirmedCap"], "已在游戏内确认的上限", 0, max_level)
    progress = _i(data["currentProgressXp"], "本级已有经验")
    if current > cap or target > cap:
        raise ValueError("等级超过已确认上限；先核对或使用降修路线计算")
    if current == cap and progress:
        raise ValueError("已到确认上限时本级进度必须为0；本工具不假定封顶经验保留")
    if current < max_level and progress >= resources._step_xp(current + 1):
        raise ValueError("本级进度必须小于升下一级所需经验")
    if current == max_level and progress:
        raise ValueError("满级时本级进度必须为0")
    required = sum(resources._step_xp(r) for r in range(current + 1, target + 1))
    return current, target, cap, progress, required - (progress if target > current else 0)


def _item_budget(required, xp, quote):
    count = _ceil(Fraction(required) / xp)
    return {"requiredXp": str(required), "xpPerItem": str(xp), "itemCount": str(count),
            "purchasedXp": str(count * xp), "surplusXp": str(count * xp - required),
            "costLiang": None if quote is None else str(count * int(quote["unitPrice"])),
            "quote": quote, "quoteWarnings": [] if quote is None else quote["warnings"],
            "surplusMeaning": "算术余量；达到上限时是否保留未核实，不能当成可用经验"}


def cultivation_items(data):
    """Gold pills: require actual per-item XP, never silently assume quality/2."""
    _fields(data, ("type", "currentLevel", "targetLevel", "currentProgressXp", "confirmedCap", "quality"),
            ("confirmedItemXp", "itemXpEvidence", "quote"))
    kind = _enum(data["type"], ("attack", "spell", "defense", "anti_spell"), "人物四修类型")
    current, target, cap, progress, required = _range(data)
    quality = _i(data["quality"], "九转金丹品质", 1)
    quote = _quote(data.get("quote"))
    result = _meta("gold_pill_route", ["ordinary_cultivation", "gold_pill_xp_unverified"])
    result.update(type=kind, quality=str(quality), currentLevel=str(current), targetLevel=str(target),
                  confirmedCap=str(cap), currentProgressXp=str(progress))
    ordinary = resources.cultivation({k: data[k] for k in ("type", "currentLevel", "targetLevel", "currentProgressXp", "confirmedCap")})
    result["ordinary"] = ordinary
    if "confirmedItemXp" not in data:
        if "itemXpEvidence" in data:
            raise ValueError("有经验依据时也须提供confirmedItemXp")
        result.update(status="unsupported", missing=["confirmedItemXp", "itemXpEvidence"],
                      explanation="未从官方出版资料独立核实九转金丹品质÷2及奇数品质取整，不能自动代入。请读取游戏道具说明，手工给出每颗实际经验及依据。")
        return result
    xp = _fraction(data["confirmedItemXp"], "道具实际经验", positive=True)
    evidence = _text(data.get("itemXpEvidence"), "游戏内经验依据")
    budget = _item_budget(required, xp, quote)
    normal_cost = int(ordinary["costLiang"])
    result.update(status="conditional_manual_xp", itemXpEvidence=evidence, item=budget,
                  itemEligibility="unknown: 请确认当前道具在该角色/四修项目可用；不由品质或价格推断",
                  breakEvenUnitPriceLiang=None if budget["itemCount"] == "0" else str(Fraction(normal_cost, int(budget["itemCount"]))),
                  cheaperRoute=None, savingsLiang=None, conditionalPriceComparison=None,
                  quoteWarnings=[] if quote is None else quote["warnings"])
    if quote is not None:
        delta = normal_cost - int(budget["costLiang"])
        cheaper = "items" if delta > 0 else "ordinary" if delta < 0 else "equal"
        result["conditionalPriceComparison"] = {"cheaperRoute": cheaper, "savingsLiang": str(abs(delta)),
                                                "basis": "仅在输入报价、每颗XP和资格均成立时的纯路线算术",
                                                "quoteFreshness": quote["freshness"], "quoteKind": quote["kind"]}
        if not quote["stale"]:
            result.update(cheaperRoute=cheaper, savingsLiang=str(abs(delta)))
    result["comparisonScope"] = "仅比较全普通与全道具两条纯路线，按人工经验及同服报价成立；未优化混合采购，也未计时间价值"
    return result


def pet_cultivation(data):
    _fields(data, ("type", "currentLevel", "targetLevel", "currentProgressXp", "confirmedCap"),
            ("characterLevel", "fruitEligibility", "quote"))
    kind = _enum(data["type"], ("attack", "spell", "defense", "anti_spell"), "召唤兽修炼类型")
    current, target, cap, progress, required = _range(data)
    quote = _quote(data.get("quote"))
    role = None if "characterLevel" not in data else _i(data["characterLevel"], "角色等级", 0, 175)
    eligibility = _enum(data.get("fruitEligibility", "unknown"), ("confirmed", "unknown", "ineligible"), "游戏内修炼果可用性")
    result = _meta("pet_fruit_route", ["pet_fruit_xp", "pet_xp_schedule", "pet_eligibility_partial"])
    result.update(status="calculated" if eligibility == "confirmed" else "eligibility_" + eligibility,
                  type=kind, currentLevel=str(current), targetLevel=str(target),
                  confirmedCap=str(cap), currentProgressXp=str(progress),
                  characterLevel=None if role is None else str(role), fruitEligibility=eligibility,
                  item=_item_budget(required, Fraction(150), quote),
                  steps=[{"targetLevel": str(r), "xp": str(CUMULATIVE_PET_XP[r] - CUMULATIVE_PET_XP[r-1])} for r in range(current+1, target+1)],
                  taskCharacterLevelReference=str(max(65, target * 5 + 20)),
                  eligibilityNotes=["必须输入游戏内实际解锁上限；旧召唤兽介绍的20级上限与当前官方工具箱25级计算范围不同，不据角色等级自动解锁。",
                                    "官方可核实≥65级是修炼任务/秘传任务参与门槛，不能直接当作所有道具使用资格。",
                                    "未独立核实修炼果每日限量、跨上限经验保留和特殊上限解锁，预算不等于现在即可吃完。"])
    return result


def _shortest(current, cap, target, stage, full_cap=False):
    start = (current, cap, stage)
    dist = {start: 0}
    parents = {}
    queue = [(0, start)]
    while queue:
        cost, state = heapq.heappop(queue)
        if cost != dist[state]:
            continue
        level, ceiling, phase = state
        if level >= target and phase == "after":
            path = []
            end = state
            while state != start:
                state, action = parents[state]
                path.append(action)
            return cost, list(reversed(path)), end
        edges = []
        if level < ceiling:
            xp = resources._step_xp(level + 1)
            edges.append(((level+1, ceiling, phase), xp,
                          {"action": "train", "fromLevel": str(level), "toLevel": str(level+1),
                           "cap": str(ceiling), "phase": phase, "xp": str(xp)}))
        if phase == "before":
            edges.append(((level, ceiling, "after"), 0,
                          {"action": "ascend_keep", "fromLevel": str(level), "toLevel": str(level),
                           "fromCap": str(ceiling), "toCap": str(ceiling), "xp": "0"}))
            if level in ASCENSION:
                after_level, after_cap = ASCENSION[level]
                edges.append(((after_level, after_cap, "after"), 0,
                              {"action": "ascend_reduce", "fromLevel": str(level), "toLevel": str(after_level),
                               "fromCap": str(ceiling), "toCap": str(after_cap), "xp": "0"}))
        elif 20 <= ceiling < 25 and ceiling-level < 2 and (not full_cap or level == ceiling):
            edges.append(((level-1, ceiling+1, phase), 0,
                          {"action": "raise_cap", "fromLevel": str(level), "toLevel": str(level-1),
                           "fromCap": str(ceiling), "toCap": str(ceiling+1), "xp": "0"}))
        for next_state, edge_cost, action in edges:
            candidate = cost + edge_cost
            if candidate < dist.get(next_state, 10**30):
                dist[next_state] = candidate
                parents[next_state] = (state, action)
                heapq.heappush(queue, (candidate, next_state))
    raise ValueError("已核实规则下没有通往目标的路线")


def cap_route(data):
    _fields(data, ("type", "stage", "currentLevel", "currentProgressXp", "confirmedCap", "targetLevel", "characterLevel"))
    kind = _enum(data["type"], ("attack", "spell", "defense", "anti_spell"), "可降修的四修类型")
    stage = _enum(data["stage"], ("before", "after"), "飞升阶段")
    current = _i(data["currentLevel"], "当前修炼等级", 0, 25)
    target = _i(data["targetLevel"], "目标修炼等级", current, 25)
    cap = _i(data["confirmedCap"], "已确认修炼上限", 20, 25)
    progress = _i(data["currentProgressXp"], "本级已有修炼经验")
    role = _i(data["characterLevel"], "角色等级", 0, 175)
    if current > cap or (stage == "before" and cap != 20):
        raise ValueError("飞升前仅支持已确认20上限，当前修炼不能超过上限")
    if current == cap and progress:
        raise ValueError("已到上限时进度必须为0")
    if current < 25 and progress >= resources._step_xp(current+1):
        raise ValueError("本级进度超过下一等级所需经验")
    result = _meta("cultivation_cap_route", ["ordinary_cultivation", "ascension_mapping", "after_ascension_cap", "reset_progress_unknown"])
    # Boundary-only reset planning avoids claiming unknown XP reset behavior.
    if progress and (stage == "before" or target > cap):
        result.update(status="unsupported", explanation="降修/飞升时非零本级经验如何处理未核实；请提供本级进度为0的边界状态后重算。不能默认为清零或保留。")
        return result
    xp, path, end = _shortest(current, cap, target, stage)
    full_xp, full_path, _ = _shortest(current, cap, target, stage, full_cap=True)
    if target > current and progress:
        xp -= progress
        full_xp -= progress
        path[0] = dict(path[0], xp=str(int(path[0]["xp"])-progress), progressAppliedXp=str(progress))
        full_path[0] = dict(full_path[0], xp=str(int(full_path[0]["xp"])-progress), progressAppliedXp=str(progress))
    per_purchase = 20000 if kind in ("defense", "anti_spell") else 30000
    count = (xp+9)//10
    full_count = (full_xp+9)//10
    before_required = max([135] + [5*int(p["toLevel"])+20 for p in path if p["action"] == "train" and p.get("phase") == "before"]) if stage == "before" else None
    after_required = max([0] + [5*int(p["toLevel"])+20 for p in path if p["action"] == "train" and p.get("phase") == "after"])
    available_after = role-15 if stage == "before" else role
    deficits = []
    if before_required is not None and role < before_required:
        deficits.append("飞升前角色需至少" + str(before_required) + "级")
    if available_after < after_required:
        deficits.append("飞升后点修阶段角色需至少" + str(after_required) + "级，须另行升级")
    result.update(status="requires_character_levels" if deficits else "calculated_with_prerequisites",
                  objective="最少普通修炼新增经验；固定单价下同时最少两与资材",
                  type=kind, stage=stage, initialLevel=str(current), initialCap=str(cap),
                  finalLevel=str(end[0]), finalCap=str(end[1]), requiredXp=str(xp),
                  purchases=str(count), costLiang=str(count*per_purchase), materialsConsumed=str(count*5),
                  surplusXp=str(count*10-xp), contributionConsumed="0", path=path,
                  fullCapStrategy={"requiredXp": str(full_xp), "costLiang": str(full_count*per_purchase), "path": full_path},
                  savingVersusFullCapLiang=str((full_count-count)*per_purchase),
                  prerequisites={"requiredBeforeCharacterLevel": None if before_required is None else str(before_required),
                                 "requiredAfterCharacterLevel": str(after_required),
                                 "requiredContributionExclusive": str(150*max([0]+[int(a["toLevel"]) for a in path if a["action"] == "train"])),
                                 "characterLevelGaps": deficits,
                                 "ascensionQuest": "飞升前方案还需任意6项师门技能≥130且完成飞升任务" if stage == "before" else "已飞升状态由输入确认",
                                 "guild": "入帮>14天、对应修炼已开放，累计帮贡>最高实际点修等级×150，且有足够资材"},
                  limitations=["只计普通修炼追加XP、两和资材；不计升级角色/技能、任务、时间或机会成本。",
                               "每个降修动作都在0本级经验边界，未假定带进度降修的清零/保留规则。",
                               "不是自动操作指令；先在游戏内核对该项当前上限和飞升阶段。",
                               "满上限再降是受限策略的最优路线；最优结果可能并列，不宣称唯一。"])
    return result


def gem_feasibility(data):
    _fields(data, ("gemType", "slot", "equipmentLevel", "currentForge", "targetForge", "existingGemTypes", "effects"), ("providedGrades", "characterLevel"))
    gem = next((g for g in resources.GEM_TYPES if g["id"] == data["gemType"]), None)
    if gem is None:
        raise ValueError("仅支持八种普通属性宝石")
    slot = _enum(data["slot"], ("武器", "头盔", "铠甲", "腰带", "鞋子", "项链"), "装备部位")
    equipment = _i(data["equipmentLevel"], "装备原始要求等级", 0, 160)
    if equipment % 10:
        raise ValueError("仅支持原始要求等级为10倍数的装备，简易不改变此输入")
    current = _i(data["currentForge"], "当前锻炼", 0, 20)
    target = _i(data["targetForge"], "目标锻炼", current, 20)
    existing = data["existingGemTypes"]
    all_gems = {g["id"]: g for g in resources.GEM_TYPES}
    if not isinstance(existing, list) or any(not isinstance(g,str) or g not in all_gems for g in existing) or len(set(existing)) != len(existing) or len(existing)>2:
        raise ValueError("已有宝石类型须为不重复的0至2种支持类型")
    if (current == 0 and existing) or (current > 0 and not existing) or len(existing) > current:
        raise ValueError("已有锻炼等级与已有宝石类型矛盾")
    if any(slot not in all_gems[g]["slots"] for g in existing):
        raise ValueError("已有宝石与装备部位不符")
    effects = data["effects"]
    if not isinstance(effects, list) or any(x not in ("精致", "无级别限制", "简易") for x in effects) or len(effects) != len(set(effects)):
        raise ValueError("effects仅接受不重复的精致/无级别限制/简易列表，普通装备填[]")
    cap = None if "无级别限制" in effects else equipment//10 + int("精致" in effects)
    reasons = []
    role=None if "characterLevel" not in data else _i(data["characterLevel"],"人物等级",0,175)
    wearing_min=0 if "无级别限制" in effects else max(0,equipment-(5 if "简易" in effects else 0))
    if role is not None and role<wearing_min:reasons.append("人物等级不满足所填装备穿戴门槛；核对等级/简易/无级别，不能只凭已镶宝石推定可穿")
    if target > current and slot not in gem["slots"]:
        reasons.append("所选宝石不适用于该部位")
    if target > current and len(set(existing + [gem["id"]])) > 2:
        reasons.append("会超过同件装备最多两种宝石的限制")
    if cap is not None and current > cap:
        raise ValueError("已有锻炼超过所填装备/特效允许上限，请核对装备信息")
    if cap is not None and target > cap:
        reasons.append("目标超过该装备锻炼上限")
    grades = list(range(current+1, target+1))
    if "providedGrades" in data:
        if not isinstance(data["providedGrades"], list):
            raise ValueError("providedGrades必须是有序列表")
        supplied = [_i(x,"提供的宝石等级",1,20) for x in data["providedGrades"]]
        if supplied != grades:
            reasons.append("须按顺序提供每个新增等级宝石各一颗，不可跳级或只用最高级一颗")
    result = _meta("ordinary_gem_feasibility", ["ordinary_gem_insertion", "refined_gem_cap", "wearing_level_effects"])
    result.update(status="ineligible" if reasons else "eligible", reasons=reasons,
                  equipmentLevel=str(equipment), slot=slot, characterLevel=None if role is None else str(role), minimumCharacterLevel=str(wearing_min), characterLevelEligible=None if role is None else role>=wearing_min, wearingScope="只查已给人物等级；未核武器造型/性别等资格，未给人物等级时不能把镶嵌可行当角色可穿", forgeCap=None if cap is None else str(cap),
                  capMeaning="无级别不受装备等级÷10限制；本工具只核验至20锻" if cap is None else "原装备等级÷10，精致加1，简易不另减原装备等级",
                  requiredGrades=[str(g) for g in grades],
                  allowedSlots=list(gem["slots"]),
                  rawStatDelta=None if reasons else {"key": gem["stat"], "value": str((target-current)*int(gem["perStep"])), "unit": "原始装备属性"})
    return result


def star_gems(data):
    """Synthesize a requested quantity of ONE grade; not insertion-price totals."""
    _fields(data, ("targetGrade", "quantity"), ("craftSkill", "quote"))
    grade = _i(data["targetGrade"], "星辉石目标等级", 1, 11)
    quantity = _i(data["quantity"], "目标颗数", 1)
    skill = None if "craftSkill" not in data else _i(data["craftSkill"], "宝石工艺技能", 0, 7)
    quote = _quote(data.get("quote"))
    units = {1: 1}
    for level in range(2, grade+1):
        units[level] = 3*units[level-1] + sum(units[e] for e in STAR_EXTRAS.get(level, ()))
    required_skill = 0 if grade == 1 else 4 if grade == 2 else 5 if grade <= 5 else 6 if grade <= 7 else 7
    result = _meta("star_gem_synthesis", ["star_base_recipe", "star_2024_recipe", "star_attribute_unknown"])
    result.update(status="eligible" if required_skill == 0 else "skill_unknown" if skill is None else "eligible" if skill >= required_skill else "ineligible",
                  targetGrade=str(grade), quantity=str(quantity), requiredCraftSkill=str(required_skill),
                  baseUnitsPerStoneLowerBound=str(units[grade]), baseUnitsLowerBound=str(units[grade]*quantity),
                  directPurchaseCostLiang=None if quote is None else str(int(quote["unitPrice"])*quantity), quote=quote,
                  quoteWarnings=[] if quote is None else quote["warnings"],
                  directRecipe={"baseGrade": None if grade==1 else str(grade-1), "baseCount": "0" if grade==1 else "3",
                                "extraGrades": [str(x) for x in STAR_EXTRAS.get(grade,())]},
                  rawStatDelta=None,
                  limitations=["只算指定等级成品颗数，不冒充逐级镶嵌所需总价。",
                               "材料为无失败下限；9至11级合成必成功，低级合成仍未计失败损失、体力及手续费。",
                               "星辉石逐属性增量未获官方独立核实，不生成气血/伤害/速度等面板收益。",
                               "灵饰一般镶嵌等级≤灵饰等级÷10；特殊特效和逐级镶嵌交易规划未在此判定。"])
    return result


CALCULATORS = {"gold_pill": cultivation_items, "pet_fruit": pet_cultivation,
               "cap_route": cap_route, "gem_eligibility": gem_feasibility, "star_gem": star_gems}


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线且可追溯的修炼/宝石路线；未知机制不补造")
    parser.add_argument("input", help="UTF-8 JSON普通文件，最多1MiB；见examples/routes-*.json")
    parser.add_argument("--kind", required=True, choices=tuple(CALCULATORS),
                        help="gold_pill人工确认单颗XP的金丹预算；pet_fruit修炼果；cap_route飞升/降修；gem_eligibility普通宝石资格；star_gem星辉石成品合成")
    parser.add_argument("--output", help="仅创建新JSON文件，绝不覆盖；省略时输出到终端")
    args = parser.parse_args(argv)
    try:
        result = CALCULATORS[args.kind](resources.read_resource_input(args.input))
        output = json.dumps(result,ensure_ascii=False,indent=2)+"\n"
        if args.output:
            with Path(args.output).open("x",encoding="utf-8") as f:
                f.write(output)
        else:
            sys.stdout.write(output)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
