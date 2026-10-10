# 配装输入约定

主计划 schema_version 继续为字符串 "1.0"，兼容早先的基础输入；新增字段都是可选项。输入 Schema 描述结构，Python/浏览器引擎再次强制验证动态指标键、引用、冲突和资源上限。资源计算页的独立输入不使用此结构，见 resource-calculators.md。

## 必填

- budget：已确认的非负新增总预算；currency：同一货币/价格单位标签，不执行汇率换算
- metrics：1–12 个 {id,name,unit,direction}；direction 为 maximize 或 minimize
- baseline：{label,stats}，stats 必须恰好覆盖当前人物每个指标的绝对面板
- options：0–64 个候选，每件必须有 id、name、slot、price 和且仅有 deltas / measured_stats 中的一项

同一 slot 最多选一个候选，未选表示保留当前装备。指标、候选、槽位 id 为小写字母开头，之后仅小写字母/数字/下划线/连字符，最长 64 字符。显示名称可以中文；未知字段和重复 JSON 键会拒绝，不静默忽略拼错的参数。

## 先选择比较目标，不必先编权重

可选 objective：
- min_cost：先用预算和全部 constraints 筛选可行组合，再找新增总花费最少的方案。把“速度至少多少”“防御不能低于多少”等已确认目标写入 min_stats / max_stats。无需 weights；同价按更换件数、候选 ID 确定展示顺序，不偷偷按面板或权重评分。当前装备已满足全部条件时，可以返回零花费零更换；没有面板目标时会提醒，并按其余已填限制找最低花费
- pareto：无需 weights，查看成本与各指标之间互有取舍的可行方案。不指定唯一最优；best=null，alternatives=[]，pareto 提供前沿。status=ok 表示存在可行方案，不能仅看 best 是否为 null 判断无解
- weighted：高级线性偏好评分，weights 必须恰好覆盖每个指标、全部非负、至少一个大于零；不归一化，不替用户编造

兼容旧版：objective 省略且存在 weights 时按 weighted 计算；两者都省略时采用 pareto。不会默认等权。min_cost / pareto 可以完全不带 weights；如仍提供 weights，会验证其完整性并保留，但不用于主方案评分或平局排序。未使用加权目标的组合 score=null，无主权重时报告 weights=null。

正常表单先选“达到目标后尽量少花钱”或“先看各方案取舍”；权重仅在高级模式出现。空白模板使用无权重 Pareto，旧的带权重示例和草稿保留原算法。

最小达标省钱示例（纯合成数值）：

```json
{
  "schema_version": "1.0",
  "objective": "min_cost",
  "budget": 10,
  "currency": "合成单位",
  "metrics": [{"id": "speed", "name": "速度", "unit": "点", "direction": "maximize"}],
  "baseline": {"label": "合成当前面板", "stats": {"speed": 100}, "evidence": "synthetic"},
  "constraints": {"min_stats": {"speed": 110}},
  "options": [
    {"id": "a", "name": "合成候选 A", "slot": "shoes", "price": 4, "deltas": {"speed": 10}, "evidence": "synthetic"},
    {"id": "b", "name": "合成候选 B", "slot": "shoes", "price": 8, "deltas": {"speed": 20}, "evidence": "synthetic"}
  ]
}
```

结果为花费 4 的达标方案 A，不需要权重，也不会因 B 属性更高就建议多花钱。改成 objective=pareto 后两个候选均为不同取舍，没有唯一赢家。

## 数字和草稿

数值必须是 JSON 数值，不能带引号。有限数、绝对值不超过 10^12，输入小数位最多 6 位。价格、费用和预算非负；负属性增量合法。输出金额、属性及已使用的权重、分数均为十进制字符串，保证跨环境精度；计数仍是整数。

输入中的 null、空值或缺少指标表示未知，不会补零。省略非必需 weights 不代表缺少面板数据。浏览器可以保存未完成草稿，--check / 页面诊断会列出待填项，但计算会被阻止。确认为不变才填写 0，确认为免费才填价格 0。精度限制按原始数字标记检查，0.1000000 也超过六位小数，请写成 0.1；科学记数法按其实际小数位检查。

## 基线和候选

baseline 可加 equipment（槽位 id 到当前装备名称的对象）、evidence（user_confirmed / unverified / synthetic，默认 unverified）。这些状态是用户声明，工具不独立核实。

候选字段：
- deltas：同一测试状态下，相对该槽位当前装备的净人物面板变化，完整指标对象
- measured_stats：只更换该件装备后完整人物面板。程序减去 baseline.stats 得到净增量；不能填装备自身原始属性
- price：购买报价/新增投入；fees：额外必要费用，默认 0。组合花费为所有 price+fees 之和
- owned：布尔值，默认 false。为 true 时 price 必须为 0，仍需支付的改造等费用可以填 fees
- evidence：同基线，默认 unverified；source：最多 1000 字符的依据，可写区服、报价日期和费用范围；notes：最多 4000 字符

套装联动、共享前置费用和多件联合才生效的效果不能被各件独立相加。程序不自动分摊或去重共享费用；请将这些方案分开比较，或先由用户确定互不重复的净成本。未确认售出收入不抵扣。

## 限制 constraints

所有字段可省略，省略表示没有该限制：
- min_stats、max_stats：部分指标到绝对最终面板目标的映射；下限不能大于上限
- locked_slots：保留当前装备的槽位 id 列表；须出现在候选或 baseline.equipment
- required_options：必选候选 id；excluded_options：排除 id
- conflicts：最多 128 对不同候选 id，表示不能同时选；支持跨槽位冲突
- max_changes：0–12 的整数，默认 12

同槽位多件必选、必选又排除、必选替换锁定槽位、互相冲突的必选项会被拒绝。正确但预算不足或目标不可达的输入不会被当成格式错误；结果 status=no_feasible_plan，best 为 null，基线仍保留并列明未满足条件。

## 情景和手工 A/B

- budget_scenarios：最多 8 个 {label,budget}，沿用主 objective 和限制，不改变主预算；Pareto 情景返回各自前沿和截断计数，best=null
- weight_scenarios：最多 8 个 {label,weights}，明确的高级加权试算，必须提供完整权重对象，沿用主预算和限制；主模式为 min_cost / pareto 时也不需要主 weights
- manual_plans：最多 2 个 {label,option_ids}，空列表就是当前装备。超预算或不满足目标允许展示，但会标明不可行；不存在的 ID、重复项和同槽位多选会拒绝

各组标签必须唯一。情景重算本次候选，不推测未来价格、预算或市场可得性。零预算可以选择已确认免费备用装备，零变更当前基线始终单独显示。

## 背景与确认清单

可选 character={level,school,server,purpose}，字段均可省略。level 为 1–200 整数，仅作背景，不验证门派/等级/区服资格。不要输入账户身份或密码。

可选 checklist 最多 20 个 {item,status,note?}，status 为 confirmed / unverified / not_applicable。它记录人工核对事项，例如临时符状态一致、报价费用齐全、套装特技联动、装备使用资格。未确认项目不自动阻止数学计算，但报告会保留提醒。

可选 title、notes、top_n；top_n 为 1–50，默认 10，控制 weighted / min_cost 的 best 与 alternatives 合计显示数；Pareto 前沿独立最多显示 100 个，并报告截断。
