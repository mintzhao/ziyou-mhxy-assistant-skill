# 单一版本化决策档案（host 接口 v1）

`scripts/dossier.py` 把事实、当前快照、计算步骤和依赖放在一个源档案里。宿主从自然语言维护、保存、重开和解释；玩家不必写 JSON、拼命令、手工复制每次计算后的总价。没有联网、安装、账户、收费接口或表达式执行。

只在连续预算/状态联动或保存重开确有需要时使用本接口。可靠规则短答、直接转述来源数字和单次独立计算不要求建档；有依据的简单算术用最小通用计算，支持的领域计算用最小对应工具。该轻量选择不关闭来源、单位、binding或领域资格/精度守卫。

## 最小工作流

1. 宿主整理本次区服、币种、核价日和用户当前状态；分开已确认、条件、未知、冲突
2. 把会变化的数据放在 `facts`，`snapshot` 用 `$fact` 引用同一值。库存同时出现在单件与总计划时，两处必须引用同一个库存事实
3. 声明 allowlist 中的计算步骤。使用 `project.gem_upgrade` 自动生成宝石现金/库存行，或 `project.cultivation` 重新生成普通修炼规则现金/帮派资材消耗；总计划直接引用生成的 `option`
4. 每次新报价/库存/进度变化只修改对应事实并记录本轮来源，建立新 revision，重编整份档案
5. 给玩家当前结果和易读报告，保存完整 JSON bundle；旧版本不覆盖

包根目录命令：

    python -X utf8 scripts/dossier.py examples/dossier-original-v1.json --format text
    python -X utf8 scripts/dossier.py examples/dossier-original-v2.json --output new-v2-result.json
    python -X utf8 scripts/dossier.py new-v2-result.json --format text --output reopened-v2.txt

`--output` 使用排他创建；已存在文件或软链接会拒绝。省略路径输出终端。JSON 输出是可再次直接输入的完整 bundle；易读文本是说明，不是可回读的数据文件。没有自动联网补价或自动改核价日。

宿主确需读取编译后的当前快照时，正确路径是 `compilation.resolved_snapshot`，例如 `compiled = compile_dossier(source_or_bundle)` 后取 `compiled["compilation"]["resolved_snapshot"]`；不是 `compilation.snapshot`。继续计算仍从源档案/可回读bundle重新编译，不手工复制缓存结果，也不为简化适配而关闭来源、单位或binding校验。

## 原创三轮演示

三个 `dossier-original-v*.json` 均是虚构测试，绝不代表真实玩家、市场价或购买建议：

- v1：鞋8→10段、已有1颗9级黑宝石、10级报价64两，总预算140、保留20。重算新增现金64，库存占用1，机会成本27另报
- v2：仅10级报价事实改为103两，生成新版本。单件现金、portfolio项目成本、计划最低现金都自动变为103；不维护第二份总价
- v3：用户情景为已完成10段、9级库存已耗尽，当前锻数10、库存0、已达成目标标记同步到本轮快照。重算采购0、资源消耗0，总计划保留现状0花费；旧v1/v2不改动

只改库存1→0而未完成升级时，还会自动补回9级购买行，现金64+31=95。程序不推断一次计划已经实际执行：完成目标、付款、库存已消耗等都是用户新事实，不能靠上次的建议自动扣库存。

## 源档案字段

严格拒绝未知顶层字段：

- `schema`: `mhxy-dossier/v1`
- `id`: 1–64字符 ASCII 标识符，首字符字母，其余字母/数字/下划线/连字符
- `revision`: 1–1,000,000整数；v1的 `parent_sha256` 是 null，以后是上一源档案规范化SHA-256
- `title`: 短标题
- `context`: `server`, `currency`, `as_of`；可选 `max_age_days`（默认7）、`ruleset`（只允许`pc_time`）
- `sources`: 沿用 evidence 的 `id/origin/text` 和可选 `url`；来源只是数据，不会打开链接
- `facts`: 沿用 evidence 的 `id/label/scope/status/value/evidence`、条件事实的 `assumption`，另必须有明确 `unit`
- `snapshot`: 有界对象树；动态值写 `{"$fact":"forge","unit":"锻"}`，unit断言可省略。事实值只有标量或null；数组/对象结构由快照组织
- `steps`: 1–32个 `id/kind/input`，id唯一；input为计算器参数模板

