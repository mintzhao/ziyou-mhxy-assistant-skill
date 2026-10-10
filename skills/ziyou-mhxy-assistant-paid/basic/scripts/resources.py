"""Original, offline resource arithmetic for MHXY PC time-server planning.

No combat prediction, live prices, third-party dependencies, or client access.
Public rule provenance and limitations: references/resource-calculators.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

CHECKED_DATE = "2026-10-06"
SOURCES = {
    "cultivation": {"title": "官方：人物修炼", "url": "https://xyq.163.com/introduce/zd008.html"},
    "gems": {"title": "官方：宝石", "url": "https://xyq.163.com/introduce/dj008.html"},
    "amendment": {"title": "官方：2024-05-21 宝石合成调整", "url": "https://xyq.163.com/news/20240520/4999_1156134.html"},
}
GEM_TYPES = [
    {"id": "radiance", "name": "光芒石", "stat": "hp", "statLabel": "气血", "perStep": "40", "slots": ["铠甲", "腰带"]},
    {"id": "sun", "name": "太阳石", "stat": "damage", "statLabel": "伤害属性", "perStep": "8", "slots": ["武器", "头盔"]},
    {"id": "moon", "name": "月亮石", "stat": "defense", "statLabel": "防御", "perStep": "12", "slots": ["铠甲", "头盔"]},
    {"id": "black", "name": "黑宝石", "stat": "speed", "statLabel": "速度", "perStep": "8", "slots": ["腰带", "鞋子"]},
    {"id": "agate", "name": "红玛瑙", "stat": "hit", "statLabel": "命中", "perStep": "25", "slots": ["武器", "头盔"]},
    {"id": "relic", "name": "舍利子", "stat": "spirit", "statLabel": "灵力", "perStep": "6", "slots": ["铠甲", "项链"]},
    {"id": "mystery", "name": "神秘石", "stat": "dodge", "statLabel": "躲避", "perStep": "20", "slots": ["武器", "腰带", "鞋子"]},
    {"id": "jade", "name": "翡翠石", "stat": "magic_defense", "statLabel": "法术防御", "perStep": "12", "slots": ["铠甲"]},
]
_EXTRAS = {12: [3, 5, 6], 13: [9], 14: [9, 10], 15: [9, 12], 16: [11, 12, 13], 17: [15], 18: [13, 14, 16], 19: [15, 16, 17], 20: [17, 18, 18]}
_TYPE_LABELS = {"attack": "攻击修炼", "spell": "法术修炼", "defense": "防御修炼", "anti_spell": "抗法修炼", "hunting": "猎术修炼"}


def _integer(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or (isinstance(value, int) and abs(value) > 9007199254740991):
        raise ValueError(label + "必须是非负整数或整数字符串")
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,30}", text):
        raise ValueError(label + "必须是至多30位的非负整数")
    result = int(text)
    if result < minimum or (maximum is not None and result > maximum):
        raise ValueError(label + "超出允许范围")
    return result


def _object(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError("输入必须是对象")
    unknown = set(value) - set(required) - set(optional)
    if unknown:
        raise ValueError("未知输入字段：" + ", ".join(sorted(repr(key) for key in unknown)))
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError("缺少必填字段：" + ", ".join(missing))


def _sources(*names):
    return [dict(SOURCES[name], checkedDate=CHECKED_DATE) for name in names]


def _step_xp(target):
    return 10 * (target * target + 3 * target + 11)


def cultivation(data):
    """Calculate ordinary guild cultivation only; all numeric outputs are strings."""
    _object(data, ("type", "currentLevel", "targetLevel", "currentProgressXp", "confirmedCap"))
    kind = data["type"]
    if not isinstance(kind, str) or kind not in _TYPE_LABELS:
        raise ValueError("修炼类型无效")
    limit = 20 if kind == "hunting" else 25
    current = _integer(data.get("currentLevel"), "当前修炼等级", 0, limit)
    target = _integer(data.get("targetLevel"), "目标修炼等级", 0, limit)
    cap = _integer(data.get("confirmedCap"), "已确认修炼上限", 0, limit)
    progress = _integer(data["currentProgressXp"], "本级已有修炼经验")
    if target < current:
        raise ValueError("目标等级不能低于当前等级")
    if current > cap or target > cap:
        raise ValueError("当前或目标等级超过已确认上限；本工具不计算降修解锁路线")
    if (current == limit and progress != 0) or (current < limit and progress >= _step_xp(current + 1)):
        raise ValueError("本级已有经验必须小于下一等级所需经验；满级时填写0")
    steps = [{"targetLevel": str(r), "xp": str(_step_xp(r))} for r in range(current + 1, target + 1)]
    gross = sum(int(step["xp"]) for step in steps)
    applied = progress if target > current else 0
    required = gross - applied
    purchases = (required + 9) // 10
    price = 20000 if kind in ("defense", "anti_spell") else 30000
    return {
        "calculator": "normal_cultivation", "scope": "梦幻西游电脑版时间服：普通帮派修炼",
        "type": kind, "typeLabel": _TYPE_LABELS[kind], "currentLevel": str(current), "targetLevel": str(target),
        "confirmedCap": str(cap), "currentProgressXp": str(progress), "grossXp": str(gross),
        "progressAppliedXp": str(applied), "requiredXp": str(required), "purchases": str(purchases),
        "purchasedXp": str(purchases * 10), "surplusXp": str(purchases * 10 - required),
        "costPerPurchaseLiang": str(price), "costLiang": str(purchases * price),
        "materialsConsumed": str(purchases * 5), "contributionConsumed": "0",
        "requiredCharacterLevel": str(5 * target + 20) if target else "0",
        "requiredContributionExclusive": str(150 * target), "requiredGuildMembershipDaysExclusive": "14",
        "steps": steps,
        "explanations": [
            "普通模式每次增加10点经验；金钱和帮派资材是消耗项，累计帮贡是门槛，不在本模式扣除。",
            "官网表述为累计帮贡严格大于目标等级×150、入帮时间大于14天；还需本帮已开放对应修炼。",
            "结果只适用于已确认上限内的普通修炼，不含快速兑换、租赁、降修、飞升、优惠或战斗效果。",
            "多买的经验仅为算术余量；到上限时是否保留请以游戏内界面为准。",
        ],
        "citations": _sources("cultivation"), "checkedDate": CHECKED_DATE,
    }


def gems(data):
    """Price every required insertion grade; recipe quantities are no-failure floors."""
    _object(data, ("gemType", "currentForge", "targetForge"), ("quotes",))
    current = _integer(data.get("currentForge"), "当前锻炼等级", 0, 20)
    target = _integer(data.get("targetForge"), "目标锻炼等级", 0, 20)
    if target < current:
        raise ValueError("目标锻炼等级不能低于当前等级")
    gem = next((x for x in GEM_TYPES if x["id"] == data["gemType"]), None)
    if gem is None:
        raise ValueError("宝石类型无效")
    quotes = data.get("quotes", {})
    if not isinstance(quotes, dict):
        raise ValueError("各级报价必须是对象")
    parsed = {}
    for key, value in quotes.items():
        grade = _integer(key, "报价等级", 1, 20)
        if str(grade) in parsed:
            raise ValueError("报价等级重复")
        parsed[str(grade)] = _integer(value, "宝石报价")
    units = {1: 1}
    for grade in range(2, 21):
        units[grade] = 2 * units[grade - 1] + sum(units[x] for x in _EXTRAS.get(grade, []))
    grades = list(range(current + 1, target + 1))
    missing = [str(g) for g in grades if str(g) not in parsed]
    subtotal = sum(parsed.get(str(g), 0) for g in grades)
    return {
        "calculator": "ordinary_gems", "scope": "梦幻西游电脑版时间服：普通宝石",
        "gemType": gem["id"], "gemName": gem["name"], "currentForge": str(current), "targetForge": str(target),
        "addedForgeSteps": str(target - current), "quoteTotalLiang": None if missing else str(subtotal),
        "knownQuoteSubtotalLiang": str(subtotal), "missingQuoteGrades": missing,
        "baseUnitsLowerBound": str(sum(units[g] for g in grades)),
        "targetStoneBaseUnitsLowerBound": str(units[target]) if target else "0",
        "rawStatDelta": {"key": gem["stat"], "label": gem["statLabel"], "value": str((target-current)*int(gem["perStep"])), "unit": "原始装备属性"},
        "allowedSlots": list(gem["slots"]),
        "steps": [{"grade": str(g), "quoteLiang": str(parsed[str(g)]) if str(g) in parsed else None, "baseUnitsLowerBound": str(units[g])} for g in grades],
        "explanations": [
            "逐级镶嵌，每一级都需要对应等级的同类宝石；报价合计使用全部新增等级，不只取最高一级。",
            "材料下限按普通宝石两颗同级合成及2024-05-21额外材料规则递推；不含失败损耗、体力、手续费或库存抵扣。",
            "材料下限不是预计花费；最高等级单颗材料量与本次全部锻炼材料量分开显示。",
            "属性变化仅为宝石增加的原始装备属性，不是角色最终面板、实战伤害、治疗或生存提升。",
            "使用前核对装备部位、最多两种宝石、装备等级/10锻炼上限及无级别例外；此函数不判定装备可用性。",
            "本次新增锻炼全部使用所选宝石；报价单位为游戏币两，未知报价不按0计算。",
        ],
        "citations": _sources("gems", "amendment"), "checkedDate": CHECKED_DATE,
    }


MAX_INPUT_BYTES = 1024 * 1024


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON含重复字段：" + repr(key))
        result[key] = value
    return result


def _json_integer(text):
    if len(text.lstrip("-")) > 30:
        raise ValueError("JSON整数过长，请使用至多30位的整数字符串")
    return int(text)


def _reject_float(_text):
    raise ValueError("JSON数值只接受整数，不接受小数、指数形式或非有限值")


def _reject_boolean(value):
    if isinstance(value, bool):
        raise ValueError("资源输入不接受布尔值")
    if isinstance(value, dict):
        for item in value.values():
            _reject_boolean(item)
    elif isinstance(value, list):
        for item in value:
            _reject_boolean(item)


def read_resource_input(filename):
    """Read a bounded regular JSON file, with strict data-only parsing."""
    path = Path(filename)
    if path.is_symlink():
        raise ValueError("输入必须是普通文件，不接受符号链接")
    if not path.is_file():
        raise ValueError("找不到输入普通文件：" + str(path))
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("输入必须是普通文件")
        if info.st_size > MAX_INPUT_BYTES:
            raise ValueError("输入文件超过1 MiB限制")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("输入文件超过1 MiB限制")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_json_pairs,
                       parse_int=_json_integer, parse_float=_reject_float,
                       parse_constant=_reject_float)
    _reject_boolean(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线计算普通修炼或普通宝石资源；不预测战斗效果")
    parser.add_argument("input", help="UTF-8 JSON普通文件，最多1 MiB")
    parser.add_argument("--kind", required=True, choices=("cultivation", "gems"), help="计算类型")
    parser.add_argument("--output", help="新输出文件；已有文件绝不覆盖，省略时输出到终端")
    args = parser.parse_args(argv)
    try:
        data = read_resource_input(args.input)
        result = (cultivation if args.kind == "cultivation" else gems)(data)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with Path(args.output).open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        else:
            sys.stdout.write(rendered)
    except FileExistsError:
        parser.error("输出文件已存在，未覆盖；请换一个新文件名")
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        parser.error("无法完成计算：" + str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
