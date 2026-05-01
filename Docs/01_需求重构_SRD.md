# 01 需求重构 SRD

产品方向：本地部署的多设备网络运营控制台。  
目标：把当前家庭/办公网络、VPS、Tailscale、Clash、NAS、Agent 协同的“脚本 + 文档 + 人工经验”重构为可执行、可验证、可回滚、可审计的运营系统。  
依据：`00_现状审计报告.md` 与 `/Users/epix/Dev/TraeDev/contabo/network-audit-2026Q2/多设备统一网络管理项目配置情况及功能目标.md`。

## 1. 问题与风险先行

### 用户真实痛点

- 用户不是想“拥有很多网络脚本”，而是想在办公室、5G、外网、家中不同网络环境下稳定工作，不再每次靠记忆排查。
- 用户不是想“持续优化参数”，而是想先稳定可用，再在独立窗口做可回滚优化。证据：`P2_EXECUTION_LOG_2026-04-20.md` 记录“先稳定可用，不再持续折腾网络参数”。
- 用户不是想“看一堆历史报告”，而是想知道此刻哪个事实源可信、哪个变更已上线、哪个结论只是仓库层准备。证据：`CURRENT_SOURCE_OF_TRUTH.md`、`P0_COMPLETION_REPORT_2026-04-20.md`、`P1_EXECUTION_LOG_2026-04-20.md`。
- 用户不是想“每次人工问 Agent”，而是希望 OpenClaw/Hermes 等多 Agent 在同一网络事实与证据目录下协作，避免路径漂移和重复试错。证据：`多设备统一网络管理项目配置情况及功能目标.md`。

### 当前业务风险

- 运营不可封板：移动端与订阅链仍缺真实证据，不能宣称线上运营完成。证据：`mobile-compare/manual_20260421_120408/compare_result.json`、`subscription-hits/hits.csv.template`。
- 知识不可交接：事实源已开始收敛，但路径、脚本、现场固化位置仍并存。证据：`CURRENT_SOURCE_OF_TRUTH.md`、`systemd/mihomo-exitnode-rules.service`、`openwrt/etc-init.d-mihomo-exitnode`。
- 变更不可规模化：Batch1 可控，但 Batch2/全量扩围前缺少自动门禁、证据包和报告产物。证据：`BATCH1_MINIPC_CANARY_CHANGE_ORDER_2026-04-22.md`、`BATCH1_24H_OBSERVATION_CHECKLIST_2026-04-23.md`。
- 安全不可忽视：正式配置目录中存在可复用认证材料形态，需要产品层 secret redaction 与发布前扫描。证据：`configs/sing-box-config.deploy.json`、`configs/clash-subscription.runtime-safe.yaml`、`sync_to_github.sh`。

## 2. 需求目标

### 一句话目标

让用户用一个本地控制台管理“多设备网络事实、阶段变更、验证门禁、证据归档、回滚和运营报告”，把网络工程从手工排障变成可重复的运维流程。

### 成功状态

- 任一网络变更都必须有阶段、目标设备、前置检查、执行动作、通过标准、失败回滚、证据路径。
- 任一“已完成”结论都必须能回链到 bench、mobile compare、subscription hit、fingerprint 或人工签收记录。
- 任一 Agent 都只能从同一 facts/config/runs 目录读取当前事实，不能自由引用旧路径。
- 任一敏感字段在报告、同步、Agent 上下文中默认脱敏。

## 3. In Scope

- 资产与事实源管理：终端、路由、边缘节点、VPS、腾讯云、Tailscale IP、端口、服务名、角色。
- 阶段执行编排：P0/P1/P2、Batch1/Batch2、移动实测、订阅发布、Exit Node 规则、ASUS 金丝雀。
- 证据归档：bench JSON、mobile compare JSON、subscription hits、fingerprints、人工 checkpoint、截图索引。
- 门禁判定：NA 检查、HTTP code、样本数、命中率、drift、P0/P1/P2 stop condition。
- 回滚管理：订阅哈希回滚、ASUS 网关回滚、Exit Node 规则回滚、VPS 配置回滚、客户端回滚。
- 报告生成：AS-IS、阶段报告、变更单、观察清单、每日/每次维护巡检报告。
- 安全与审计：secret 扫描、脱敏展示、敏感文件排除、操作审计日志。
- 多 Agent 协作边界：为 OpenClaw/Hermes/其他 Agent 提供只读 facts、任务状态、证据包和决策记录。

## 4. Out of Scope