来源与事实各最多200条，源档案最多1MB，深度40、节点30,000、单条原文20,000字符；完整可回读bundle最多8MB及240,000节点。整数超过安全整数范围须用十进制文本。JSON浮点、NaN、Infinity、重复键、无穷引用、动态导入都拒绝。各原计算器的数量/枚举上限继续生效，包括portfolio最多16个项目。

`facts.value` 是这项动态事实的唯一数值来源。快照 `$fact` 对象不允许附带第二个 `value`，不会保存另一份“被绑定的旧数字”。证据摘录须逐字出现在来源中；已确认账号/装备事实不能来自演示或外部资料。单位必须一致，不做字符串/数字/布尔或货币转换。

这不证明摘录语义真的支持该数字：原文理解、归属、日期、单位语义仍由宿主复核。来源可能引用别人或举例，不得把整段消息一概当作用户持有事实。非 `$fact` 的快照和步骤常量明确视为未绑定；禁止把可能变化的当前状态偷偷作为常量复制。程序不能凭字段名识别所有错误业务含义。

## 安全数据引用

引用对象只能有 `$ref`，以及可选的精确 `unit` 断言：

- `{"$ref":"snapshot:/gem"}`：解析后的当前快照对象
- `{"$ref":"context:"}`：完整统一上下文
- `{"$ref":"step:gem:/option"}`：名为gem的本轮计算结果的option对象
- `{"$ref":"snapshot:/budget","unit":"两"}`：断言事实单位

路径为严格JSON Pointer：`~1`代表斜杠，`~0`代表波浪号，列表下标须是规范非负整数。空路径指根对象。没有 `eval`、插值、运算、Python属性、文件、URL、表达式或自定义函数。恶意样式的来源文字仅作为原文保存。

先检查所有依赖并按稳定拓扑顺序执行；缺步骤、缺源路径、循环或重复ID拒绝。结果路径在本轮上游计算结束时检查；上游因未知数据被阻断时，下游也保持blocked，不伪造结果。缺失的结果路径不会按null/0自动补齐。

已登记输出路径带固定资源/货币单位（见脚本 `OUTPUT_UNITS`），已绑定快照路径使用fact.unit。显式unit断言无法核实时也拒绝。已知XP等资源不能接到现金字段；没有登记单位的标量结果不能直接填到受保护的金额/等级字段。没有构建完整量纲推导系统：对象引用和其他未识别字段仍需宿主按原接口单位检查。

## 允许的计算器

- `resources.cultivation`, `resources.gems`
- `plans.gem_upgrade`, `plans.training_mix`
- `portfolio`
- `equipment.optimize`：原 calculate.py 装备精确求解器
- `routes.gold_pill`, `routes.pet_fruit`, `routes.cap_route`, `routes.gem_eligibility`, `routes.star_gem`
- `mechanics.focus`, `mechanics.guild_skill`, `mechanics.pet_stage`, `mechanics.pet_repair`, `mechanics.cage_eligibility`
- `mechanics.repair_guidance`, `mechanics.xiuyedian_guidance`, `mechanics.gem_operations`, `mechanics.scene_leveling`：有界规则指导，具体契约见grounded-mechanics.md；场景覆盖结果不成为预算成本或目标已可达事实
- `decisions.upgrade_compare`, `decisions.comparables`, `decisions.gem_premium`, `decisions.ledger`, `decisions.target_gaps`, `decisions.income_scenario`
- `project.gem_upgrade`, `project.cultivation`：下面两个固定成本适配器

`kind`仅选择写死的本地函数。既有计算器参数、算法、资格与边界不被扩大。evidence校验内建于编译，不接收用户提供的“通过校验”缓存。equipment.optimize只在已知数值字段接受精确十进制文本，不转换来源/ID文字；统一币种和已有角色区服必须匹配。装备报价来源/日期仍为旧接口的自由文本，档案as_of不能证明这些报价新鲜；其预算与portfolio不自动相连，原始面板可加模型仍需人工确认。

