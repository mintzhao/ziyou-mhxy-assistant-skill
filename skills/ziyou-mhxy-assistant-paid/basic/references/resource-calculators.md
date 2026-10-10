# 离线资源计算：修炼与普通宝石

核对日期：2026-10-06。范围：梦幻西游电脑版时间服。这里是预算、材料和原始装备属性计算，不是实战公式或整体账号收益推荐。不能套用于手游、畅玩服或其他版本。

## 证据与更新范围

- [官方人物修炼](https://xyq.163.com/introduce/zd008.html)：普通修炼经验、金钱、资材和门槛
- [官方宝石介绍](https://xyq.163.com/introduce/dj008.html)：原始装备属性、部位、逐级镶嵌、普通宝石的基础合成
- [2024-05-21 系统调整](https://xyq.163.com/news/20240520/4999_1156134.html)：12至20级普通宝石的额外合成材料；该规则仍显示于核对时的[官方工具箱](https://xyq.163.com/tools/index.html)

官网旧说明可能局部陈旧：宝石页面日期标签为2013-01-02，介绍中的宝石总数与实际列表也不一致。规则采用具体表格；涉及合成时以明确的2024调整覆盖旧合成说明。不能据此宣称是2026完整规则库。镶嵌说明开头明确要求宝石等级等于当前锻炼等级加一，后文简略条款只写“大于”；本工具采用逐级方式，且提示实际装备资格需在游戏内确认。

实现只根据公开事实独立编写，没有复制官方计算器或第三方工具的源码、图片、表格版式、付费资产。运行时不联网、不抓取页面、不调用外部API。

## 普通人物修炼

设当前等级为a、目标等级为b，升级到r级的经验为：

`E(r) = 10 × (r² + 3r + 11)`

先累计r=a+1至b，再扣除本级已有经验p。需要购买的次数为 `ceil(剩余经验/10)`。每次固定增加10点经验；攻击、法术、猎术每次30,000两，防御、抗法每次20,000两；每次消耗5点帮派资材。

区分消耗和门槛：

- 金钱、帮派资材会消耗
- 普通模式的累计帮贡只作门槛，不作为扣款
- 官网原文门槛为累计帮贡严格大于150b，入帮时间严格大于14天
- 角色等级至少5b+20；帮派还须开放对应修炼
- 必须输入游戏内确认的当前修炼上限；目标超过上限会拒绝计算

支持范围是普通四修0至25级、猎术0至20级。它不推断账号已解锁的上限，不包含降修、飞升、快速兑换、租赁、优惠或提升战斗效果。没有升级时不扣现有进度。末次购买超出目标所需的经验作为算术余量显示；达到上限时游戏是否保留该余量需游戏内确认。

校验例：攻击0→9需要5,190经验、519次购买、15,570,000两及2,595资材；同区间防御修炼为10,380,000两。0→1已有149经验时，尚缺1经验，仍按一次购买计算。

## 普通宝石

一次从锻炼a提升至b，需要分别准备a+1、a+2……b级宝石各一颗。各等级报价直接相加。未填写的报价保持未知，完整报价合计返回null，并列出缺失等级；已经填写的零价是真实的零。

材料下限与报价分开。F(1)=1，每颗g级普通宝石的无失败一级材料下限为：

`F(g) = 2 × F(g−1) + Σ F(额外材料等级)`

2024规则要求的额外材料：

| 目标等级 | 额外同类型宝石 |
| --- | --- |
| 12 | 3、5、6级各一颗 |
| 13 | 9级一颗 |
| 14 | 9、10级各一颗 |
| 15 | 9、12级各一颗 |
| 16 | 11、12、13级各一颗 |
| 17 | 15级一颗 |
| 18 | 13、14、16级各一颗 |
| 19 | 15、16、17级各一颗 |
| 20 | 17级一颗、18级两颗 |

本次锻炼材料下限是ΣF(g)，g从a+1至b。“最高级单颗材料量”单列，不能代替本次全部锻炼所需量。例：单颗12级为2,100，锻炼0→12为4,147；单颗20级为2,392,444。这些是原始材料下限，不是实际预计花费，不含失败损失、体力、手续费、库存抵扣，也不提供失败概率。直接购买已经合成的宝石应使用报价合计。

八种可选宝石的每次新增锻炼属性：光芒石气血40、太阳石伤害属性8、月亮石防御12、黑宝石速度8、红玛瑙命中25、舍利子灵力6、神秘石躲避20、翡翠石法术防御12。返回允许部位供核对。新增的每一锻都按当前选择的同一种宝石计算。

这些只是宝石的原始装备属性。没有应用强身、种族、坐骑、经脉、套装、临时符、取整或战斗规则。尤其不能把红玛瑙结果当成伤害，把光芒石结果当成角色最终气血。已有装备面板若已含宝石，不应再次叠加。

函数不判定装备实际可用性。使用者须核对部位、已有宝石类型、最多两种类型的限制、装备等级/10的普通锻炼上限与无级别例外。这里不处理吸收宝石、星辉石、精魄灵石或其他材料。

## API

Python：`scripts/resources.py` 中的 `cultivation(dict)`、`gems(dict)`。浏览器：`window.MHXYResources.cultivation(input)`、`.gems(input)`。不存在第三方依赖；浏览器运行本身不需要Node或Python。

数值输入接受非负整数、十进制整数字符串；报价单位是游戏币“两”，不接受小数、负数、null或布尔值。字符串最多30位。两端的数值类型必须是JS安全整数范围内的整数，大数应传字符串。计算使用Python整数和JS BigInt；所有数值结果使用字符串，缺失报价使用null。

修炼的五个字段全部必填，包括本级已有经验（没有时显式填0）。宝石的gemType、currentForge、targetForge必填，quotes可省略以表示全部报价未知。未知顶层字段会报错，避免拼写错误被忽略。

修炼输入：

```json
{"type":"attack","currentLevel":"0","targetLevel":"9","currentProgressXp":"0","confirmedCap":"9"}
```

type可选attack、spell、defense、anti_spell、hunting。返回requiredXp、purchases、costLiang、materialsConsumed、contributionConsumed、requiredCharacterLevel、requiredContributionExclusive、requiredGuildMembershipDaysExclusive、逐级steps、explanations和citations。带Exclusive的门槛用严格大于比较。

宝石输入：

```json
{"gemType":"moon","currentForge":"0","targetForge":"3","quotes":{"1":"100","2":"200","3":"400"}}
```

返回quoteTotalLiang、knownQuoteSubtotalLiang、missingQuoteGrades、baseUnitsLowerBound、targetStoneBaseUnitsLowerBound、rawStatDelta、allowedSlots、逐级steps、explanations和citations。rawStatDelta含key、label、value、unit，不直接写回角色配装面板。

浏览器另外提供gemTypes与cultivationTypes元数据。来源URL固定为官方页面，不接收用户传入的链接。

## 命令行运行

将上面的修炼示例保存为 `cultivation-input.json`，然后在本包根目录运行：

```sh
python -X utf8 scripts/resources.py cultivation-input.json --kind cultivation --output cultivation-result.json
```

将宝石示例保存为 `gems-input.json`，运行：

```sh
python -X utf8 scripts/resources.py gems-input.json --kind gems --output gems-result.json
```

Windows已有Python时可将 `python3` 换成 `py -3`。不带 `--output` 会直接向终端输出JSON；指定输出时只允许创建新文件，已有结果和输入文件绝不覆盖。

命令行仅读取UTF-8普通文件（支持BOM），上限1 MiB；拒绝符号链接、重复JSON字段、非有限数字、小数或指数写法、布尔值及超长数值。报错时显示原因，不会联网补全数据。输出引用的官方页面只是来源链接，计算时不会访问它们。
