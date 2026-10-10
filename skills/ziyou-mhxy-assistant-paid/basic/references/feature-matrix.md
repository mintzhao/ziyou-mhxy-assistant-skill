# 公开资料补查

公开规则补查与报价归一化：宿主只读联网能力有条件可用，Python本地检查来源/日期/范围/单位并连接原comparables；没有独立抓取器或网页新表单。详见 public-research-workflow.md。

# 哪个入口能做什么（基础版）

本表说明可用的功能入口与适合的使用方式。新增浏览器功能使用精确整数运算，运行不依赖 Python；自然语言 Skill 由宿主模型理解并运行本地 Python。网页关键词引导不是通用聊天模型。

## 核心决定

| 需求 | 离线网页 | Skill / 宿主 | 命令行 |
|---|---|---|---|
| 不知道该用哪个工具 | 首页明示字段解析，最多两个优先确认项；充分的普通修炼条件直接计算，原文短语核对后预填，不重问已给字段 | 理解问题、区分实际事实/举例/假设，最少追问 | 不提供自然语言模型 |
| 普通修炼 / 普通宝石数量 | equipment.html 的资源区域，可保存、重开、导出说明 | resources 工具与来源解释 | resources.py |
| 手工自升 / 换成品 | decision.html：新增现金、库存机会成本、条件卖旧、临界价 | decisions.upgrade_compare | decisions.py --kind upgrade_compare |
| 完整普通宝石自升与成品对照 | planning.html#gem_upgrade：装备资格、全部新增等级、同级库存、报价、费用、预算与成品比较 | plans.gem_upgrade，可用自动项目适配器接共同预算 | plans.py --kind gem_upgrade |
| 普通点修与经验道具混用 | planning.html#training_mix：逐种整颗方案精算、普通购次补足、道具上限 | plans.training_mix | plans.py --kind training_mix |
| 多目标共同预算 | planning.html#portfolio：预留、分类上限、前置、互斥、共享库存、已完成项目 | portfolio，可用 dossier 将已支持成本步骤真正关联 | portfolio.py |
| 装备面板取舍 | equipment.html：最低成本达标 / Pareto / 可选加权，保留现状 | 原精确装备引擎；dossier 的 equipment.optimize | calculate.py |
| 保存本次输入、改价/库存后继续 | 各网页草稿可重开；修改后必须重新计算，旧结果失效 | 单份版本化 dossier；新事实、来源、候选与依赖统一重编 | dossier.py；Python revise API |
| 已执行项目后只计划剩余任务 | 共同预算中的“已完成”项目不再收费/耗库存，可满足前置；当前余额/库存由用户更新 | dossier 保留来源和当前快照 | portfolio.completed_options |
| 一处事实自动更新所有关联步骤 | 网页三个养成表单同档保存，但没有跨表单自动成本依赖；录入的整项目成本须自己更新 | dossier 支持明确事实引用、受支持项目适配器及依赖重编 | dossier.py |

网页共同预算只优化已录入整项目的最低新增现金，不自动理解装备实战收益，不推断某项目已经完成，不生成未来出售现金或新库存。

## 扩展能力：目前仍由 Skill / 命令行使用

这些能力没有独立网页表单。用户可以直接在支持本地 Skill 的宿主里提问，不必编写 JSON；宿主负责选择工具、整理输入、执行、解释及保存。

| 功能 | 已有入口 | 边界 |
|---|---|---|
| 经验道具、宠修果、提上限/降修、普通宝石资格、星辉石 | routes.py：gold_pill / pet_fruit / cap_route / gem_eligibility / star_gem | 只计算各接口明示规则；未知品质经验须确认。普通宝石资格已包含在新的宝石网页计划中 |
| 专注、帮派技能手工逐级费用、普通宠物0–50灵性、宠装珍珠、炼兽笼资格 | mechanics.py：focus / guild_skill / pet_stage / pet_repair / cage_eligibility | 不补造全来源属性、实战伤害、完整仙露随机规则或练级总耗时 |
| 分方法修理入口/手动步骤、练宠场景区间 | mechanics.py：repair_guidance / scene_leveling；dossier同名mechanics步骤 | 首页仅有界说明，非完整表单。含人物快捷/已有石/玩家摊选择、宠装三失败珍珠右键切栏；当前买方最终菜单和现价仍未核。场景79行覆盖不证明最优或可达 |
| 同类报价、宝石溢价、分币种总账、目标差距、真实收支情景 | decisions.py：comparables / gem_premium / ledger / target_gaps / income_scenario | 用户提供近期可比数据；无自动估值、统一折扣或回本承诺 |
| 神兽、命魂玉、低级魔王、花果/凌波等有界规则说明 | GUIDE.md 对应 references | 包内核对日和适用范围必须保留；不是全游戏准确率或最新全机制保证 |
| 事实原文和计算绑定检查 | evidence.py，dossier 内建 | 验证结构与摘录匹配，不验证自然语言理解、归属或事实真伪 |

## 保存什么，在哪里重开

