# 算法、输出与限制

## 两个一致的精确引擎

Python 3.9+ 使用标准库 Decimal（局部精度 60 位）；现代浏览器使用 BigInt 定点数，原始属性/金额/权重缩放 10^6，乘积偏好分缩放 10^12。浏览器自编 JSON 解析器保留数字原始标记，避免 JSON.parse 先转浮点而丢精度。没有第三方代码、CDN、后端或网络计算。

每个候选的单槽位增量为 deltas 或 measured_stats−baseline.stats。组合增量为逐指标相加，最终面板为基线加增量。花费为报价加费用，不扣未确认出售收入。

仅 weighted 模式计算偏好分 = Σ（用户权重 × 方向符号 × 组合增量）；maximize 符号 +1，minimize 为 −1。这是用户定义的线性偏好，绝不是战斗、伤害、回报率或胜率公式。

## 枚举、限制与排序

对各槽位“保留当前”或“选一候选”的选择作笛卡尔积。枚举前检查理论组合数，不能靠低预算绕过上限。逐方案检查预算、面板上下限、锁定、必选、排除、冲突和更换件数；只在可行组合中排名。

objective 选择三种目标：
- weighted：偏好分降序；同分时花费少优先，再更换件数少优先，再按槽位排序后的候选 ID 字典序
- min_cost：花费升序；同价时更换件数少优先，再按槽位排序后的候选 ID 字典序。只优化录入条件下的新增花费，不用权重或额外属性作隐含平局评分。同价方案可能不止一个；best 为确定性代表
- pareto：不选唯一赢家，best=null、alternatives=[]；前沿仅按花费、件数、候选 ID 展示，这种展示顺序不是推荐排名

省略 objective 时，有 weights 兼容旧版 weighted，没有 weights 默认为 pareto。不生成默认权重，非加权组合 score=null。相同输入得到确定性结果。min_cost 允许没有面板目标，但会提醒；已满足全部约束的当前装备通常为最低花费。

budget_scenarios 和 weight_scenarios 共享候选空间，分别改变预算或使用明确的高级权重。预算情景沿用主 objective，Pareto 预算情景精确重算其完整前沿后再受展示上限截断；其他情景只返回该目标下的 best。权重情景明确使用 weighted，即使主方案没有 weights。manual_plans 单独精确计算并如实标记违反的条件。

零花费、零变更基线总会显示，即使不满足用户设定目标或必选条件。所有可行组合不存在时 best=null，不把基线冒充达标方案。免费备用装备可能支配原基线；“不花钱”不一定等于“不换装备”。

## Pareto 与负面取舍

花费越少越好，各指标按用户选择方向逐维比较；A 每维不差于 B 且至少一维严格更好时，A 支配 B。权重为零的指标也参加 Pareto 比较。只比较本次输入和限制下可行的方案。

相同价格和全部增量向量合并，保留确定性排序首项，equivalent_count 标记等价组合数量。前沿最多展示 100 个代表，weighted 按偏好排序，其他模式按花费、件数和 ID 展示；若截断，summary 会说明完整数量。weighted / min_cost 的 best 来自完整有界枚举，不受前沿展示上限影响。Pareto 模式即使只有一个向量也不把它标成游戏唯一最优。drawbacks 是按用户方向变差的指标，不能隐藏。

## 报告关键字段

- schema_version=1.0；objective=weighted / min_cost / pareto，objective_description 为可读描述；model 分别为 user_defined_linear_preferences（旧版保持不变）、user_defined_min_cost、user_defined_pareto；status=ok / no_feasible_plan
- title、notes、budget、currency、metrics、weights（未提供时 null）；character、constraints、checklist 保留上下文
- baseline：当前零变更参考、label、equipment、evidence、on_pareto，以及完整组合结构
- best、alternatives、pareto：可行方案；无解时 best=null，其余为空。Pareto 有解也保持 best=null，靠 status / feasible_count 区分，候选在 pareto
- budget_scenarios、weight_scenarios：各自 label、objective、预算/权重、best（可为 null）、feasible_count；Pareto 预算情景另有 pareto、pareto_total、pareto_shown、pareto_truncated
- manual_plans：label 和 plan，后者可以不可行
- diagnostics：数据/目标/预算与人工核对提醒，不是游戏战斗诊断
- evidence_summary：候选证据声明的计数；不代表独立验证
- summary：理论/实际枚举数、预算内数、可行数、预算内被条件排除数、向量和前沿计数、比较次数、截断状态

每个组合有 selection、price、remaining_budget、deltas、final_stats、score、is_baseline、feasible、violations、drawbacks。每件选择含报价、费用、总价、owned、evidence、source、notes、replaces。整份计划与候选 notes 会保留为人工备注，绝不自动变成计算约束。金额/属性/已使用分数与权重是普通十进制字符串；未使用加权评分时 score=null。数值不用科学记数法；计数为整数。手工不可行方案的剩余预算可以是负数。

可读文本/HTML/CSV 导出说明比较目标，包含基线、该目标适用的首选、备选、已展示的 Pareto、A/B、情景和限制说明。完整机器元数据在 JSON 中。HTML 转义所有动态内容、无脚本；CSV 对可能作为电子表格公式执行的单元格加安全前缀。负数可能因此作为文本导入，保留数值字符，不损失精度。

## 限额和失败行为

- 1 MB UTF-8 输入；最多 32 层 JSON；拒绝重复键、非有限数、无效 Unicode
- 1–12 指标、64 候选、12 槽位（候选与当前装备槽位的并集）
- 各槽位“候选数+1”的乘积不超过 10,000
- 输入数字绝对值不超过 10^12，最多 6 位小数；计算结果可以超过输入上限
- 每次主前沿或 Pareto 预算情景计算最多 2,000,000 次前沿候选对检查；超过上限即失败，不输出未经证明的部分最优结果
- 最多 8 个预算情景、8 个权重情景、2 个人工计划、128 对冲突、20 条人工清单
- 文件输出独占创建；既有输入/报告不被覆盖。浏览器下载由用户选择保存位置，不自动持久化

Pareto 预算情景也受同样的单次安全上限；任何一项超限则整份计算失败，不返回半份成功报告。10,000 组合不保证所有多指标冲突输入都能完成 Pareto。若限制过大，减少候选或指标。浏览器计算同步完成，复杂输入会短暂占用页面；保护上限不会自动降低计算精度。

## 不包含的能力

没有真实市场价格/库存、行情历史、游戏账户、自动取数、OCR、战斗模拟或伤害模型。不会自动验证装备等级与角色资格、套装/特技联动、非线性阈值、共享成本或商店交易规则。

原始 scripts/resources.py 仅覆盖普通修炼与普通宝石。新版 scripts/routes.py 另提供已核验范围内的宠修果、边界降修路线、宝石资格和星辉材料，以及手工确认经验的金丹条件算术；详见 verified-routes.md。仍不是完整规则数据库，未知失败概率与未验证机制不补造。是否购买、升级、换装及其游戏后果由使用者核实决定。
