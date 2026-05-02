import { FormEvent, useEffect, useMemo, useState } from "react";

type Language = "zh" | "en";
type AuthMode = "login" | "register";
type PageKey =
  | "dashboard"
  | "topology"
  | "devices"
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

function App() {
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem("uninode.language") as Language | null) ?? "zh";
  });
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [activePage, setActivePage] = useState<PageKey>("dashboard");
  const [summary, setSummary] = useState<ConsoleSummary>(defaultSummary);
  const [configStatus, setConfigStatus] = useState<ConfigStatus>(defaultConfigStatus);
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
      { label: t.cards.devices, value: summary.counts.devices },
      { label: t.cards.services, value: summary.counts.services },
      { label: t.cards.evidence, value: summary.counts.evidence },
      { label: t.cards.jobs, value: summary.counts.automation_jobs },
    ],
    [summary, t],
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
  }, []);

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