| 文件 | 重开入口 | 迁移 / 缓存行为 |
|---|---|---|
| 装备草稿（schema_version 1.0） | equipment.html 顶部“打开草稿” | 保留旧版权重、兼容省略 fees=0 的原契约；缺失必填数字仍未知 |
| 自升 / 替换草稿（mhxy-decision-draft v1） | decision.html“打开草稿” | 保留模式、所有报价、未知与未完成输入；未来版本拒绝 |
| 养成计划草稿（mhxy-planning-draft v2） | planning.html“打开计划草稿” | 严格迁移rc1的v1；同存三套表单、问题出处、修炼预算/预留及当前选页；不导入结果缓存 |
| 资源草稿（mhxy-resource-draft/v2） | equipment.html 资源区“打开资源草稿” | 支持v1和以前无schema导出，增加最小问题出处；丢弃旧results，须重算 |
| 单一决策源档案 / 编译bundle（mhxy-dossier/v1） | Skill / dossier.py | 重开只信源档案结构，缓存结果及其声明不被使用；按当前引擎重新编译 |
| 普通结果 JSON、TXT、CSV、HTML | 阅读与复核；装备结果JSON有独立报告查看入口 | 不是可编辑草稿。请同时保存对应草稿；不能把截图/报告当唯一恢复副本 |

没有自动持久保存。关闭或刷新前手动保存并核对下载目录；点击“生成下载”只表示代码提交了下载请求，实际落盘要由浏览器完成。各导入均有格式与大小限制，损坏、未来版本或取消导入不应覆盖当前输入。读文件期间新编辑会阻止迟到导入覆盖。

## 条件改变后怎么继续

1. 打开原草稿或让宿主读原 dossier；保留原文件副本
2. 新报价更新金额与真实来源/观察日期。把核价日改成今天不会把旧报价重新标成今天
3. 已经执行的项目明确标记完成；填写实际当前现金和剩余库存，不用上一计划的“预计剩余”代替事实
4. 修改目标或宝石种类后，先处理界面的重新核对提醒；旧价格、库存或达标声明不能自动套到新目标。共同预算保留实际完成记录，但原候选与改变后目标的关联必须重新确认
5. 重新计算，检查未知、过期、资格、分类预算和前置。未知不作零，旧物未到账不作现钱
6. 保存新草稿或新 revision，另导出可读说明；网页计算证据JSON保留输入/结果用于核对

页面受策略阻止时不绕过安全限制；本包无安装器、运行时第三方API、付费规则库、账号或发布步骤。是否付费、联网、处理对话取决于宿主服务。

问题到预填的模式、大小、未解析资料、来源及本地链接隐私边界见question-intake.md。它不是通用自然语言模型，也没有隐式跨表单同步。

## 2.2.0-rc3新增边界

mechanics.py增加repair_guidance、xiuyedian_guidance、gem_operations，dossier有同名mechanics步骤。是已知规则/单批实际预览/已有资格检查的连接，不是完整最省修业点/修理成本优化。首页新增对应说明和玄灵珠条件步骤，未新增完整输入表单或通用自然语言模型。当时三失败宠装珍珠资格曾保留未知；本次2013全服明文已闭合该缺口，当前规则见下述补核与repair-route-evidence.md。人物珍珠公式、三失败宠装乾坤石资格、直接镶嵌失败/技能仍未独立确认。玄灵珠当前库存占格语义仍缺，不支持最少跑动承诺。详见grounded-mechanics.md。

## 2.2.0-rc4路由纠正

“三修13”不是装备三次修理失败。页面不再以裸“三修”进入repair；明确三修失败、修理或宠装修复问题仍保留repair。比较题进入正确入口不等于已求出养成顺序；portfolio对备选表达仍需核对。

## 2.2.0-rc5玄灵珠条件规划

scripts/crafting.py新增独立单文件会话和逐步清单，支持2–8级一颗散珠、实际库存/容量、条件成功轨迹及手工观察后续算。它没有接入dossier自动预算项目，也没有网页合成表单；首页只给条件解释和本地用法链接。详见crafting-planner.md。

## 2.2.0-rc7修理步骤与练宠场景

repair_guidance兼容增补equipment_slot与ordinary_skill_level，仅作用于人物自行普通修理。ordinary_repair_workflow提供铁匠铺、所需技能、已给自行技能的门槛判断和有前置的手动步骤，exact_current_menu_verified=false；不会要求玩家先练技能才能尝试任何其他修法。

scene_leveling通过79条官方表内数字记录检查所问场景，区分玩家等级与宝宝满经验/获经验区间。固定玩家0–175行可生成level_coverage_example和未覆盖段；变动玩家档位保留条件，不能自行规定按队长等级选档。目标可达、最优路线、总时长和总现金保持null。首页只是带日期/来源的有界说明，结构化查询和单一档案由宿主/CLI执行；没有完整练宠网页表单。



## 2026-10-07修理路线证据补核

repair_guidance保留旧输入，新增quick_repair方法以及stone_state、stone_type、payment_preference可选字段；输出method_choices与repair_workflow，区分已核入口、条件、费用和剩余界面缺口。as_of按各条规则的全服日期约束，不把2026界面放进早期历史状态。pet_repair增加可选耐久与日期，共用已核珍珠规则。

人物0耐久满足快捷入口≤10；2015的10仙玉仅历史列价，2024免费仙玉限制保留。宠装三失败珍珠于2013-03-19全服允许，右键2015-06-16、切栏2026-04-07全服；激活乾坤石修宠装+200同于2026-04-07全服，但三失败宠装用石资格仍未知。