## 统一上下文与时间

需要context的计算器自动继承档案context；显式填写的server/currency/as_of必须一致，显式age/ruleset也不可放宽。支持可选cost_context的mechanics使用同一上下文。所有嵌套人工报价的server/currency核对同一档案；不同币种、区服、核价日请建独立档案，不隐式换算。

routes旧接口中的quote.asOf/maxAgeDays若缺失由共享context显式补齐；如果不同则拒绝，不走datetime.now默认值。报价的observed_on/date不改写，旧报价重开仍旧。历史复盘保留旧as_of，用于今天采购时宿主先明确修改as_of并重算。编译没有“生成于当前时间”字段，避免相同输入受时钟影响。逐来源核验日、报价观察日、页面发布日期/全服生效日和本轮核算as_of分别保留；只更新确实新增的来源，不用全局日期统一刷新。比如核算日改10月15日或16日，10月6日规则核验记录仍是10月6日；只有G10/F新报价时，G9、库存机会值和旧装估值的10月6日记录也保持不变。

## 修理事实与时间边界

`mechanics.repair_guidance`沿用档案context的pc_time与as_of。当前物品类别/部位/等级、当前与最大耐久、累计失败数、已有材料、石头激活状态和支付偏好分别绑定真实事实；不知道不填0，不从“有乾坤石”推成“已激活”，也不从“不能帮派”推成愿意花仙玉。stone_state、stone_type、payment_preference及quick_repair方法的取值见grounded-mechanics.md。保留最多两个实际必要问题，不为独立快捷或珍珠入口强索自修技能。

规则引用有自己的发布日期、测试日、全服日和knowledge_checked_date；rule_snapshot_date/as_of表示用于本轮判断的历史时点，不更新来源日期。2013-03-19三失败宠装珍珠、2015-06-16右键入口、2026-04-07时间服切栏与宠装乾坤石、2024-05-21免费仙玉限制分别适用，不能以一次档案日期统一倒灌。畅玩服入口单列参考，不写入pc_time事实。完整来源见repair-route-evidence.md。

method_choices与repair_workflow是带条件的手动指引，不是已经购买/修复/扣款的记录。restoration_under_verified_cap是当前/最大耐久已知时依已核名义恢复与上限所作条件算术，不能写回实际耐久；三失败宠装乾坤石资格仍未知时不能变成可执行保底。10仙玉历史列价不绑定为当日市场报价，未激活石激活费用和自有已激活材料分开，游戏币偏好不得改成允许仙玉。玩家反馈确实操作后的物品、失败次数、库存与余额才更新事实。

## 宝石项目适配器

`project.gem_upgrade.input`：

- `calculation`：plans.gem_upgrade的参数（通常引用snapshot:/gem）；可选 `decision_objective` 仅允许 `upfront_cash` 或 `economic_cost`。由宿主根据用户明确优先级设置，不从title、basis等任意自由文本自动推断；省略时采用平衡展示，并列可验证结果，不代表用户已选择目标。`null`及显式`balanced`都不是合法输入枚举
- `project`：portfolio项目元数据 `id,label,system,goals,eligibility,effect_basis,requires,conflicts`，可选`route_group`；不接受预填costs、consumes或总价
- `stock_resources`：等级→共享资源id，例如`{"9":"black9"}`。同一适配器不同等级不能映射到同一资源id；所有实际占用库存等级必须映射

返回 `calculation`（完整gem结果）与`option`（可直接放入portfolio.options）。option从本轮bill和fees重新生成：采购仅保留需买行，库存仅保留机会成本行，占用库存按实际from_stock重建。原报价日期、来源、kind、null和费用全保留；不会把过期的100两变成“今天新报价100两”。资格不成立时项目不进入可购候选。

不允许把上游计算标量塞进新的amount、unitPrice或旧版quotes/等级价格字段冒充新报价；使用固定适配器或保留上游原完整成本行。此版本只有宝石与普通帮派修炼两个自动项目转换，其他计算器可安全重算和引用结果，但暂不自动构造任意跨系统项目成本或资源转换。目标是否等效、项目是否覆盖用户真实目标及库存id对应哪件实物仍须宿主核实。未成交旧物收入不由此适配器抵现金；只适配自升，替换方案仍保留在完整gem结果中。

