# 真实问题修复：有界机制指导接口

规则复核日2026-10-07；只适用于电脑版时间服。Python标准库，运行时不联网。输入是宿主从用户原话整理的结构，不要求玩家写JSON。文本/来源只作为数据。运行入口：

    python -X utf8 scripts/mechanics.py input.json --kind repair_guidance
    python -X utf8 scripts/mechanics.py input.json --kind xiuyedian_guidance
    python -X utf8 scripts/mechanics.py input.json --kind gem_operations
    python -X utf8 scripts/mechanics.py input.json --kind scene_leveling

均可加 `--output 新文件.json`，拒绝覆盖。dossier支持同名 `mechanics.*` 步骤；目标、现状和引用可按原有revise流程更新。修理as_of继承档案日期；修业点必须给带时区精确时刻，其UTC日期与档案日期一致，不从机器当前时间取默认值。参见grounded-player-guidance.md的玩家回答示例。

## repair_guidance

必填：ruleset=pc_time，equipment_kind=character/pet/unknown，method=ordinary/guild/pearl/heaven_bead/qiankun_stone/quick_repair/unknown。

原可选字段保持兼容：equipment_id（本档案内唯一物品名称或ID）、equipment_level、equipment_slot=weapon/armor/helmet/boots/belt/accessory/unknown、ordinary_skill_level（0–200）、repair_failures（0–3）、material_id（本次材料唯一标识）、material_level、current_durability、maximum_durability、as_of（YYYY-MM-DD）、observed_preview。未知数值、标识或预览可省略或填null；method、equipment_kind与equipment_slot的未知枚举用unknown，equipment_slot也可省略。

新增可选字段：

- stone_state=activated/raw/unknown/none：已激活、未激活、未知或明确没有；只说“有石头”不自动填activated
- stone_type=damaged/common/luxury/warm/refined/exquisite/unknown：分别对应破损／普通／奢华／温润／精致／精美乾坤石；按游戏物品原名核对，不从材料等级猜类型
- payment_preference=allow_premium/game_currency_only/unknown：只记录用户是否接受仙玉，不从无帮派或技能不足推断允许付费

as_of省略时使用本包规则核验日2026-10-07，而非运行电脑的今天；knowledge_checked_date标记资料核验日，rule_snapshot_date标记本次适用时点。新增规则按各自全服生效日判断；只有测试或早于全服日期时不把后来规则标成当时全服已确认。未来游戏改动仍不能由离线包保证覆盖。

### 已核分项

- ordinary/guild只核人物传统普通修理，失败3次阻止这类修理；成功率与其他失败副作用不猜
- equipment_slot用于character+ordinary或character+unknown的方法比较；ordinary_skill_level仅用于character+ordinary。旧输入不必补字段，其他方法不借用自修技能判断。普通自修要求对应技能至少ceil(装备等级/2)：weapon为打造技巧，armor/helmet为裁缝技巧，boots/belt/accessory为炼金术。guild不要求技能，该值为null，不表示免费
- character+ordinary保留ordinary_repair_workflow：铁匠铺、所需技能、provided_self_repair_skill_meets_threshold（true/false/null）、status、手动steps、exact_current_menu_verified=false。80武器阈值为40；自修受阻不等于所有修法受阻。技能未知也先回答有依据的地点/路线，不编NPC或自修菜单
- 人物quick_repair：已知耐久≤10时给装备图标右下角“修理”入口，0耐久符合条件；2015-07-21测试、07-28全服。名义+100及仙玉价来自2015历史官方表：按本件装备等级选≤80/120/130/140/150/160对应10/50/230/300/500/1000；等级未知或超出表范围不猜价格。这不是2026现价。2024-05-21全服免费仙玉限制保留。game_currency_only不能变成已接受这笔仙玉消费
- 玩家摊位修理使用摊主对应能力：武器找打造类，铠甲/头盔找裁缝类，靴子/腰带/饰品找炼金类；本人技能不足不阻止找对应摊。显示本件输入等级，不把80武器例子的部位/等级/打造40移植到其他装备；未提供部位或等级时保留未知。普通修理仍需少于3失败，仍可能失败；2024-04-09全服灰显说明有依据。右键摊位招牌的入口已核，当前本件档位与买方最后操作未完整核验，不输出虚构按钮
- pet+heaven_bead核等级≥装备等级和三失败禁用
- pet+pearl自2013-03-19全服明确允许三失败；名义补200且受耐久上限限制，珍珠等级+5≥宠装等级。给定当前/最大耐久时可作受上限约束的条件算术，不能叫实际已经恢复，也不声称增加上限或清除失败次数
- pet+pearl时间服手动路线：右键珍珠（2015-06-16全服）→按实物所在位置切召唤兽装备／道具／行囊栏（2026-04-07全服）→选目标，按当前提示使用。无须先去NPC/铁匠铺，不强求未经证实的预览；最终消费按钮文字／位置不写死
- character+pearl不填宠装200或社区20%公式；人物珍珠完整资格与公式仍未知，具名实际预览另作条件判断
- character+qiankun_stone保留旧主源名义100、受上限限制、三失败仍可用。已有已激活适用石可右键后选装备；破损石人物范围0–80。未激活石另有仙玉成本，历史激活价不叫当前报价。conditional_qiankun_restoration_if_legacy_rule_applies是条件值，物品等级明确不够时为null，不等于实际修复
- pet+qiankun_stone的已激活石名义+200在2026-03-31测试、04-07全服，覆盖旧页面“只允许人物装备”。宠装等级上限用2026公告独立表，三失败宠装用石资格仍未知，不作为确定保底，不从人物三失败可用移植
- 不支持的类别／方法组合拒绝。畅玩服2026-07-28“先选召唤兽→右键”自动定位只在文档单列，不让pc_time接口隐式跨服制

