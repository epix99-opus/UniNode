import { FormEvent, useEffect, useMemo, useState } from "react";

type Language = "zh" | "en";
type AuthMode = "login" | "register";
type PageKey =
  | "dashboard"
  | "topology"
  | "devices"
  | "services"
  | "evidence"
  | "automation"
  | "reports"
  | "settings";

type User = {
  id: number;
  email: string;
  display_name: string;
};

type ConsoleSummary = {
  health: {
    status: string;
    next_action: string;
  };
  counts: {
    devices: number;
    services: number;
    evidence: number;
    automation_jobs: number;
  };
  safety: {
    execution_mode: string;
    network_changes_require_approval: boolean;
    offline_policy: string;
  };
};

type ConfigStatus = {
  ok: boolean;
  errors: string[];
  warnings: string[];
  paths: Array<{
    id: string;
    path: string;
    required: boolean;
    status: string;
    next_action: string;
  }>;
  execution: {
    default_mode: string;
    require_approval_for_network_changes: boolean;
  };
  offline_policy: {
    default_offline_state: string;
    treat_expected_offline_as_failure: boolean;
  };
};

type Device = {
  id: string;
  name: string;
  type: string;
  role: string;
  ip_lan: string | null;
  ip_public: string | null;
  ip_tailscale: string | null;
  expected_online: boolean;
  human_action: string | null;
  status: string;
  missing_facts: string[];
  tags: string[];
};

type Service = {
  id: string;
  name: string;
  device_id: string;
  type: string;
  endpoint: string;
  expected_status: string;
  dependencies: string[];
  tags: string[];
};

type EvidenceSummary = {
  total: number;
  blocked_count: number;
  by_validity: Record<string, number>;
  by_type: Record<string, number>;
};

type SecurityFindings = {
  blocked: boolean;
  total: number;
  findings: Array<{
    id: string;
    type: string;
    label: string;
    severity: string;
    source_path: string;
    line: number;
    redacted_excerpt: string;
  }>;
};