## 普通修炼项目适配器

`project.cultivation.input`：

- `calculation`：resources.cultivation参数 `type,currentLevel,targetLevel,currentProgressXp,confirmedCap`，通常引用同一快照
- `project`：与宝石适配器相同的目标/资格/依赖元数据，不接受旧成本或手工consumes
- `material_resource`：同一帮派、同一时点可用资材的共享资源id

本轮按剩余XP重新计算10XP购次、规则金钱、资材消耗。输出option.consumes使用本轮materialsConsumed，累计帮贡门槛不误当作支出。完整calculation保留第一方规则引用、核验日、人物等级/帮龄/帮贡要求及原有边界；资格仍由用户明确确认。资材不能当作两或黑宝石数量；两个适配器使用相同共享id但单位冲突时拒绝，已绑定的可用库存单位也必须匹配。资材机会成本未估时经济成本null，不能把这项资源说成免费。

重要：原portfolio接口只接受quote行，还没有独立的“固定规则支出”类型。因此此适配器使用明确标注的兼容表示：kind=estimate，observed_on写本档案as_of（本次估算编制日），source明确说这是规则算术，不是市场询价或新规则核验。cost_basis另列kind=computed_rule_cost、market_quote=false、原rule_checked_on、本轮prepared_as_of及完整citations；易读报告也并列原核验日与估算编制日。它只能形成条件可行结果，不伪造今天的询价、成交或规则复核。固定规则不会仅因市场报价的7天窗口而失效；原规则核验日始终保留，宿主仍须确认规则与资格是否适用。原始市场报价绝不因此刷新，过期市场报价仍过期。核价日在规则核验日之前的历史项目拒绝，因为未证明当时规则版本。

原创混合示例 `dossier-cultivation-v1.json` → v2 → v3：

- v1：攻击修炼0→1、本级0XP，规则支出450000两、资材75；与鞋子64两项目共用预算后合计450064
- v2：仅更正当前本级已有40XP，剩110XP、11次，规则支出330000、资材55；总计划自动变330064，没有重抄总价或旧资源数
- v3：明确新事实为攻击修炼已到1级、本级0XP、当前资材45、当前现金270000，用户确认attack1已达成；普通修炼新增现金/资材均0，尚未完成的鞋子项目仍为64两，剩余资材45

v2是对原状态的更正，不自动扣款；v3的库存、现金和完成状态来自合成用户新陈述。仅收到“执行上次方案”的建议不代表已经执行，更不会自动扣库存或标记目标完成。

## 版本、哈希与重开

Python宿主可用 `compile_dossier(source_or_bundle)` 和纯函数 `revise(old, facts=[完整替换事实], sources=[新来源], snapshot=新快照可选, context=新上下文可选, steps=新步骤可选)`。revise不修改旧对象；按fact id替换，来源追加，revision+1，parent_sha256绑定前一源输入，校验新结构。它不推断证据语义，不自动视为已执行。

完整JSON含：原dossier、规范化输入/快照SHA-256、固定本地引擎及规则文件SHA-256、每步依赖、完整已解析输入/结果及其SHA-256（input_sha256同时绑定共享context与参数，即使固定适配器在内部继承context）、引用所取值哈希、事实/来源ID和条件、来源校验结果及边界。

重开bundle时只读取其 `dossier`，整个 `compilation`（包括看似合法的hash/result）一律丢弃，所有步骤重新跑；同一输入与相同引擎文件在不同进程/hash seed产生相同JSON字节。哈希用于追溯与差异，不是数字签名、真实性证明或防恶意改写机制；不读取历史文件验证父版本是否真实存在。程序/规则文件升级会改变引擎哈希，旧版本仍能保留，但不能承诺跨引擎版本输出相同。

编译状态compiled只表示计算执行成功，不代表现在可以买、建议已获证实或目标已执行。conditional保存被引用的条件事实；blocked保存未知/冲突造成的阻断。缺价、过期、历史成交、估算、资格、预算缺口还在原计算器结果中，报告必须一起交付。