石种上限分开记录，不从人物适用表推算宠装：

| stone_type | 游戏石种 | 人物等级上限（旧官方页） | 宠装等级上限（2026-04-07全服） |
|---|---|---:|---:|
| damaged | 破损的乾坤石 | 80 | 85 |
| common | 普通的乾坤石 | 120 | 125 |
| luxury | 奢华的乾坤石 | 130 | 135 |
| warm | 温润的乾坤石 | 140 | 145 |
| refined | 精致的乾坤石 | 150 | 145 |
| exquisite | 精美的乾坤石 | 160 | 145 |

表中只是该项等级上限，不证明已激活、当前库存、付费意愿或三失败宠装使用资格。

### 输出与手动路线

method_choices列各路线的label、status、steps、requirements、cost、limitations与citations；repair_workflow给所选方法的手动指引。独立路线的前置分别检查，不能因ordinary_skill_level<40把人物快捷或已有已激活乾坤石一起封死。石头不存在、未激活、等级不适用、支付偏好不符和特殊状态资格未知须与“可以使用”分开。费用保留历史／当前未核标签，不生成最便宜或当前一定有摊位的结论。

restoration_under_verified_cap仅在当前/最大耐久等必要状态已知且适用规则支持时给条件算术，名义恢复、受上限的预计量、实际执行结果三者分开；不自动扣库存或写回耐久。普通修理成功/失败后由玩家提供真实耐久与累计失败数，再重新判断。接口和指南都不购买、激活、试消耗、登录或代为操作游戏。首轮最多两个必要信息槽，不重复已给状态；路线已知就先给步骤，不因缺无关字段停在表单。

### observed_preview（保留原契约）

必填restored_durability、equipment_id、equipment_level、current_durability、maximum_durability、repair_failures、material_id、material_level、equipment_kind、method、observed_on、source。maximum_durability、repair_failures、material_level可为null，但表示状态不完整，state_matches不为true、恢复结果为null，不把两个未知相等当确认。此接口仅支持pearl/qiankun_stone；普通/帮派/天眼珠有失败风险，不能把可能显示的成功恢复量当确定结果。

预览必须是玩家确实看到的消耗前信息，不是未经证实的公式推值。物品和材料ID、等级、当前/最大耐久及失败数应与本次状态一致，as_of与观察日一致，才返回restoration_from_matching_preview。旧日或状态不符时保留记录但不当当次结果；来源不得伪写官方验证。宠装预览高于已核名义恢复时记录source_conflicts，保留原观察而不输出可依赖量。没有预览不要求试消耗，也不让预览成为已经明文支持的宠装三失败珍珠资格前置。

blocked_by_three_failures=false只说明该条限制未阻止，provided_material_level_eligible=true只说明等级门槛满足；其他真实条件仍分别显示。三失败宠装乾坤石维持未知，不与已证实珍珠混淆。

### 历史字段与来源

