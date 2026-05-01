# 05 Cursor 新会话引导词

将以下内容粘贴到新打开的 `/Users/epix/Dev/UniNode` 项目会话中：

```text
你现在在 /Users/epix/Dev/UniNode 项目中工作。请先读取并遵守项目级 Cursor rules：

- .cursor/rules/00-uninode-product-context.mdc
- .cursor/rules/10-safety-automation-boundaries.mdc
- .cursor/rules/20-frontend-console.mdc
- .cursor/rules/30-api-backend.mdc
- .cursor/rules/40-docs-configs.mdc

项目目标：开发 UniNode Ops Console，一个本地优先的可视化网络运维控制台，覆盖全球访问链路、旁路由/FreeSky、VPS VPN 订阅、Tailscale、NAS/Obsidian、OpenClaw/Hermes 多 Agent 协作，以及 Cursor 自动化检查、诊断、故障处理、证据归档、审批与回滚。

请把以下文档作为当前事实源：

- Docs/03_PRD_本地部署控制台产品.md：产品 PRD
- Docs/04_开发实施任务细分解构.md：开发实施任务拆解
- Docs/00_现状审计报告.md：来源项目 AS-IS 与风险
- Docs/01_需求重构_SRD.md：需求重构
- Docs/02_产品定位与功能清单.md：产品定位与 MVP/V1/V2 范围

重要约束：

1. 设备临时断电、离线、未接通是正常状态，不要把它直接判定为架构失败；应标记为 needs_human_power_on 或 expected_offline。
2. 默认只做只读检查和 dry-run，不要自动修改路由器、VPS、OpenWrt、Armbian、Tailscale、防火墙、DNS、订阅或 NAS 服务。
3. 任何生产配置动作必须先给出目标设备、影响范围、预检、命令、回滚、验证证据，并等待明确批准。
4. 不得输出或提交 secret；代理 UUID、private_key、password、token、auth key、订阅 URL、SSH 密码、证书材料必须脱敏。
5. 不要把模板证据、空样本、invalid JSON、全 NA bench、empty fingerprint 或 mobile insufficient_data 当成通过证据。

请从 Docs/04_开发实施任务细分解构.md 的 Task 0 开始执行。先检查当前目录结构，然后提出最小实现计划；如果需要创建代码骨架，优先采用：

- apps/web：React + TypeScript + Vite
- apps/api：Python FastAPI + Pydantic + SQLite
- configs：YAML 配置
- data：本地运行态和证据库，默认不入 git

完成每个任务时都要给出：改了哪些文件、如何运行、如何验证、还有哪些风险。
```