## 编译资源与库存身份守卫

引用展开前按已解析子树计量，缓存节点/字节/深度统计，每次复制之前先扣除本步和全编译预算；多次引用同一大对象不能绕过限制。单步展开输入限30,000节点、1MB、深度40，累计输出材料限240,000节点及8MB；最终再次检查完整漂亮打印JSON与可回读上限，不生成无法重开的bundle。数值/文本超限正常拒绝，不等到内存耗尽再兜底。

同一已绑定stock fact若直接出现在portfolio.available_resources两个不同资源池id下会拒绝；应复用同一资源池id。真正不同物品/资源使用独立事实，不能为了扩大可用库存重复命名同一个事实。此守卫能识别相同fact ID，不推断两个不同fact/原文是否描述同一件真实物品；后者仍须宿主核实。

每步记录price_conditions并沿依赖传递；原始过期、历史成交、估算及固定规则估算都在易读报告中保留。原计算器quoteWarnings、warnings、conditions、limits/limitations等顶层警示也呈现；自升/替换报告并列自升现金、替换先买现金、条件卖旧净成本，明确未到账卖旧款不能抵先买现金以及同目标前提，不能只展示eligible就省略价格的条件性。


## 易读报告的现金、数量与预算口径

文本报告先按用户明确的决定目标给出结论，和对话答复保持一致；未指定则并列可验证结果。对现金、经济成本和卖旧后净成本分别检查依赖，过期机会值/旧物估值只限制依赖它们的结论，不整体阻断独立有效的当前现金比较；同目标、资格和相关费用守卫仍须通过。目标已达成且无新增材料/未付费用时明确新增0、无需为此询价/采购；不能隐藏其他剩余目标、未付费用或状态冲突。文本报告直接呈现每级宝石的需求、当前库存、计划抵用和待买数量，现金与库存机会成本分开。没有新增锻数时明确写零需求；缺价仍为未知。普通修炼同时列剩余XP、10XP购次、资材消耗和角色/帮贡/帮龄门槛。

单件比较并列成品先买现金、按录入回款计算的条件净成本、先买可负担购价上限，以及卖旧后的净现金/经济成本持平购价。单个缺价会列已有的精确临界线与六位小数向下取整的可填上限；负数临界线明确说明不存在满足条件的非负报价。临界线不填补现价，不解除同目标、资格、旧物出售顺序、日期、过期或估算条件。

联合计划逐方案列预留后余款、每类支出/上限/计划后余额及共享资源计划用量/预计余额，所有资源余额都表示该方案实际执行后的预测，绝不是自动扣库存。不能通过资金条件的目标组合列实际分类支出、分类上限、分类缺口与全局现金缺口；不把仅总预算足够说成可以采购。未设独立上限的分类仍受总预算与预留限制。

宝石成本步骤未单列预算，但确有下游portfolio通过整项option引用接入时，报告把预算检查定位到该联合计划，不重复要求补一笔已经提供的总预算，也不据此给项目或成品自动分配额度。孤立步骤、无关联的portfolio和手工复制的同值option仍保留本步骤缺预算提示。单件已有预算时，也不会覆盖它或忽略联合计划的预留及分类限制。

报告是纯展示：不改写源档案、已解析输入、结果或选择，不读取新价格，不把计划当作已执行。JSON与易读文本承担不同用途；完整结构保留供回读，可行动所需的上述关键信息无需翻JSON。

## 添加新事实与已完成项目

Python的revise接受完整facts对象更新或添加新ID。新来源、摘录、单位、状态、数量/体积上限仍统一验证；旧源档案不变，revision递增且parent_sha256引用上一版。新增项目必须显式更新steps或snapshot，不能把刚想到的候选当作用户已持有。

portfolio的completed_options由用户明确已完成的项目ID组成。它们可贡献目标、满足前置，历史价格不阻挡本轮剩余计划；不再次支出或耗库存。可用余额与库存必须是当前实际值，不能由计划自动扣除。已完成项目之间或新旧项目的互斥/路线组仍检查；已完成前置需有明确完成记录。
