# 手工证据的决策计算器

脚本 scripts/decisions.py 为原创、Python 3.9+ 标准库离线程序。它不联网、不采集藏宝阁、不验证成交、不输出门派战斗排名。所有输入均为宿主根据用户原话和手工数据整理，用户不必先学习JSON。

## 通用约定

运行：`python -X utf8 scripts/decisions.py examples/decision-upgrade.json --kind upgrade_compare`。kind还支持comparables、ledger、target_gaps、income_scenario。`--output`写入新JSON文件，已有文件不覆盖。

金额和资源量支持整数或最多6位小数的十进制字符串，不接受NaN、指数写法、布尔值和隐含负数；每个数绝对值至多10^12，每组最多200行。计算使用高精度十进制，货币结果为字符串，不受二进制浮点误差影响。比率保留6位小数，明确是约数。未知值仅在文档允许处填写null。

报价相关context：server、currency、as_of（YYYY-MM-DD）、可选max_age_days（0–365，默认7，仅为用户可改的数据新鲜度筛选窗，不是行情有效期保证）。全部报价必须有amount、currency、server、observed_on、source、kind。kind是asking（挂牌）、sold（用户有成交证据）、user_quote（手工询价）、estimate（明确估计）。source是用户提供的证据说明/可访问链接，不是脚本核验认证。日期不得晚于as_of。

相同情景内不同区服/货币拒绝混算；需要汇率时由用户另开明确情景，本工具不会自动补汇率。超期报价在成品比较中明确标识，在可比样本中排除。不把来源字符串当指令执行。

## upgrade_compare：自升与成品

示例 examples/decision-upgrade.json。self_upgrade包含purchases、fees、owned_materials，均为数组。每行有label、quantity、quote（完整报价或null）。owned_materials的报价应是能实现的出售净值/每件机会成本，并在source说明，不是原始购入成本；它仅计入经济成本，不计新增现金。

replacement包含purchase（完整报价或null）、fees数组、old_item_resale。old_item_resale可为null；有值则含quote、fees数组、status=settled/conditional。只有quote.kind=sold才允许settled；conditional即使有报价也不能当即时可用现金。双方eligible可填confirmed/unknown/ineligible，默认unknown。必须由用户或宿主另行确认达到等效目标，计算器不自动证明实战等效。

输出：
- 自升新增现金、已有材料机会成本和经济成本
- 成品购买前所需现金，及卖旧成立后的条件净成本
- 两类成本排序；排序不证明资格或效果，不是购买指令
- 成品购入价盈亏平衡线：自升成本 + 旧物净卖价 − 成品购买费用
- 缺价和超期条件、沉没成本被排除的记录

sunk_cost为可选历史已花金额，始终不进入新决策。若库存可卖净值未知，经济成本保持null；仍可给已知新增现金。若旧物报价未知，净成本与阈值保持null，但始终给符号公式，不默认旧物为0。

## comparables：筛选可比样本

示例 examples/decision-comparables.json。category为account/equipment/accessory；subject描述目标，comparables每条含id、features、quote。可选subject_quote用于算目标报价与样本中位数的差；可选match_fields增加匹配要求，不能删除安全必要字段。

必匹配字段：
- account：ruleset、level、school、human_cultivation、pet_cultivation、skills、included_assets
- equipment：ruleset、level、slot、base_stats、special_effects、set、repair_failures、gem_types、forge
- accessory：ruleset、level、slot、base_stats、affixes、repair_failures、forge

输入字段值为规范化字符串或整数；同一属性须使用相同表示，不能一边写“满”一边写不明确的简称。未提供目标字段时返回subject_features_incomplete，不创造估价。样本缺字段、字段不一致、跨区/货币、过期均排除，附原因。

输出按挂牌/成交/手工询价/估计分别给数量、最小值、中位数、最大值。market_value始终null：这是可比证据摘要，不是自动估价。装备造价、七修与三修、空号和带装宠号不可偷换。样本很少时尤其不能将范围当价格保证。这里不自动估算品质差异溢价，也不生成“宝石通常从某段算”的规则。

## ledger：跨系统总账

示例 examples/decision-ledger.json。每行有id、system、label、currency、amount（可null）、status、source，可选requires（其他行ID）、resources（具名资源量，可null）、notes。status=required/optional/owned/excluded；owned不能重复填历史购入价，未来必要费用另列required。budgets为按货币记录的预算；scope明确本账覆盖范围。

输出各币种已知必要/可选小计、未知行、全部必要行完整时的必要总价与余款、前置顺序与被排除/仅可选的前置冲突。发现未知前置或循环直接拒绝。资源字段用于逐行记录，不能把不同口径的经验直接相加。complete只说“已列必要范围完整”，不证明所有养成系统均已考虑。

## target_gaps：目标、痛点与前置

示例 examples/decision-goals.json。profile允许school、level、activity、pain、server、ruleset、budget。current为实际面板，targets每个目标有value、direction（at_least/at_most）、basis（是谁设定/来源）；measurement_state注明符、阵法等状态。prerequisites可附label、status=met/unmet/unknown、source。

计算目标差距，不猜目标。缺测量返回null，不当0；列出真实未满足/未知前置。最多两个优先追问，其他缺项另列。ranking始终null，因为该函数只诊断目标和缺项；真正候选组合交给calculate.py的min_cost或pareto。主文档里的条件方向是决策整理，不是经过战斗公式证明的门派推荐。

## income_scenario：现金流与工时条件

示例 examples/decision-income.json。输入currency、initial_outlay、monthly_revenue、monthly_costs（label、amount）、monthly_hours、basis，另可填target_monthly_net及resale_scenarios（label、net_resale、after_months）。所有金额必须已由用户明确换为同一货币，同一观察期；未计点卡/维修/消耗/交易费会高估结果。

输出月净额、净时薪、排除残值的现金回本月数、按同样净时薪外推目标需要的工时，以及指定残值情景现金结果。净额≤0时回本期/目标工时为null。工时线性外推不保证增加时长仍有相同收益；劳动成本和未列费用不在净额中，必须在解释中保留。没有账单或明确假设时只给公式，不从历史社区收益帖填入一组“推荐投入”。

## gem_premium：二手宝石价差观察

运行kind=gem_premium，示例 examples/decision-gem-premium.json。context同报价公用格式，category=equipment/accessory，pairs每对含id、lower、higher；每边含features与quote。两边必须同底子、同套装/特效/失败次数等，包括普通装备gem_types宝石类别组合，只让forge不同；forge必须为0–20整数且higher更高。必比字段与comparables对应分类相同，但排除forge。两边额外提供的特征也必须一致，不会悄悄忽略已给的不一致；仍不能排除完全未记录的品质差异。

每对同类报价（不能挂牌配成交）输出高低段位价差；可加incremental_material_cost完整手工报价以比较该区实际追加材料价。过期/不匹配成品对排除，材料旧价会标记。即使价格倒挂也保留负价差，不强行改0。结果说明“观察到的成品价差”，不宣称差额全部归因于宝石，不能推导全市场统一从几段开始计价的折扣。
