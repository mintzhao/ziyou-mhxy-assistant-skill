# 跨 agent 接入

主入口采用 [Agent Skills 标准](https://agentskills.io/specification)。只有 skills/ziyou-mhxy-assistant-paid/SKILL.md 是可发现技能；basic/GUIDE.md 是内嵌免费能力参考，不作为第二个 Skill 注册。

## 能力分层

| 当前宿主能力 | 可用范围 | 缺失能力的处理 |
|---|---|---|
| 能加载 Skill/读参考 | 有依据的规则与流程说明 | 不声称已执行计算 |
| 能执行 Python、访问用户指定文件 | 免费计算、资料保存和修改 | 不能伪造保存或计算结果 |
| 能执行 Python、访问可信 HTTPS 服务 | 免费远程准备、摘要和报价 | 未接通时继续已有免费功能 |
| 另有可调用的官方支付工具及用户授权 | 获取账单并完成官方付款/交付 | 缺工具时停在 prepare，不出新账单 |
| 有可信不记录秘密的临时通道 | 原单证明恢复 | 缺通道时使用官方恢复流程或人工核对 |

不支持本地脚本执行的纯聊天宿主，目前只能读取指引；本客户端没有 MCP 服务。支持 Skill 格式不等于通过本服务的付款验收。

## 各宿主安装

先解压或复制完整 ziyou-mhxy-assistant-paid 目录，再按宿主当前文档加载；本工具不自动安装或覆盖宿主技能。

| 宿主 | 安装方式 | 独立客户端实测状态 |
|---|---|---|
| WorkBuddy | 使用其 Skill 导入功能导入 ZIP/完整目录，确认会话已加载 | 既有运行版本有项目验收记录；独立开源包尚未在此宿主验收 |
| Codex | 复制完整目录到本机已配置的 Skill 根目录；本环境使用 ~/.codex/skills | 2026-10-10 实际安装 0.9.0-client.1，原生发现、五轮自然语言自动调用、免费计算/资料及三个 HTTPS 免费 prepare 通过；未付款 |
| Claude Code | 按官方文档放入项目 .claude/skills 或用户 ~/.claude/skills | 指引已整理，未在原生宿主验收 |
| 其他支持 Agent Skills 的宿主 | 按其当前技能目录/导入方式安装，核对实际工具能力 | 待各宿主验证 |

Claude Code 来源：[官方 Skills 文档](https://code.claude.com/docs/en/skills)。Codex 路径来自本地 Skill Creator 指引；使用不同版本时以当前宿主配置为准。标准支持范围参考 [Agent Skills](https://agentskills.io/home)，本表不构成所有平台已可付款的承诺。

0.9.0-client.3 更新版本、发布说明和上述实测记录，34 个执行文件与已测试版本逐字节一致。Codex 高级准备测试使用合成附件，缺预算时保持未知且返回澄清，三个服务均展示完整价格、事实和 UTC+08 有效期，charge_created=false；没有测试真实行情、截图识别或实际付款。

## 运行约定

主入口、资产编辑、远程桥接均以 Skill 根目录为工作目录；basic/scripts 下免费命令以 basic 为工作目录。先确定实际加载的 Skill 路径，不依赖调用者当前目录、不猜测用户文件路径。脚本可用绝对路径调用；用户输入通过 stdin 或明确的数据文件传入。

客户端只需 Python 3.10+ 标准库，Windows 可用 python 或 py 选择解释器。宿主调用时使用 -X utf8，并以 UTF-8 编码 stdin、解码 stdout/stderr；Windows 默认代码页不能代替 JSON 的 UTF-8 约定。PowerShell 可按下列方式完成免费计算：

```powershell
Set-Location '<实际 Skill 路径>'
python -X utf8 -B scripts/remote_client.py --help
python -X utf8 -B basic/scripts/resources.py basic/examples/cultivation-input.json --kind cultivation
```

结构化输出按 JSON 处理，非零退出码是失败；exit 0 也不代替业务字段核对。玩家仍使用普通中文，宿主提取已有事实并运行工具，不把 JSON 模板当成玩家必填表。

## 支付依赖

需要当前宿主真实可调用支付宝官方 alipay-payment-skill。官方另提供 alipay-authenticate-wallet 处理钱包授权；这些工具独立安装，不包含在本仓库。官方来源：[alipay/payment-skills](https://github.com/alipay/payment-skills)。其安装器当前要求 Node.js/npm，官方命令为 npx -y @alipay/agent-payment@latest install；具体运行和故障恢复遵循已安装官方 Skill，不在本客户端复制实现。

检查的是当前会话工具是否可调用，不能以磁盘上有文件代替已加载。用户要求安装后才执行安装；安装目标是当前宿主环境，安装器未覆盖该宿主时按宿主文档导入官方完整目录。安装许可不等于钱包授权或付款许可。不新增“先 check-wallet”的项目要求。

用户未选择付费服务时不用安装支付工具。准备完成但支付工具缺失时保留资料和摘要，暂停 confirm/asset-confirm；摘要过期后重新免费准备并获得确认。已生成账单则恢复原单，不能因换宿主或补装工具重新购买。

## 宿主验收清单

逐个宿主记录：入口和参考可读、免费示例实际执行、资料保存/重开、缺项不出账单、完整摘要及有效期展示、支付工具加载状态、用户明确确认、真实官方买方付款/验付/交付、原单恢复和证明不泄漏。真实交易需要另行明确授权。离线测试和免费 prepare 不代表任何宿主的实付验收。