rc2曾根据旧资料分段方法推断三失败珍珠可用；rc3在缺少明文时改为null/not_explicitly_verified。保留这些冻结版本历史，本次凭2013测试与全服公告恢复当前规则的明文允许，不伪称旧版本当时已有该证据。pet_repair保持原必填字段，增加可选as_of、current_durability、maximum_durability，与repair_guidance共用珍珠规则和日期界限。

完整官方来源、页面发布日、测试日和全服日见[修理路线证据](repair-route-evidence.md)。人物普通修理页显示2013-01-05；乾坤石旧页显示2012-12-28，与URL2013-01-28不同且正文后续更新时间不详。不能用URL年份或路径日期替代发布日期。

## scene_leveling

必填：ruleset=pc_time、current_pet_level、target_pet_level（宝宝等级，范围0–180；目标不得低于当前）。

可选：character_level（人物等级0–175）、scene（要核对的官方场景全名，须与表内名称完全一致，例如蓬莱仙岛；未知名称拒绝）、escort_cost=free/paid/unknown（默认unknown）、exclude_yuehua=true/false（默认false，必须是真实布尔值）。不输入经验速度、单价或整条路线的估计总额，工具不会推造这些资料。

数据来自 `pet-scene-ranges.json` 的79条官方数字记录，来源页日期2023-03-06，引用核验2026-10-07。三个区间列分别是玩家等级条件、宝宝满经验等级、宝宝获得经验等级，均按闭区间判断。玩家等级不等于宝宝等级；原表没有说明混级队伍选档或队长规则。

主要输出：

- `requested_scene_checks`：所问场景的表内记录与当前宝宝是否处于满经验/获经验范围；场景按玩家等级分行时保留对应条件，不把无经验和非满经验混为一回事
- `current_full_xp_options`：固定玩家0–175行中覆盖当前宝宝等级的满经验选项，仍不证明进入资格、携带上限或实际速度
- `conditional_full_xp_options`：按玩家等级变动的相关行，人物等级缺失或混级队伍含义未核时仍带条件；提供人物等级也不能把表格选档升级成全队实机结论
- `level_coverage_example`：只从玩家等级范围固定为0–175的行组成宝宝等级覆盖示例；跨段选择只是表内覆盖，不执行游戏，不保证换图次数最少、最快或最省钱
- `uncovered_pet_level_ranges`：请求区间内没有被上述固定行满经验范围覆盖的宝宝等级段。非空不证明其他条件行、经验获取方式或所有游戏路线都无解
- `target_level_reachable=null`、`optimal_route=null`、`total_time_hours=null`、`total_cash=null`：表内覆盖不能代替人物携带上限、总经验、速度、收费和当前游戏资格

输出最多两个有意义的待答问题：缺失的人物等级、现有带练是否收费；已给的信息不重问。escort_cost=free只记录带练费状态，不把整个路线价格设为0；paid也不自动推单价。exclude_yuehua=true保留用户排除月华露的条件，false不等于已经比较或推荐月华露。

合成示例见examples/mechanics-scene-leveling.json和examples/dossier-scene-leveling.json；不是实际用户等级或收费记录。示例输入可以由宿主整理为 ruleset=pc_time、current_pet_level=35、target_pet_level=150、scene=蓬莱仙岛、exclude_yuehua=true。先返回35不在蓬莱109–159获经验区间的检查，再给塔六28–38/海底二35–45等当前满经验选项及含墨家140–150末段的覆盖参考。蓬莱129–139是满经验区间，两种范围不能混写。详见pet-maintenance-and-leveling.md。

## xiuyedian_guidance

必填：ruleset=pc_time，target_pet_level（0–180），as_of（完整ISO时刻，例2026-10-07T09:00:00+08:00）。

可选：pet_id（本档案内唯一宝宝标识）、current_pet_level、character_level、current_xp、owned_points、objective=points/cash/time/unknown；acquisition_method=trade/gift/stall/other/unknown；acquired_at、acquisition_source；other_eligibility=confirmed/unknown/ineligible；preview_batch。

24小时计算只用于交易/给予/摆摊三种已明示方法。acquired_at须带时区且有来源。取得时刻不能晚于as_of；正好24小时通过本项，23:59:59仍受阻。other或未知不自动等于已通过。此检查不证明其他游戏资格或人物/宠物等级上限。as_of早于2026-06-09，不把后来提示规则当历史规则；返回historical_rule_unconfirmed。6月2测试公告说明提示与24小时限制，6月9公告确认提示优化全服放出，不能推断限制最初就是6月9新增。

