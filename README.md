# 自游·梦幻助手：独立 Skill 客户端

本仓库是自游·梦幻助手的独立 Skill 客户端，支持能读取 Agent Skills 并执行 Python 的聊天助手。
客户端和内嵌免费工具采用 [MIT 许可证](LICENSE)。高级分析调用作者运营的收费服务；付费算法、服务端实现、验付、订单账本和支付执行工具不包含在本仓库中。

客户端版本为 `0.9.0-client.2`，以付费运行包 `0.8.7` 为基础。34 个既有执行文件保持原字节；本版在已测试的 `0.9.0-client.1` 上更新发布说明、版本和实测记录，执行代码不变。免费功能继续免费，高级服务仍先确认摘要和费用，再通过支付宝官方工具付款。

## 安装和使用

安装完整的 [skills/ziyou-mhxy-assistant-paid](skills/ziyou-mhxy-assistant-paid/SKILL.md) 目录到当前宿主的 Skill 目录；不要只复制 SKILL.md，也不要单独注册 basic 子目录。平台说明见 [跨 agent 接入](docs/COMPATIBILITY.md)。

可从 [GitHub Releases](https://github.com/mintzhao/ziyou-mhxy-assistant-skill-client/releases/latest) 下载 Skill ZIP，或克隆本仓库后复制完整技能目录：

```powershell
git clone https://github.com/mintzhao/ziyou-mhxy-assistant-skill-client.git
```

Codex 用户技能目录在已验证的 Windows 环境中为 `$HOME/.codex/skills`；Claude Code 可使用 `$HOME/.claude/skills` 或项目 `.claude/skills`；WorkBuddy 使用 Skill 导入功能。安装前检查同名技能，避免覆盖旧版资料；以当前宿主配置为准。

普通玩家直接说问题，例如“攻击修炼从 10 到 15 要准备多少材料？”或“把已有装备跨角色分配，先给我看分析范围和费用”。无需自己填写 JSON。截图识别、文件访问、脚本执行和联网均取决于当前宿主。

本地工具只使用 Python 标准库，要求 Python 3.10 及以上。Windows 的 CPython 3.11.9 和 3.12.15 分别通过 11 项离线客户端测试。2026-10-10 已在 Codex 实际安装 `0.9.0-client.1`，五个新会话无需指定技能名，即可自动调用免费计算、资料处理及三个服务的免费准备。其他宿主和真实付款没有由这些测试一并验证。付款工具另需 Node.js/npm 和当前宿主可调用的支付宝官方 Skill，不随本仓库打包。

## 离线验证与打包

在本目录运行以下命令；不连接正式服务、不出账单、不付款：

```powershell
python -X utf8 -B tools/verify_client.py
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B tools/build_client.py --output dist
```

构建目录必须尚不存在。构建生成带标准名称顶层文件夹的 Skill ZIP 和 SHA256SUMS；ZIP 只含安装所需 Skill 文件，不带维护测试和仓库工具。完整客户端目录本身可移到任意可信新目录后验证和构建，不需要私有项目、支付 SDK 或服务端依赖。

## 服务、费用和隐私

三个高级服务分别为跨录入情景共同方案、已有资产自动分配、角色套装/特技标记组合分析，当前配置为每次 1.00 CNY。模型或宿主费用另计。确认价格以可信固定商品配置和本次完整摘要一致为前提；资料编辑、缺项澄清和 prepare 不创建订单。

远程准备会把本次分析所需资料发给配置的服务端。不得上传游戏密码、验证码、钱包凭据或无关个人资料。资料核实日期不会自动更新。详见 [客户端边界](docs/BOUNDARY.md) 和 [远程契约](skills/ziyou-mhxy-assistant-paid/references/remote-bridge.md)。

开源许可证覆盖本目录内作者原创的客户端代码与文档，不授予私有服务端源码、游戏/平台商标或第三方内容的权利，也不承诺免费使用收费服务。支付宝工具使用其自己的许可及条款，通过官方来源独立安装。

源码和安装包在本仓库发布；技能市场上架另行处理。私有项目和正式服务继续单独维护，公开源码不包含其实现或历史。