- 不在 MVP 中重写 Clash、sing-box、Tailscale、OpenWrt、ASUS 固件能力。
- 不在 MVP 中做远程 SaaS 控制面；默认本地部署、局域网访问、文件系统持久化。
- 不在 MVP 中自动登录 ASUS Web UI 或手机端 App 执行点击操作，先用执行单 + 人工签收。
- 不在 MVP 中建设完整 NAS/Obsidian 同步产品，只纳入资产、健康检查、证据与 runbook。
- 不在 MVP 中实现 OpenClaw/Hermes 的任务调度系统，只提供网络与证据基础设施。
- 不在 MVP 中把性能优化自动应用到生产设备；所有生产变更默认需要人工确认门禁。

## 5. 功能需求（FR）

### FR-01 资产事实源

系统必须维护 `assets.yaml`，覆盖：
- 终端：Mac、Windows、Linux、iPhone、Android、iPad。
- 路由：华为 Q2 Pro、ASUS RT-AC86U / FreeSky。
- 边缘节点：miniPC backup-gateway、EpixNAS / RPi。
- 云：Contabo VPS、腾讯云。
- 服务：sing-box、mihomo、clash-meta、Tailscale、NAS/Obsidian、OpenClaw/Hermes。

验收标准：
- 能从 `network_facts.env` 导入已知 IP/端口。
- Tailscale IP 为空时必须标红为 `missing_required_for_ops`。
- README 引用不存在文件时必须报 `dangling_reference`。

证据来源：
- `network_facts.env`
- `README.md`
- `多设备统一网络管理项目配置情况及功能目标.md`

### FR-02 阶段与批次建模

系统必须维护 `phases.yaml`，至少支持：
- `P0 availability`
- `P1 stability`
- `P2 performance`
- `Batch1 miniPC canary`
- `Batch2 expansion`
- `Mobile 5G measurement`
- `Subscription release`

每个阶段必须包含：
- scope
- prechecks
- actions
- gates
- rollback
- evidence_required
- owner
- decision_required

验收标准：
- 没有 evidence_required 的阶段不能进入 `ready_to_execute`。
- gate 失败时状态进入 `blocked` 或 `rollback_required`。

证据来源：
- `NETWORK_REMEDIATION_EXECUTION_SHEETS_2026-04-20_v1.md`
- `BATCH1_MINIPC_CANARY_CHANGE_ORDER_2026-04-22.md`
- `BATCH1_24H_OBSERVATION_CHECKLIST_2026-04-23.md`

### FR-03 证据采集与导入

系统必须能导入和索引：
- `bench/**/*.json`
- `results/**/*.csv|txt`
- `mobile-compare/**/*.json`
- `fingerprints/**/*.sha256|*.rules|*.nft`
- `subscription-hits/**/*`
- ASUS 截图与人工签收记录

验收标准：
- bench 样本中任一关键字段为 `NA` 时，该样本标记为 `invalid_measurement`。
- mobile compare 中 `insufficient_data` 必须阻塞移动端封板。
- subscription hits 只有 template 时必须阻塞订阅链封板。
- fingerprint 为空内容哈希时必须标记为 `empty_snapshot_suspected`。

证据来源：
- `bench/20260422T021827Z/pc_direct.json`
- `bench/20260422T022825Z/pc_direct.json`
- `mobile-compare/manual_20260421_120408/compare_result.json`
- `fingerprints/epix/20260421T215802Z_baseline-local/fingerprint.sha256`
- `subscription-hits/hits.csv.template`

### FR-04 门禁引擎

系统必须提供可配置 gate：
- `no_na_fields`
- `http_200_or_reachable`
- `min_sample_count`
- `subscription_static_coverage`
- `subscription_live_hits`
- `mobile_valid_download_count`
- `fingerprint_non_empty`
- `p0_no_outage`
- `p1_no_repeated_instability`
- `secret_scan_pass`

验收标准：
- Batch1 Step0 遇到 `NA` 样本时必须阻止切换。
- 后续复测样本 HTTP 200 后才可进入 canary。
- 移动端 `valid_download_count < 2` 不得进入性能归因。

证据来源：
- `BATCH1_MINIPC_CANARY_CHANGE_ORDER_2026-04-22.md`
- `bench/20260422T021827Z/pc_direct.json`
- `bench/20260422T022825Z/pc_direct.json`
- `tools/compare_exitnodes.py`

### FR-05 回滚库

系统必须把每类变更绑定回滚动作：
- Exit Node 规则：`apply_exitnode_rules_safe.sh rollback`
- ASUS Path A：终端默认网关恢复 ASUS。
- ASUS Path B：ASUS DHCP 默认网关恢复 `192.168.50.1`。
- 订阅：回滚到上一 SHA-256。
- VPS sing-box：恢复 `/etc/sing-box/config.json.bak.<ts>`。
- 移动证据：删除或废弃错误 session，不影响线上。

验收标准：
- 没有 rollback 的 action 不能进入 `approved`。
- 回滚后必须要求最少三项复测：外网可达、国内可达、当前网关/订阅/服务状态。