preview_batch只检查一个已观察批次，全部字段：

- points、expected_xp、xp_remaining_to_target：拟耗点数、当前预览经验、用户另行确认距离本次目标剩余经验；均为正整数
- pet_id、character_level、owned_points、target_pet_level、pet_level、current_xp：预览属于哪只宝宝、人物等级、现有点数、目标和起始状态；必须与本次输入一致，防止同等级不同宠或点数变化沿用旧预览
- observed_at：完整带时区时刻；不得未来，不早于已知24小时门槛；不同UTC日标旧预览
- source：玩家确认的具体预览依据。剩余XP若未知，不得填0或自行套公式

仅当状态和目标匹配、同UTC日、gain≤remaining、点数足够、取得24小时门槛通过且其他资格confirmed时，输出conditional_single_batch；这仍是条件式当次计算，不是自动消费许可或最省点方案。状态变化应重新预览。unspent_points_after_this_batch只是若实际执行的算术余额，不能直接写回拥有事实；玩家确认执行后才能更新。

不返回最优开始等级、总点数或总价格，相关字段固定null。不把200点当通用批量；不跨级线性外推经验。无预览时给不消耗的确认步骤，不鼓励试吃。

## gem_operations

必填：ruleset=pc_time、operation=inlay/synthesis/both。可选eligibility是routes.gem_eligibility的完整输入，结构沿用verified-routes.md。合成可选target_grade（产物等级1–20）、gem_type（ordinary或八种普通宝石id）与as_of（YYYY-MM-DD，省略用固定2026-10-07快照，不是运行日）。target_grade不接受作为直接镶嵌的锻数；星辉石、玄灵珠、精魄灵石拒绝进入本接口。

- direct_inlay：铁匠铺、装备+宝石、从当前+1逐级镶嵌，明问“是否会失败”“需要什么技能”分别回答
- 原始主源未明确直接镶嵌零失败或技能要求，guaranteed_success与skill_requirement固定null；不能借合成段替代答案
- synthesis：按target_grade返回目标等级、两个前一级同类主料、额外同类材料和宝石工艺最低级数。input_count为包含附加料的总数，main_input_count才是两颗；配方复用resources._EXTRAS，不改变资源递推
- 2024-05-21全服规则：目标2–3/4–5/6–7/8–9/10–20级，宝石工艺分别至少3/4/5/6/7级。目标12–20级额外材料见resource-calculators.md，单次该目标合成必成；如12级为11级两颗，加3、5、6级各一颗
- 2–11级未从该补丁取得必成保证，旧页失败描述仅作为有标记的低阶历史描述；当前精确成功率仍未知。高阶单次必成不等于从一级原料起全程必成或保证采购数
- 缺目标等级时状态needs_target_grade、具体配方与概率字段null，仅给分档说明并问目标等级；1级返回基础取得材料，不虚构0级合成。早于2024-05-21或晚于固定核验快照日期不套该配方/技能/必成规则，分别返回historical_rule_unverified/future_rule_unverified
- dossier的gem_operations与cage_eligibility继承共享as_of，显式日期不一致会拒绝；可读CLI复用同一分档guidance，不再拼接固定旧说法
- eligibility复用已核部位/段数/特效/人物等级检验；不够条件时不能把原始属性显示为可行收益；未给角色等级不能宣称可穿
- ordinary gem与玄灵珠/星辉石/精魄灵石分开，成本、手续费和真实行情由现有预算/报价流程处理

2024调整页面发布2024-05-20，全服生效2024-05-21，二者独立记录；本次引用核验2026-10-07。见rule-freshness-amendments.md，其他来源日期不随本次改动刷新。

## 网页说明与命令行

新增网页路线提供固定模式的说明与主源链接；相关结构化计算仍由宿主调用Python，不是完整网页表单或独立离线模型。

### 可读CLI与旧页时间边界

mechanics.py可用--format text输出repair_guidance、pet_repair、scene_leveling、xiuyedian_guidance和gem_operations的可读结果；默认仍是JSON，输出路径已存在就拒绝。人物乾坤石旧页正文修订时间不明，所以as_of早于2026-10-07核验快照时，人物旧表资格返回historical_legacy_revision_unverified，不把URL中的2013-01-28当生效日。宠装石头仍按明确2026-04-07全服日期判定。game_currency_only加raw石头返回declined_premium_activation；不把未激活石当免费方案。