type TopologyGraph = {
  active_layer: string;
  layers: Array<{ id: string; name: string }>;
  nodes: Array<{
    id: string;
    label: string;
    type: string;
    status: string;
    hint: string | null;
    layers: string[];
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    layer: string;
    label: string;
  }>;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const copy = {
  zh: {
    product: "UniNode Ops Console",
    eyebrow: "本地优先 · 只读优先 · 证据驱动",
    authTitle: "进入你的网络运维驾驶舱",
    authSubtitle:
      "注册或登录后可以查看 Dashboard、拓扑、设备、证据、自动化任务与报告。默认 dry-run，不会修改生产网络。",
    email: "邮箱",
    password: "密码",
    displayName: "显示名称",
    login: "登录",
    register: "注册",
    needAccount: "没有账号？创建本地账号",
    haveAccount: "已有账号？直接登录",
    logout: "退出",
    signedInAs: "当前用户",
    nav: {
      dashboard: "总览",
      topology: "拓扑",
      devices: "设备",
      services: "服务",
      evidence: "证据",
      automation: "自动化",
      reports: "报告",
      settings: "设置",
    },
    heroTitle: "从这里判断网络是否真的可运营",
    heroBody:
      "不是堆脚本，也不是漂亮空壳。这个版本把安全边界、证据缺口、离线设备和下一步动作放到一屏里。",
    status: "状态",
    nextAction: "下一步",
    cards: {
      devices: "设备",
      services: "服务",
      evidence: "证据",
      jobs: "任务",
    },
    safety: "安全边界",
    configStatus: "配置状态",
    configOk: "配置可用",
    configNeedsWork: "配置需处理",
    required: "必需",
    optional: "可选",
    present: "存在",
    missing: "缺失",
    errors: "错误",
    warnings: "提示",
    deviceInventory: "设备事实源",
    expectedOnline: "预期在线",
    humanAction: "人工动作",
    serviceCatalog: "服务目录",
    topologyGraph: "拓扑图",
    nodes: "节点",
    edges: "连接",
    layer: "图层",
    endpoint: "端点",
    dependencies: "依赖",
    expectedStatus: "预期状态",
    evidenceSummary: "证据摘要",
    totalEvidence: "证据总数",
    blockedEvidence: "阻塞证据",
    byValidity: "按有效性",
    byType: "按类型",
    securityRisk: "安全风险",
    securityBlocked: "安全阻塞",
    noSecurityFindings: "未发现敏感字段",
    securityFindings: "发现项",
    missingFacts: "缺失事实",
    noMissingFacts: "事实完整",
    lanIp: "LAN IP",
    publicIp: "公网 IP",
    tailscaleIp: "Tailscale IP",
    dryRun: "默认执行模式",
    approval: "生产网络变更需要审批",
    offline: "离线设备策略",
    pageEmpty: "当前页面是 v0.1 交互骨架，后续任务会接入真实配置和 evidence 扫描。",
    actions: {
      importFacts: "导入事实源",
      scanEvidence: "扫描证据",
      createDryRun: "创建 dry-run 任务",
    },
    pages: {
      dashboard: "查看全局健康、证据缺口和人工动作。",
      topology: "切换物理拓扑、Tailscale、全球访问、NAS/Agent 层。",
      devices: "管理 Huawei、ASUS、miniPC、EpixNAS、VPS、腾讯云和终端设备。",
      services: "查看 VPN 订阅、旁路由、Tailscale、NAS、Obsidian 和 Agent 服务。",
      evidence: "识别 valid、invalid、template_only、missing、stale 和 requires_human_collection。",
      automation: "生成只读检查、诊断、报告任务，配置动作必须审批。",
      reports: "生成当前态报告、证据缺口报告、安全报告和 Agent 上下文。",
      settings: "配置语言、工作目录、安全策略、执行模式和 Agent provider。",
    },
  },
  en: {
    product: "UniNode Ops Console",
    eyebrow: "Local-first · readonly-first · evidence-driven",
    authTitle: "Enter your network operations cockpit",
    authSubtitle:
      "Register or sign in to access Dashboard, topology, devices, evidence, automation jobs, and reports. The default mode is dry-run and never changes production networking.",
    email: "Email",
    password: "Password",
    displayName: "Display name",
    login: "Sign in",
    register: "Register",
    needAccount: "Need an account? Create a local one",
    haveAccount: "Already registered? Sign in",
    logout: "Log out",
    signedInAs: "Signed in as",
    nav: {
      dashboard: "Dashboard",
      topology: "Topology",
      devices: "Devices",
      services: "Services",
      evidence: "Evidence",
      automation: "Automation",
      reports: "Reports",
      settings: "Settings",
    },
    heroTitle: "Know whether the network is actually operable",
    heroBody:
      "Not a pile of scripts. Not a static shell. This version puts safety boundaries, evidence gaps, offline devices, and next actions in one interactive console.",
    status: "Status",
    nextAction: "Next action",
    cards: {
      devices: "Devices",
      services: "Services",
      evidence: "Evidence",
      jobs: "Jobs",
    },
    safety: "Safety Boundary",
    configStatus: "Config Status",
    configOk: "Config ready",
    configNeedsWork: "Config needs attention",
    required: "Required",
    optional: "Optional",
    present: "Present",
    missing: "Missing",
    errors: "Errors",
    warnings: "Warnings",
    deviceInventory: "Device Inventory",
    expectedOnline: "Expected online",
    humanAction: "Human action",
    serviceCatalog: "Service Catalog",
    topologyGraph: "Topology Graph",
    nodes: "Nodes",
    edges: "Edges",
    layer: "Layer",
    endpoint: "Endpoint",
    dependencies: "Dependencies",
    expectedStatus: "Expected status",
    evidenceSummary: "Evidence Summary",
    totalEvidence: "Total evidence",
    blockedEvidence: "Blocked evidence",
    byValidity: "By validity",
    byType: "By type",
    securityRisk: "Security Risk",
    securityBlocked: "Security blocked",
    noSecurityFindings: "No sensitive fields found",
    securityFindings: "Findings",
    missingFacts: "Missing facts",
    noMissingFacts: "Facts complete",
    lanIp: "LAN IP",
    publicIp: "Public IP",
    tailscaleIp: "Tailscale IP",
    dryRun: "Default execution mode",
    approval: "Production network changes require approval",
    offline: "Offline device policy",
    pageEmpty: "This page is the v0.1 interactive shell. Later tasks will connect real config and evidence scans.",
    actions: {
      importFacts: "Import facts",
      scanEvidence: "Scan evidence",
      createDryRun: "Create dry-run job",
    },
    pages: {
      dashboard: "Review global health, evidence gaps, and human actions.",
      topology: "Switch between physical topology, Tailscale, global access, NAS, and Agent layers.",
      devices: "Manage Huawei, ASUS, miniPC, EpixNAS, VPS, Tencent Cloud, and terminal devices.",
      services: "Review VPN subscriptions, gateway, Tailscale, NAS, Obsidian, and Agent services.",
      evidence: "Classify valid, invalid, template_only, missing, stale, and requires_human_collection.",
      automation: "Generate readonly checks, diagnostics, and report tasks. Config actions need approval.",
      reports: "Generate current status, evidence gap, security, and Agent context reports.",
      settings: "Configure language, workspace paths, safety policy, execution mode, and Agent providers.",
    },
  },
} satisfies Record<Language, Record<string, unknown>>;

const pageKeys: PageKey[] = [
  "dashboard",
  "topology",
  "devices",
  "services",
  "evidence",
  "automation",
  "reports",
  "settings",
];

const defaultSummary: ConsoleSummary = {
  health: {
    status: "evidence_gap",
    next_action: "Import facts and scan evidence before claiming readiness.",
  },
  counts: {
    devices: 0,
    services: 0,
    evidence: 0,
    automation_jobs: 0,
  },
  safety: {
    execution_mode: "dry_run",
    network_changes_require_approval: true,
    offline_policy: "needs_human_power_on",
  },
};

const defaultConfigStatus: ConfigStatus = {
  ok: false,
  errors: ["CONFIG_ERROR"],
  warnings: [],
  paths: [],
  execution: {
    default_mode: "dry_run",
    require_approval_for_network_changes: true,
  },
  offline_policy: {
    default_offline_state: "needs_human_power_on",
    treat_expected_offline_as_failure: false,
  },
};

const defaultEvidenceSummary: EvidenceSummary = {
  total: 0,
  blocked_count: 0,
  by_validity: {},
  by_type: {},
};

const defaultSecurityFindings: SecurityFindings = {
  blocked: false,
  total: 0,
  findings: [],
};

const defaultTopology: TopologyGraph = {
  active_layer: "physical",
  layers: [],
  nodes: [],
  edges: [],
};

function App() {
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem("uninode.language") as Language | null) ?? "zh";
  });
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [activePage, setActivePage] = useState<PageKey>("dashboard");
  const [summary, setSummary] = useState<ConsoleSummary>(defaultSummary);
  const [configStatus, setConfigStatus] = useState<ConfigStatus>(defaultConfigStatus);
  const [devices, setDevices] = useState<Device[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [evidenceSummary, setEvidenceSummary] = useState<EvidenceSummary>(defaultEvidenceSummary);
  const [securityFindings, setSecurityFindings] = useState<SecurityFindings>(defaultSecurityFindings);
  const [topologyLayer, setTopologyLayer] = useState("physical");
  const [topology, setTopology] = useState<TopologyGraph>(defaultTopology);
  const [token, setToken] = useState(() => localStorage.getItem("uninode.token") ?? "");
  const [user, setUser] = useState<User | null>(() => {
    const rawUser = localStorage.getItem("uninode.user");
    return rawUser ? (JSON.parse(rawUser) as User) : null;
  });
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "UniNode Operator",
  });
  const [message, setMessage] = useState("");
  const t = copy[language];

  const statCards = useMemo(
    () => [
      { label: t.cards.devices, value: devices.length || summary.counts.devices },
      { label: t.cards.services, value: services.length || summary.counts.services },
      { label: t.cards.evidence, value: evidenceSummary.total || summary.counts.evidence },
      { label: t.cards.jobs, value: summary.counts.automation_jobs },
    ],
    [devices.length, evidenceSummary.total, services.length, summary, t],
  );

  useEffect(() => {
    localStorage.setItem("uninode.language", language);
  }, [language]);

  useEffect(() => {
    fetch(`${apiBase}/api/console/summary`)
      .then((response) => response.json())
      .then((payload: ConsoleSummary) => setSummary(payload))
      .catch(() => setSummary(defaultSummary));
    fetch(`${apiBase}/api/config/status`)
      .then((response) => response.json())
      .then((payload: ConfigStatus) => setConfigStatus(payload))
      .catch(() => setConfigStatus(defaultConfigStatus));
    fetch(`${apiBase}/api/devices`)
      .then((response) => response.json())
      .then((payload: Device[]) => setDevices(payload))
      .catch(() => setDevices([]));
    fetch(`${apiBase}/api/services`)
      .then((response) => response.json())
      .then((payload: Service[]) => setServices(payload))
      .catch(() => setServices([]));
    fetch(`${apiBase}/api/evidence/summary`)
      .then((response) => response.json())
      .then((payload: EvidenceSummary) => setEvidenceSummary(payload))
      .catch(() => setEvidenceSummary(defaultEvidenceSummary));
    fetch(`${apiBase}/api/security/findings`)
      .then((response) => response.json())
      .then((payload: SecurityFindings) => setSecurityFindings(payload))
      .catch(() => setSecurityFindings(defaultSecurityFindings));
  }, []);

  useEffect(() => {
    fetch(`${apiBase}/api/topology?layer=${encodeURIComponent(topologyLayer)}`)
      .then((response) => response.json())
      .then((payload: TopologyGraph) => setTopology(payload))
      .catch(() => setTopology(defaultTopology));
  }, [topologyLayer]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const endpoint = authMode === "login" ? "login" : "register";
    const payload =
      authMode === "login"
        ? { email: form.email, password: form.password }
        : form;

    try {
      const response = await fetch(`${apiBase}/api/auth/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        setMessage(data.detail ?? "Authentication failed");
        return;
      }
      setToken(data.token);
      setUser(data.user);
      localStorage.setItem("uninode.token", data.token);
      localStorage.setItem("uninode.user", JSON.stringify(data.user));
    } catch {
      setMessage("API is not reachable. Start the FastAPI server first.");
    }
  }

  function logout() {
    setToken("");
    setUser(null);
    localStorage.removeItem("uninode.token");
    localStorage.removeItem("uninode.user");
  }

  if (!token || !user) {
    return (
      <main className="auth-layout">
        <section className="auth-copy">
          <button
            className="language-toggle"
            type="button"
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
          >
            {language === "zh" ? "English" : "中文"}
          </button>
          <p className="eyebrow">{t.eyebrow}</p>
          <h1>{t.authTitle}</h1>
          <p>{t.authSubtitle}</p>
          <div className="orbit-map" aria-hidden="true">
            <span className="node node-a" />
            <span className="node node-b" />
            <span className="node node-c" />
            <span className="node node-d" />
          </div>
        </section>

        <form className="auth-panel" onSubmit={submitAuth}>
          <h2>{authMode === "login" ? t.login : t.register}</h2>
          <label>
            {t.email}
            <input
              autoComplete="email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
            />
          </label>
          {authMode === "register" && (
            <label>
              {t.displayName}
              <input
                value={form.display_name}
                onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                required
              />
            </label>
          )}
          <label>
            {t.password}
            <input
              autoComplete={authMode === "login" ? "current-password" : "new-password"}
              minLength={authMode === "register" ? 12 : 1}
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              required
            />
          </label>
          {message && <p className="form-message">{message}</p>}
          <button className="primary-action" type="submit">
            {authMode === "login" ? t.login : t.register}
          </button>
          <button
            className="text-action"
            type="button"
            onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}
          >
            {authMode === "login" ? t.needAccount : t.haveAccount}
          </button>
        </form>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="brand-kicker">UniNode</p>
          <h1>{t.product}</h1>
        </div>
        <nav aria-label="Primary navigation">
          {pageKeys.map((key) => (
            <button
              className={activePage === key ? "active" : ""}
              key={key}
              type="button"
              onClick={() => setActivePage(key)}
            >
              {t.nav[key]}
            </button>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p>{t.signedInAs}</p>
            <strong>{user.display_name}</strong>
          </div>
          <div className="topbar-actions">
            <button type="button" onClick={() => setLanguage(language === "zh" ? "en" : "zh")}>
              {language === "zh" ? "English" : "中文"}
            </button>
            <button type="button" onClick={logout}>
              {t.logout}
            </button>
          </div>
        </header>

        <section className="hero-card" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">{t.eyebrow}</p>
            <h2 id="page-title">{t.heroTitle}</h2>
            <p className="lede">{t.heroBody}</p>
          </div>
          <div className="status-pill">
            <span>{t.status}</span>
            <strong>{summary.health.status}</strong>
          </div>
        </section>

        <section className="status-grid" aria-label="Operations counters">
          {statCards.map((card) => (
            <article className="status-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
            </article>
          ))}
        </section>

        <section className="work-panel">
          <div>
            <p className="eyebrow">{t.nav[activePage]}</p>
            <h2>{t.pages[activePage]}</h2>
            <p>{t.pageEmpty}</p>
          </div>
          {activePage === "devices" && (
            <div className="device-list" aria-label={t.deviceInventory}>
              {devices.map((device) => (
                <article className="device-card" key={device.id}>
                  <div className="device-card-header">
                    <div>
                      <strong>{device.name}</strong>
                      <p>{device.role}</p>
                    </div>
                    <span>{device.status}</span>
                  </div>
                  <dl>
                    <div>
                      <dt>{t.lanIp}</dt>
                      <dd>{device.ip_lan ?? "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.publicIp}</dt>
                      <dd>{device.ip_public ?? "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.tailscaleIp}</dt>
                      <dd>{device.ip_tailscale ?? "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.expectedOnline}</dt>
                      <dd>{String(device.expected_online)}</dd>
                    </div>
                    <div>
                      <dt>{t.humanAction}</dt>
                      <dd>{device.human_action ?? "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.missingFacts}</dt>
                      <dd>
                        {device.missing_facts.length > 0
                          ? device.missing_facts.join(", ")
                          : t.noMissingFacts}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
          {activePage === "topology" && (
            <div className="topology-board" aria-label={t.topologyGraph}>
              <div className="layer-tabs">
                {(topology.layers.length > 0 ? topology.layers : [{ id: topologyLayer, name: topologyLayer }]).map(
                  (layer) => (
                    <button
                      className={layer.id === topology.active_layer ? "active" : ""}
                      key={layer.id}
                      type="button"
                      onClick={() => setTopologyLayer(layer.id)}
                    >
                      {layer.name}
                    </button>
                  ),
                )}
              </div>
              <div className="topology-grid">
                <section>
                  <h3>{t.nodes}</h3>
                  {topology.nodes.map((node) => (
                    <article className={`topology-node ${node.status}`} key={node.id}>
                      <strong>{node.label}</strong>
                      <span>{node.type}</span>
                      <p>{node.status}</p>
                      {node.hint && <small>{node.hint}</small>}
                    </article>
                  ))}
                </section>
                <section>
                  <h3>{t.edges}</h3>
                  {topology.edges.map((edge) => (
                    <article className="topology-edge" key={edge.id}>
                      <strong>
                        {edge.source} → {edge.target}
                      </strong>
                      <span>
                        {t.layer}: {edge.layer}
                      </span>
                      <p>{edge.label}</p>
                    </article>
                  ))}
                </section>
              </div>
            </div>
          )}
          {activePage === "services" && (
            <div className="service-list" aria-label={t.serviceCatalog}>
              {services.map((service) => (
                <article className="service-card" key={service.id}>
                  <div className="device-card-header">
                    <div>
                      <strong>{service.name}</strong>
                      <p>{service.type}</p>
                    </div>
                    <span>{service.expected_status}</span>
                  </div>
                  <dl>
                    <div>
                      <dt>Device</dt>
                      <dd>{service.device_id}</dd>
                    </div>
                    <div>
                      <dt>{t.endpoint}</dt>
                      <dd>{service.endpoint}</dd>
                    </div>
                    <div>
                      <dt>{t.dependencies}</dt>
                      <dd>{service.dependencies.length > 0 ? service.dependencies.join(", ") : "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.expectedStatus}</dt>
                      <dd>{service.expected_status}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
          {activePage === "evidence" && (
            <div className="evidence-summary" aria-label={t.evidenceSummary}>
              <article>
                <span>{t.totalEvidence}</span>
                <strong>{evidenceSummary.total}</strong>
              </article>
              <article>
                <span>{t.blockedEvidence}</span>
                <strong>{evidenceSummary.blocked_count}</strong>
              </article>
              <article>
                <span>{t.byValidity}</span>
                <p>
                  {Object.entries(evidenceSummary.by_validity)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(" · ") || "-"}
                </p>
              </article>
              <article>
                <span>{t.byType}</span>
                <p>
                  {Object.entries(evidenceSummary.by_type)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(" · ") || "-"}
                </p>
              </article>
            </div>
          )}
          <div className="action-row">
            <button type="button">{t.actions.importFacts}</button>
            <button type="button">{t.actions.scanEvidence}</button>
            <button type="button">{t.actions.createDryRun}</button>
          </div>
        </section>

        <section className="safety-panel">
          <h2>{t.safety}</h2>
          <dl>
            <div>
              <dt>{t.dryRun}</dt>
              <dd>{summary.safety.execution_mode}</dd>
            </div>
            <div>
              <dt>{t.approval}</dt>
              <dd>{String(summary.safety.network_changes_require_approval)}</dd>
            </div>
            <div>
              <dt>{t.offline}</dt>
              <dd>{summary.safety.offline_policy}</dd>
            </div>
          </dl>
          <p>
            {t.nextAction}: {summary.health.next_action}
          </p>
          <div className={securityFindings.blocked ? "security-card blocked" : "security-card"}>
            <span>{t.securityRisk}</span>
            <strong>{securityFindings.blocked ? t.securityBlocked : t.noSecurityFindings}</strong>
            <p>
              {t.securityFindings}: {securityFindings.total}
            </p>
            {securityFindings.findings.slice(0, 3).map((finding) => (
              <small key={finding.id}>
                {finding.label} · {finding.source_path}:{finding.line}
              </small>
            ))}
          </div>
        </section>

        <section className="config-panel">
          <div className="config-heading">
            <div>
              <p className="eyebrow">{t.configStatus}</p>
              <h2>{configStatus.ok ? t.configOk : t.configNeedsWork}</h2>
            </div>
            <span className={configStatus.ok ? "config-badge ok" : "config-badge warn"}>
              {configStatus.ok ? "OK" : "CHECK"}
            </span>
          </div>
          <div className="path-list">
            {configStatus.paths.map((item) => (
              <article className="path-row" key={item.id}>
                <div>
                  <strong>{item.id}</strong>
                  <p>{item.path}</p>
                </div>
                <span className={item.status === "present" ? "path-present" : "path-missing"}>
                  {item.status === "present" ? t.present : t.missing}
                </span>
                <small>{item.required ? t.required : t.optional}</small>
              </article>
            ))}
          </div>
          {(configStatus.errors.length > 0 || configStatus.warnings.length > 0) && (
            <div className="config-messages">
              {configStatus.errors.length > 0 && (
                <p>
                  {t.errors}: {configStatus.errors.join(", ")}
                </p>
              )}
              {configStatus.warnings.length > 0 && (
                <p>
                  {t.warnings}: {configStatus.warnings.join(", ")}
                </p>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
