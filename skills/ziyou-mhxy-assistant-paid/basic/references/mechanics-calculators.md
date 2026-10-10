# 专注、帮派技能报价、普通进阶接口

入口 `python -X utf8 scripts/mechanics.py input.json --kind focus|guild_skill|pet_stage|pet_repair|cage_eligibility|repair_guidance|xiuyedian_guidance|gem_operations|scene_leveling [--output new.json]`。仅Python标准库；UTF-8 JSON输入严格拒绝重复字段、非有限数和覆盖旧输出。共同必填 ruleset=pc_time；其他服制拒绝。第一方规则与未核验项见 current-game-decisions.md。

## focus

必填 casts、period、cost_basis。casts每行 label、count、effective_mana_cost、eligibility=confirmed；只填已确认适用专注的战斗施法，耗蓝是所有已知加成/减免后的实际原耗蓝。period说明本次工作量，如“我记录的一天”，不是工具自动推定。

输出原耗蓝C、期望节省0.15C、期望支出0.85C。可选 cost_context、paid_mana_quote、extra_purchase_quote，报价字段与decisions.py相同。涉及金额时须有context的区服/币种/日期。paid_mana_quote是一点魔法的实际可避免边际现金成本，extra_purchase_quote是候选相对当前的额外购入价；没有这些输入就不给省钱/回本数。

免费恢复、溢出补蓝、消费频率没变，都可能使边际成本为0。期望回本不是某天保证回本；装备属性、套装变化与残值另核。历史/估算/过期报价只作有标签的条件算术。示例 mechanics-focus.json 不含现金假设。

## guild_skill

必填 skill、current_level、target_level、context、source、guild_fee_index、steps。context同服同币种，两为固定游戏币；source描述当次游戏内或官方工具报价；指数只记录，不猜换算公式。

steps必须按连续目标等级逐项填 target_level、experience、money_liang、contribution_spent、contribution_gate、materials。不知道的列填null，不准补0。contribution_gate录入学习前“至少需要”的当前可用帮贡门槛；严格大于的门槛须先转换为对应最小整数并在来源说明。每步消耗与学习门槛分开。

输出各资源完整总额、已知小计、缺列，以及不用再赚帮贡时的最少起始存量。计算为每一步“此前实际已花帮贡+当步门槛”的最大值，同时保证实际扣款足额。可选starting_contribution判断是否够。没有完整门槛/扣款不输出假精确起始值。

示例 mechanics-guild.json 中每级消耗k、门槛5k仅是合成算术夹具，不是工具宣称已核的2026规则。不要把这一结构扩大到强壮/神速等不同技能。

## pet_stage

仅普通进阶0至50灵性的确定性易经丹阶段。必填 current_spirit、target_spirit、owned_pills、absorption_in_progress、remaining_absorption_hours、eligibility。current_spirit限0/10/20/30/40/50边界，目标≤50；等级79不是当前灵性。

每次吸收+10灵性，正常逐颗96小时；每灵性2潜能。正在吸收的那颗已消费，不再采购；owned_pills只抵未来需要的新丹。running必须真实布尔值，进行中还需1至96小时剩余，未进行中剩余为0。可选context与pill_quote用于带来源预算，context货币必须是两。

输出还需几次吸收、新使用/新购买几颗、自然吸收小时与新增潜能。特殊宠物资格、内丹补齐、触发战斗、加速费用、仙露和特性均不包括。目标到50以后不用这段规则推算；参考页会给需要核实的仙露边界与保守选择方法，但不报未知随机成功率。

## pet_repair

必填ruleset、equipment_kind=pet、equipment_level、repair_failures；可选pearl_level、as_of、current_durability、maximum_durability。兼容旧输入，共用repair_guidance的宠装珍珠规则：2013-03-19全服明文允许三失败，珍珠等级+5≥宠装等级、名义200受耐久上限限制。current/maximum齐全时的恢复量只是已核规则条件算术，不是已执行结果；缺状态不填精确值。按as_of区分当时已全服规则，保留右键与切栏的各自日期。无法用于人物装备，不保证市场供货或已经游戏内操作；来源见pet-maintenance-and-leveling.md及repair-route-evidence.md。

## cage_eligibility

必填ruleset、pet_level、target_pet_level、character_level、character_stage（not_flyup/flyup_not_dujie/dujie）、has_courtyard与has_cage两个布尔值。输出进入30级门槛、人物等级+10与阶段共同上限、庭院/笼子前置和已核每日时间限制。NPC页面200万购笼是固定来源项目，已有不重复购买；缺总XP和每次经验速度时，总练级现金/小时保持未知，不把购笼价当0→119总价。

## 2.2.0-rc3已核分项指导

新增repair_guidance、xiuyedian_guidance、gem_operations，接口见grounded-mechanics.md。可作为dossier步骤持续更新用户事实、目标与来源；修理预览日期和修业点比较时间必须与档案日期一致。历史rc3的pet_repair在三失败时曾将pearl_blocked_by_three_failures改为null（当时未明确验证），不是true；本次补入2013全服明文后当前日期输出采用官方允许，明确的天眼珠禁用仍为true。旧冻结版本和旧测试记录不改写。

## 2.2.0-rc7场景区间与普通修理步骤

scene_leveling必填ruleset=pc_time、current_pet_level、target_pet_level，可选character_level、scene、escort_cost与exclude_yuehua。查询官方79行场景表，区分玩家选档与宝宝满经验/获经验范围；只给固定玩家0–175行的覆盖例子，保留变动玩家档位和混级组队未知。它不输出可达保证、最优路线、总小时或总现金。repair_guidance补入人物普通修理地点、部位技能和自行技能判断，仍无当前精确菜单证据。完整契约见grounded-mechanics.md；两者由宿主/CLI使用，首页只有说明。