证据来源：
- `P0_COMPLETION_REPORT_2026-04-20.md`
- `UNIFIED_OPS_RUNBOOK_2026-04-20.md`
- `RESTART_RECOVERY_GUIDE_2026-04-20.md`
- `BATCH1_24H_OBSERVATION_CHECKLIST_2026-04-23.md`

### FR-06 报告生成

系统必须生成：
- 现状审计报告
- 阶段执行报告
- 变更单
- 24h 观察报告
- 订阅发布报告
- 移动实测报告
- 回滚报告
- 交接报告

验收标准：
- 报告中每个关键结论必须有 evidence path。
- 报告不得输出明文 secret。
- 报告可以被 Git 管理，但敏感材料默认排除。

证据来源：
- `CURRENT_SOURCE_OF_TRUTH.md`
- `SUBSCRIPTION_RELEASE_MANIFEST_2026-04-20.md`
- `sync_to_github.sh`

### FR-07 多 Agent 协同接口

系统必须为多 Agent 提供只读上下文包：
- 当前资产事实
- 当前阶段状态
- 最近 evidence index
- 未决风险
- 用户需拍板事项
- 禁止引用的历史路径

验收标准：
- Agent 上下文包不包含 secret 明文。
- 每次 Agent 执行必须写入 `runs/<run_id>/agent_events.jsonl`。
- Agent 不能把模板证据解释为真实证据。

证据来源：
- `多设备统一网络管理项目配置情况及功能目标.md`
- `CURRENT_SOURCE_OF_TRUTH.md`

## 6. 非功能需求（NFR）

### NFR-01 本地优先与低依赖

- 必须能在 macOS 本地运行。
- MVP 不依赖云数据库。
- 读写普通文件即可恢复状态。
- 不能要求生产设备长期开放高权限接口。

### NFR-02 安全

- 默认 secret redaction。
- 配置扫描必须覆盖 UUID、private_key、password、token、certificate key、订阅 URL。
- 报告输出不得包含敏感值。
- 执行生产变更前必须显式确认。

### NFR-03 可审计

- 所有 run、gate、decision、rollback 必须落盘。
- 人工操作必须有 `operator_confirmation` 字段。
- 每个 evidence 文件必须记录来源、时间、场景、设备、有效性。

### NFR-04 可维护

- 配置文件必须可人工编辑。
- 错误提示必须给出下一步，不只返回异常。
- 目录结构必须稳定，避免再次路径漂移。

### NFR-05 可扩展

- 新设备、新阶段、新 gate、新脚本应通过配置扩展。
- 控制台核心不能写死 miniPC、EpixNAS、Contabo。

## 7. KPI 与 DoD

### MVP KPI

- 100% 阶段有 precheck、gate、rollback、evidence_required。
- 100% 关键报告结论带 evidence path。
- 0 个报告明文输出 secret。
- Batch1/Batch2 执行流能自动识别 `NA` 样本并阻断。
- 移动端 `insufficient_data` 能自动阻断封板。
- 订阅只有 template、无 live hits 时能自动阻断封板。
- 30 分钟巡检报告能在 1 条命令内生成。

### MVP DoD

- 可以从现有 `network-audit-2026Q2/` 导入资产、脚本、配置、bench、mobile、fingerprint、subscription 模板。
- 可以生成一份“当前不能上线运营的阻塞清单”。
- 可以创建并执行一个 dry-run 阶段，例如 `Batch1 observation checkpoint`。
- 可以生成脱敏报告。
- 可以把所有 run 归档到稳定目录，并被后续 Agent 读取。

## 8. 运营与持续维护要求

- 每次维护前必须创建 run：记录目标、设备、操作者、预期影响面。
- 每次维护后必须产生报告：成功、失败、回滚、证据、遗留风险。
- 每周至少一次 facts audit：检查悬空引用、空字段、路径漂移。
- 每月一次恢复演练：VPS、Exit Node、订阅、ASUS 网关至少各演练一次。
- 每季度一次权限与 secret 审计：确认远端仓库、Agent 上下文、报告归档中没有泄漏。
- 交接时只允许交接控制台生成的 `handoff_report.md` 与脱敏 evidence index，不交接散乱旧文档。

## 9. 开发前必须确认的输入

- 是否允许 MVP 对生产设备执行命令，还是只允许 dry-run + 人工复制命令。
- 本地控制台形态：CLI-only、TUI、Web UI 三者优先级。
- secret 处理策略：现有配置中的凭据是保留并脱敏，还是迁移到本地 secrets store。
- Batch2 扩围策略：继续单设备手动网关，还是允许 ASUS 全局 DHCP 默认网关变更。
- NAS/Obsidian 与 OpenClaw/Hermes 在 MVP 中只纳入资产/健康检查，还是必须纳入端到端功能验收。
