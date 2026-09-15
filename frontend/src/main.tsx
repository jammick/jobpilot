import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  analyses,
  developer,
  knowledge,
  optimizations,
  resumes,
  settings,
  workspace,
  type Analysis,
  type BatchUploadResult,
  type KnowledgeBase,
  type OptimizationDraft,
  type Report,
  type Resume,
  type RoleProfile,
} from "./api";
import "./styles.css";
import { motion } from "motion/react";
const qc = new QueryClient();
const MODEL_PROVIDERS: Record<string, { base: string; model: string }> = {
  openai: { base: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  deepseek: { base: "https://api.deepseek.com", model: "deepseek-chat" },
  zhipu: {
    base: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
  },
  qwen: {
    base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
  },
  moonshot: { base: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  custom: { base: "", model: "" },
};

function inferProvider(baseUrl?: string, model?: string) {
  const base = (baseUrl ?? "").toLowerCase().replace(/\/$/, "");
  const modelName = (model ?? "").toLowerCase();
  if (base.includes("deepseek") || modelName.includes("deepseek")) return "deepseek";
  if (base.includes("bigmodel") || modelName.startsWith("glm-")) return "zhipu";
  if (base.includes("dashscope") || modelName.startsWith("qwen")) return "qwen";
  if (base.includes("moonshot") || modelName.includes("moonshot")) return "moonshot";
  if (base.includes("openai.com") || modelName.startsWith("gpt-")) return "openai";
  return "custom";
}

function errorDetail(error: unknown, fallback: string) {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error
  ) {
    const detail = (error as { response?: { data?: { detail?: unknown } } }).response
      ?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

const REPORT_SECTION_LABELS = new Set(
  [
    "工作职责", "岗位职责", "职位职责", "工作内容", "职位描述", "岗位描述",
    "任职要求", "岗位要求", "职位要求", "任职资格", "资格要求", "岗位资格",
    "优先条件", "加分项", "技能要求", "教育背景", "学历要求", "关于我们",
    "福利待遇", "薪资福利", "responsibilities", "requirements", "qualifications",
    "preferredqualifications", "jobdescription", "aboutus",
  ].map((item) => item.toLowerCase().replace(/[\s:：/|·_-]+/g, "")),
);

function plainReportText(value?: string | null) {
  return (value ?? "")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function cleanReportLabel(value?: string | null) {
  const cleaned = plainReportText(value)
    .replace(/^\s*(?:(?:>|[-+*•]|\d{1,2}[.)、])\s*)+/, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[*_`~：:|\s]+|[*_`~：:|\s]+$/g, "");
  const compact = cleaned.toLowerCase().replace(/[\s:：/|·_-]+/g, "");
  return REPORT_SECTION_LABELS.has(compact) ? "" : cleaned;
}

function cleanReportList(values?: string[]) {
  return [...new Set((values ?? []).map(cleanReportLabel).filter(Boolean))];
}

function isUsefulEvidence(value?: string | null) {
  const cleaned = plainReportText(value).replace(/^[“”"']+|[“”"']+$/g, "").trim();
  if (cleaned.length < 6 || !cleanReportLabel(cleaned)) return false;
  return !/^(?:(?:https?:\/\/|www\.)\S+|(?:com|cn|net|org)\/\S+)$/i.test(cleaned);
}
const HeroMotion = React.lazy(() =>
  import("./HeroMotion").then((module) => ({ default: module.HeroMotion })),
);
type N =
  | "spark"
  | "home"
  | "plus"
  | "archive"
  | "arrow"
  | "upload"
  | "file"
  | "check"
  | "logout"
  | "chevron"
  | "settings"
  | "trash";
function I({ n, s = 18 }: { n: N; s?: number }) {
  const p: Record<N, React.ReactNode> = {
    spark: (
      <>
        <path d="M12 2l1.55 5.45L19 9l-5.45 1.55L12 16l-1.55-5.45L5 9l5.45-1.55L12 2Z" />
        <path d="M19 15l.65 2.35L22 18l-2.35.65L19 21l-.65-2.35L16 18l2.35-.65L19 15Z" />
      </>
    ),
    home: (
      <>
        <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Z" />
        <path d="M9 21v-6h6v6" />
      </>
    ),
    plus: (
      <>
        <path d="M12 5v14M5 12h14" />
      </>
    ),
    archive: (
      <>
        <rect x="3" y="4" width="18" height="5" rx="1" />
        <path d="M5 9v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V3M7 8l5-5 5 5" />
        <path d="M5 14v6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-6" />
      </>
    ),
    file: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </>
    ),
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    logout: (
      <>
        <path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-5" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    trash: (
      <>
        <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13" />
        <path d="M10 11v5M14 11v5" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.02 2.02-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.55V20.2H12v-.09A1.7 1.7 0 0 0 10.97 18.56a1.7 1.7 0 0 0-1.88.34l-.06.06-2.02-2.02.06-.06A1.7 1.7 0 0 0 7.41 15a1.7 1.7 0 0 0-1.55-1.03H5.8V11h.06a1.7 1.7 0 0 0 1.55-1.03 1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.02-2.02.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 12 4.86V4.8h2.86v.06a1.7 1.7 0 0 0 1.03 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.02 2.02-.06.06a1.7 1.7 0 0 0-.34 1.88A1.7 1.7 0 0 0 21 11h.06v2.94H21A1.7 1.7 0 0 0 19.4 15Z" />
      </>
    ),
  };
  return (
    <svg
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {p[n]}
    </svg>
  );
}
function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="rail-top">
          <span className="rail-mark">
            <I n="spark" s={17} />
          </span>
          <span className="rail-line" />
        </div>
        <nav className="rail-nav">
          <NavLink to="/resumes" title="简历库">
            <I n="file" />
            <span>简历库</span>
          </NavLink>
          <NavLink to="/new" title="新建匹配">
            <I n="plus" />
            <span>新建匹配</span>
          </NavLink>
          <NavLink to="/history" title="分析档案">
            <I n="archive" />
            <span>分析档案</span>
          </NavLink>
          <NavLink to="/settings" title="模型设置">
            <I n="settings" />
            <span>模型设置</span>
          </NavLink>
        </nav>
        <div className="rail-bottom">
          <NavLink className="rail-logo" to="/">
            <i>
              JOB
              <br />
              PILOT
            </i>
          </NavLink>
        </div>
      </aside>
      <motion.main
        className="canvas"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.main>
    </div>
  );
}
function Title({
  children,
  kicker = "JOBPILOT / CAREER INTELLIGENCE",
}: {
  children: React.ReactNode;
  kicker?: string;
}) {
  return (
    <header className="topline">
      <p>{kicker}</p>
      <h1>{children}</h1>
    </header>
  );
}
function ConfirmDialog({
  title,
  description,
  confirmLabel,
  pending,
  error,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  pending: boolean;
  error?: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel, pending]);
  return (
    <motion.div
      className="confirm-layer"
      role="presentation"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onMouseDown={(event) => event.target === event.currentTarget && !pending && onCancel()}
    >
      <motion.section
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-description"
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="confirm-icon"><I n="trash" s={19} /></span>
        <p className="eyebrow">DELETE / IRREVERSIBLE</p>
        <h2 id="confirm-title">{title}</h2>
        <p id="confirm-description">{description}</p>
        {error && <div className="confirm-error">{error}</div>}
        <footer>
          <button type="button" onClick={onCancel} disabled={pending}>取消</button>
          <button className="danger-button" type="button" onClick={onConfirm} disabled={pending}>
            {pending ? "正在删除…" : confirmLabel}
          </button>
        </footer>
      </motion.section>
    </motion.div>
  );
}
function Task({ x, onDelete }: { x: Analysis; onDelete?: (analysis: Analysis) => void }) {
  const done = x.status === "completed" || x.status === "needs_review";
  const failed = x.status === "failed";
  const score = x.total_score ?? x.report?.total;
  return (
    <div className="task-row-shell">
      <NavLink className="task-row" to={"/analysis/" + x.id}>
        <span
          className={
            "task-status " + (done ? "completed" : failed ? "failed" : "")
          }
        >
          {done ? <I n="check" s={13} /> : failed ? "!" : "…"}
        </span>
        <div>
          <b>
            {done
              ? typeof score === "number"
                ? `岗位匹配度 ${score}`
                : "评分已完成 · 等待同步"
              : failed
                ? "分析失败 · 可重新尝试"
                : "正在生成分析"}
          </b>
          <small>{new Date(x.created_at).toLocaleDateString("zh-CN")}</small>
        </div>
        <I n="chevron" s={16} />
      </NavLink>
      {onDelete && (
        <button
          className="row-delete"
          type="button"
          title="删除分析"
          aria-label="删除这条分析"
          onClick={() => onDelete(x)}
        >
          <I n="trash" s={15} />
        </button>
      )}
    </div>
  );
}
function Landing() {
  return (
    <div className="landing">
      <header className="landing-head">
        <span className="landing-word">JOBPILOT</span>
        <span>CAREER INTELLIGENCE / 2026</span>
      </header>
      <main className="landing-main">
        <section>
          <p className="eyebrow">MAKE YOUR NEXT MOVE CLEAR</p>
          <h1>
            让简历与机会，
            <br />
            <em>认真相遇。</em>
          </h1>
          <p>
            一个为真实求职决策而设计的 AI
            工作台。读取简历、理解岗位、把判断还给证据。
          </p>
          <NavLink className="landing-start" to="/new">
            开始制作 <I n="arrow" />
          </NavLink>
          <small>无需登录 · 本地私密工作区</small>
        </section>
        <React.Suspense
          fallback={
            <div className="remotion-hero motion-fallback">
              <I n="spark" s={28} />
            </div>
          }
        >
          <HeroMotion />
        </React.Suspense>
      </main>
      <footer className="landing-foot">
        <span>01 / 上传简历</span>
        <span>02 / 粘贴岗位</span>
        <span>03 / 获得证据报告</span>
        <NavLink to="/resumes">
          浏览简历库 <I n="arrow" s={14} />
        </NavLink>
      </footer>
    </div>
  );
}
function Home() {
  const { data: list = [] } = useQuery({
    queryKey: ["analyses"],
    queryFn: () => analyses.all().then((r) => r.data),
  });
  return (
    <Shell>
      <section className="hero-space">
        <div className="hero-meta">
          <span className="live-dot" /> CAREER AGENT IS READY{" "}
          <small>本地私密工作区</small>
        </div>
        <h1>
          让下一份工作，
          <br />
          <em>有迹可循。</em>
        </h1>
        <p>
          上传简历，交给 Agent
          阅读岗位要求。它会把“感觉合适”拆成可验证的证据、分数和下一步。
        </p>
        <NavLink className="hero-action" to="/new">
          <span>
            <I n="spark" />
          </span>
          开始一次岗位匹配 <I n="arrow" />
        </NavLink>
      </section>
      <section className="hero-visual">
        <div className="visual-grain" />
        <div className="visual-header">
          <span>● JOBPILOT AGENT</span>
          <span>01 / 04</span>
        </div>
        <div className="visual-stack">
          <div className="visual-document">
            <p>RESUME</p>
            <b>
              职业叙事，
              <br />
              从这里开始。
            </b>
            <span>PDF · DOCX · 批量导入</span>
          </div>
          <div className="visual-pulse">
            <i />
            <i />
            <i />
            <i />
          </div>
          <div className="visual-score">
            <span>匹配信号</span>
            <strong>86</strong>
            <b>值得投递</b>
            <small>证据已建立</small>
          </div>
        </div>
        <div className="visual-footer">
          <span>简历资料</span>
          <I n="arrow" s={16} />
          <span>岗位理解</span>
          <I n="arrow" s={16} />
          <span>匹配证据</span>
        </div>
      </section>
      <section className="home-lower">
        <div className="principles">
          <p className="eyebrow">HOW IT WORKS</p>
          <h2>
            不替你编故事，
            <br />
            只替你找到<strong>证据。</strong>
          </h2>
          <div className="principle-list">
            <span>
              <b>01</b>解析简历与岗位 JD
            </span>
            <span>
              <b>02</b>固定权重生成匹配分
            </span>
            <span>
              <b>03</b>输出可执行优化建议
            </span>
          </div>
        </div>
        <div className="recent-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">RECENT SIGNALS</p>
              <h3>最近的分析</h3>
            </div>
            <NavLink to="/history">
              全部档案 <I n="arrow" s={15} />
            </NavLink>
          </div>
          {list.length ? (
            list.slice(0, 3).map((x) => <Task key={x.id} x={x} />)
          ) : (
            <div className="empty-state">
              <span>
                <I n="file" />
              </span>
              <p>
                还没有分析记录。
                <br />
                从第一份简历开始吧。
              </p>
            </div>
          )}
        </div>
      </section>
    </Shell>
  );
}
function ResumeLibrary() {
  const client = useQueryClient();
  const { data: list = [] } = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumes.all().then((r) => r.data),
  });
  const [batch, setBatch] = useState<BatchUploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Resume | null>(null);
  const upload = useMutation({
    mutationFn: (files: File[]) => resumes.uploadBatch(files),
    onSuccess: (r) => {
      setUploadError(null);
      setBatch(r.data);
      client.invalidateQueries({ queryKey: ["resumes"] });
    },
    onError: (error: unknown) => {
      const detail =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === "string"
          ? (error as { response: { data: { detail: string } } }).response.data.detail
          : "导入失败，请确认文件为可复制文字的 PDF/DOCX，且不超过 8MB。";
      setUploadError(detail);
    },
  });
  const removeResume = useMutation({
    mutationFn: (id: string) => resumes.remove(id),
    onSuccess: () => {
      setDeleteTarget(null);
      client.invalidateQueries({ queryKey: ["resumes"] });
      client.invalidateQueries({ queryKey: ["analyses"] });
      client.invalidateQueries({ queryKey: ["history"] });
    },
  });
  return (
    <Shell>
      <div className="page-bar">
        <div>
          <p className="eyebrow">RESUME LIBRARY</p>
          <h1>我的简历</h1>
          <p className="page-description">
            集中管理原始资料，再针对具体岗位生成定向版本。
          </p>
        </div>
        <label className="pill-upload">
          <input
            type="file"
            multiple
            accept=".pdf,.docx"
            onChange={(e) =>
              e.target.files && (() => {
                setUploadError(null);
                upload.mutate(Array.from(e.target.files));
              })()
            }
          />
          <I n="upload" s={16} />
          {upload.isPending ? "正在导入…" : "导入简历"}
        </label>
      </div>
      {batch && (
        <div className="library-note">
          成功导入 {batch.imported.length} 份
          {batch.rejected.length ? `，${batch.rejected.length} 份未能读取` : ""}
        </div>
      )}
      {uploadError && <div className="library-note settings-error">{uploadError}</div>}
      <section className="resume-gallery">
        <NavLink to="/new" className="new-resume-tile">
          <span>
            <I n="plus" s={22} />
          </span>
          <b>开始新的岗位匹配</b>
          <small>选择简历并粘贴 JD</small>
        </NavLink>
        {list.map((resume: Resume, index) => (
          <article className="resume-tile" key={resume.id}>
            <div className={"resume-cover tone-" + (index % 4)}>
              <span>JOBPILOT</span>
              <I n="file" s={24} />
              <b>{resume.original_name.replace(/\.(pdf|docx)$/i, "")}</b>
              <small>PROFILE DOCUMENT</small>
            </div>
            <footer>
              <div>
                <b>{resume.original_name}</b>
                <small>
                  {new Date(resume.created_at).toLocaleDateString("zh-CN")}
                </small>
              </div>
              <div className="resume-actions">
                <NavLink
                  className="target-match"
                  to={`/new?resume=${resume.id}`}
                >
                  <I n="spark" s={14} />
                  匹配岗位
                </NavLink>
                <button
                  className="delete-resume"
                  type="button"
                  title="删除简历"
                  aria-label={`删除 ${resume.original_name}`}
                  onClick={() => setDeleteTarget(resume)}
                >
                  <I n="trash" s={14} />
                </button>
              </div>
            </footer>
          </article>
        ))}
      </section>
      {deleteTarget && (
        <ConfirmDialog
          title={`删除“${deleteTarget.original_name}”？`}
          description="源文件、文本分片、向量索引、关联分析和已生成的简历版本都会一并删除，且无法恢复。"
          confirmLabel="确认删除简历"
          pending={removeResume.isPending}
          error={
            removeResume.isError
              ? errorDetail(removeResume.error, "删除失败，请稍后重试。")
              : undefined
          }
          onCancel={() => !removeResume.isPending && setDeleteTarget(null)}
          onConfirm={() => removeResume.mutate(deleteTarget.id)}
        />
      )}
    </Shell>
  );
}

function Settings() {
  const { data, refetch } = useQuery({
      queryKey: ["model-settings"],
      queryFn: () => settings.model().then((r) => r.data),
      retry: false,
    }),
    [key, setKey] = useState(""),
    [base, setBase] = useState(""),
    [chat, setChat] = useState(""),
    [provider, setProvider] = useState("custom"),
    [showNewKey, setShowNewKey] = useState(false);
  const workspaceQuery = useQuery({
    queryKey: ["workspace"],
    queryFn: () => workspace.current().then((response) => response.data),
    retry: false,
  });
  const clearWorkspace = useMutation({
    mutationFn: () => workspace.clear(),
    onSuccess: () => {
      localStorage.removeItem("jobpilot_token");
      window.location.assign("/");
    },
  });
  const save = useMutation({
    mutationFn: () =>
      settings.updateModel(
        {
          api_key: key || undefined,
          base_url: base || undefined,
          chat_model: chat || data!.chat_model,
        },
      ),
    onSuccess: () => {
      setKey("");
      refetch();
    },
  });
  useEffect(() => {
    if (!data) return;
    setBase(data.base_url ?? "");
    setChat(data.chat_model);
    setProvider(inferProvider(data.base_url, data.chat_model));
  }, [data]);
  const chooseProvider = (value: string) => {
    setProvider(value);
    const preset = MODEL_PROVIDERS[value];
    if (preset && value !== "custom") {
      setBase(preset.base);
      setChat(preset.model);
    }
  };
  return (
    <Shell>
      <Title kicker="YOUR WORKSPACE / LLM SETTINGS">
        把你的模型，
        <br />
        <em>接入工作台。</em>
      </Title>
      <section className="settings-layout">
        <article className="settings-card">
          <div className="settings-status">
            <span className={data?.api_key_configured ? "online" : "offline"} />
            <div>
              <b>
                {data?.api_key_configured
                  ? "模型连接已配置"
                  : "尚未配置 API Key"}
              </b>
              <small>
                {data?.api_key_hint
                  ? `当前密钥 ${data.api_key_hint}，已加密保存`
                  : "密钥加密保存在你的工作区，只显示末四位。"}
              </small>
            </div>
          </div>
          <label>
            模型供应商
            <select
              value={provider}
              onChange={(e) => chooseProvider(e.target.value)}
            >
              <option value="openai">OpenAI</option>
              <option value="deepseek">DeepSeek</option>
              <option value="zhipu">智谱 AI</option>
              <option value="qwen">阿里云通义千问</option>
              <option value="moonshot">Moonshot / Kimi</option>
              <option value="custom">其他 OpenAI 兼容服务</option>
            </select>
          </label>
          <label>
            API Key
            <span className="secret-input">
              <input
                type={showNewKey ? "text" : "password"}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={
                  data?.api_key_configured
                    ? `${data.api_key_hint ?? "已配置"}；留空则保持不变`
                    : "sk- 或供应商密钥"
                }
              />
              <button type="button" onClick={() => setShowNewKey((value) => !value)}>
                {showNewKey ? "隐藏" : "显示"}
              </button>
            </span>
          </label>
          <label>
            兼容 API Base URL
            <input
              value={base}
              onChange={(e) => setBase(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </label>
          <label>
            对话模型
            <input
              value={chat}
              onChange={(e) => setChat(e.target.value)}
              placeholder="gpt-4o-mini"
            />
          </label>
          <button
            className="primary-button"
            disabled={!data || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "正在保存…" : "保存并应用"} <I n="arrow" s={16} />
          </button>
          {save.isError && (
            <p className="settings-error">保存失败，请确认后端正在运行。</p>
          )}
        </article>
        <aside className="settings-help">
          <p className="eyebrow">QUICK GUIDE</p>
          <h3>
            支持 OpenAI
            <br />
            兼容供应商。
          </h3>
          <p>
            选择供应商后会自动填充 Base URL 与推荐对话模型。这里控制 JD 解析、岗位建议和简历优化。
            岗位知识与向量检索由系统维护，不需要你额外配置。
          </p>
          <div>
            <b>提示</b>{" "}
            对话模型配置会同步给后台 Agent 任务；嵌入模型与知识库仍由开发者管理。
          </div>
          <div className="workspace-identity">
            <p className="eyebrow">PRIVATE WORKSPACE</p>
            <b>
              {workspaceQuery.data?.mode === "anonymous"
                ? `匿名工作区 ${workspaceQuery.data.workspace_code}`
                : "本机私有工作区"}
            </b>
            <small>
              {workspaceQuery.data?.mode === "anonymous"
                ? "资料只属于当前浏览器；其他电脑和浏览器无法查看。"
                : "当前为本地 Docker 模式，数据仅保存在这台电脑。"}
            </small>
            {workspaceQuery.data?.mode === "anonymous" && (
              <button
                type="button"
                className="workspace-reset-button"
                disabled={clearWorkspace.isPending}
                onClick={() => {
                  if (window.confirm("清空当前工作区的简历、分析和模型设置？此操作无法撤销。")) {
                    clearWorkspace.mutate();
                  }
                }}
              >
                {clearWorkspace.isPending ? "正在清空…" : "清空当前工作区"}
              </button>
            )}
          </div>
        </aside>
      </section>
    </Shell>
  );
}

function DeveloperConsole() {
  const client = useQueryClient();
  const [keyInput, setKeyInput] = useState("");
  const [adminKey, setAdminKey] = useState(
    () => sessionStorage.getItem("jobpilot_developer_key") ?? "",
  );
  const [selectedId, setSelectedId] = useState("");
  const [searchText, setSearchText] = useState("");
  const status = useQuery({
    queryKey: ["developer-status", adminKey],
    queryFn: () => developer.status(adminKey).then((response) => response.data),
    enabled: Boolean(adminKey),
    retry: false,
  });
  const { data: bases = [] } = useQuery({
    queryKey: ["developer-bases", adminKey],
    queryFn: () => developer.bases(adminKey).then((response) => response.data),
    enabled: Boolean(adminKey),
    retry: false,
  });
  const observability = useQuery({
    queryKey: ["developer-observability", adminKey],
    queryFn: () => developer.observability(adminKey).then((response) => response.data),
    enabled: Boolean(adminKey),
    retry: false,
    refetchInterval: 5000,
  });
  const { data: evaluationRuns = [] } = useQuery({
    queryKey: ["developer-evaluations", adminKey],
    queryFn: () => developer.evaluations(adminKey).then((response) => response.data),
    enabled: Boolean(adminKey),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.some((run) => ["queued", "running"].includes(run.status))
        ? 2000
        : false,
  });
  const insights = useQuery({
    queryKey: ["developer-insights", selectedId, adminKey],
    queryFn: () =>
      developer
        .insights(selectedId, adminKey)
        .then((response) => response.data),
    enabled: Boolean(adminKey && selectedId),
  });
  useEffect(() => {
    if (!selectedId && bases[0]) setSelectedId(bases[0].id);
  }, [bases, selectedId]);
  const [manifest, setManifest] = useState<File | null>(null);
  const [documents, setDocuments] = useState<File[]>([]);
  const importer = useMutation({
    mutationFn: () => developer.import(manifest!, documents, adminKey),
    onSuccess: () => {
      setManifest(null);
      setDocuments([]);
      client.invalidateQueries({ queryKey: ["developer-bases"] });
    },
  });
  const publisher = useMutation({
    mutationFn: (id: string) => developer.publish(id, adminKey),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["developer-bases"] }),
  });
  const evaluator = useMutation({
    mutationFn: () => developer.runEvaluation(adminKey),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["developer-evaluations"] });
      client.invalidateQueries({ queryKey: ["developer-observability"] });
    },
  });
  const search = useMutation({
    mutationFn: () => developer.search(selectedId, searchText, adminKey).then((response) => response.data),
  });
  if (!adminKey || status.isError) {
    return (
      <Shell>
        <section className="developer-unlock">
          <p className="eyebrow">DEVELOPER ACCESS ONLY</p>
          <h1>知识库管理台</h1>
          <p>
            此区域不向产品用户开放。输入服务端 <code>KNOWLEDGE_ADMIN_KEY</code>{" "}
            后解锁。
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              sessionStorage.setItem("jobpilot_developer_key", keyInput);
              setAdminKey(keyInput);
            }}
          >
            <input
              type="password"
              value={keyInput}
              onChange={(event) => setKeyInput(event.target.value)}
              placeholder="KNOWLEDGE_ADMIN_KEY"
              autoFocus
            />
            <button className="primary-button" disabled={!keyInput}>
              解锁管理台 <I n="arrow" s={16} />
            </button>
          </form>
          {status.isError && (
            <small className="settings-error">
              密钥无效，或服务端尚未配置 KNOWLEDGE_ADMIN_KEY。
            </small>
          )}
        </section>
      </Shell>
    );
  }
  return (
    <Shell>
      <Title kicker="KNOWLEDGE CENTER / ADMIN">
        让 Agent 的判断，
        <br />
        <em>有清晰的知识来处。</em>
      </Title>
      <section className="developer-status-grid">
        <article>
          <span>DATABASE</span>
          <b>{status.data?.database ?? "连接中"}</b>
          <small>
            {status.data?.vector_database
              ? "PostgreSQL + pgvector 已启用"
              : "SQLite 开发回退模式；启动 Docker 后使用 pgvector"}
          </small>
        </article>
        <article>
          <span>EMBEDDING</span>
          <b>{status.data?.embedding_model ?? "—"}</b>
          <small>
            {status.data?.embedding_configured
              ? "模型密钥已配置，可建立向量索引"
              : "未配置模型密钥，资料将只保留文本切片"}
          </small>
        </article>
        <article>
          <span>KNOWLEDGE PACKS</span>
          <b>{bases.length}</b>
          <small>已导入的版本；只有已发布版本参与评分</small>
        </article>
        <article>
          <span>AGENT RUNTIME</span>
          <b>{status.data?.queue_configured ? "Queue" : "Inline"}</b>
          <small>{status.data?.queue_configured ? "Redis Worker 异步执行" : "本地开发同步执行"}</small>
        </article>
      </section>
      <section className="observability-panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">AGENT OBSERVABILITY</p>
            <h3>运行健康与模型消耗</h3>
          </div>
          <span>最近 200 次运行 · 不记录简历正文</span>
        </div>
        <div className="observability-metrics">
          <p><span>成功率</span><b>{((observability.data?.success_rate ?? 0) * 100).toFixed(1)}%</b></p>
          <p><span>平均耗时</span><b>{observability.data?.average_duration_ms ?? 0} ms</b></p>
          <p><span>模型调用</span><b>{observability.data?.model_calls ?? 0}</b></p>
          <p><span>Token</span><b>{(observability.data?.input_tokens ?? 0) + (observability.data?.output_tokens ?? 0)}</b></p>
          <p><span>预估成本</span><b>${(observability.data?.estimated_cost_usd ?? 0).toFixed(4)}</b></p>
          <p><span>失败 / 待复核</span><b>{observability.data?.failed_runs ?? 0} / {observability.data?.needs_review_runs ?? 0}</b></p>
        </div>
        {!!Object.keys(observability.data?.average_node_duration_ms ?? {}).length && (
          <div className="node-duration-list">
            {Object.entries(observability.data?.average_node_duration_ms ?? {}).map(([node, duration]) => (
              <span key={node}><b>{node}</b><i>{duration} ms</i></span>
            ))}
          </div>
        )}
      </section>
      <section className="evaluation-panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">REGRESSION EVALUATION</p>
            <h3>Agent 质量回归</h3>
          </div>
          <button
            className="primary-button"
            disabled={evaluator.isPending || evaluationRuns.some((run) => ["queued", "running"].includes(run.status))}
            onClick={() => evaluator.mutate()}
          >
            {evaluator.isPending ? "正在提交…" : "运行完整评测"} <I n="arrow" s={15} />
          </button>
        </div>
        {evaluationRuns.length ? (
          <div className="evaluation-history">
            {evaluationRuns.slice(0, 5).map((run) => (
              <article key={run.id}>
                <span className={"evaluation-status " + run.status}>{run.status}</span>
                <div>
                  <b>Dataset {run.dataset_version}</b>
                  <small>{new Date(run.created_at).toLocaleString("zh-CN")}</small>
                </div>
                <strong>{run.metrics?.passed_cases ?? 0}/{run.metrics?.total_cases ?? 0}</strong>
                <small>{run.status === "completed" ? `证据 ${((run.metrics?.evidence_validity ?? 0) * 100).toFixed(0)}% · 对抗 ${((run.metrics?.metamorphic_pass_rate ?? 0) * 100).toFixed(0)}%` : run.error_code ?? "评测执行中"}</small>
              </article>
            ))}
          </div>
        ) : (
          <div className="archive-empty"><p>还没有评测记录。运行一次完整回归，建立质量基线。</p></div>
        )}
      </section>
      <div className="developer-actions">
        <NavLink to="/settings">
          <I n="spark" s={15} /> 配置对话模型与供应商
        </NavLink>
      </div>
      <section className="knowledge-intro">
        <div>
          <p className="eyebrow">AI PRODUCT MANAGER / VERSIONED</p>
          <h2>岗位能力包决定评分，参考资料只提供检索上下文。</h2>
        </div>
        <span>草稿不会影响任何正式分析</span>
      </section>
      <section className="knowledge-grid">
        <form
          className="knowledge-import"
          onSubmit={(event) => {
            event.preventDefault();
            if (manifest) importer.mutate();
          }}
        >
          <p className="eyebrow">IMPORT A KNOWLEDGE PACKAGE</p>
          <h3>导入能力模型</h3>
          <p>
            JSON/YAML 负责技能词典、权重和硬门槛；参考资料只作为语义检索补充。
          </p>
          <label className="knowledge-file">
            <input
              type="file"
              accept=".json,.yaml,.yml"
              onChange={(event) => setManifest(event.target.files?.[0] ?? null)}
            />
            <I n="file" s={17} />
            <span>{manifest?.name ?? "选择 JSON 或 YAML 能力包"}</span>
          </label>
          <label className="knowledge-file secondary">
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.md,.markdown,.txt"
              onChange={(event) =>
                setDocuments(Array.from(event.target.files ?? []))
              }
            />
            <I n="upload" s={17} />
            <span>
              {documents.length
                ? `已选择 ${documents.length} 份参考资料`
                : "可选：添加参考资料"}
            </span>
          </label>
          <button
            className="primary-button"
            disabled={!manifest || importer.isPending}
          >
            {importer.isPending ? "正在校验并导入…" : "导入为草稿"}{" "}
            <I n="arrow" s={16} />
          </button>
          {importer.isError && (
            <small className="settings-error">
              导入失败：请确认权重总和为 100、技能名称和规则引用一致。
            </small>
          )}
        </form>
        <aside className="knowledge-guide">
          <p className="eyebrow">STARTER PACKAGE</p>
          <h3>
            AI 产品经理
            <br />
            能力模型 v1 / v2
          </h3>
          <p>
            项目包含基础示例与带来源追溯的 v2 草稿，路径为{" "}
            <code>backend/app/seed/ai-product-manager-v2.json</code>
            。导入后请先审核来源与规则，再发布。
          </p>
          <div>
            <b>硬门槛</b>
            <span>产品策略 · LLM / RAG 技术理解</span>
          </div>
        </aside>
      </section>
      <section className="knowledge-list">
        <div className="panel-title">
          <div>
            <p className="eyebrow">KNOWLEDGE VERSIONS</p>
            <h3>能力包版本</h3>
          </div>
          <span>{bases.length} 个版本</span>
        </div>
        {bases.length ? (
          bases.map((base: KnowledgeBase) => (
            <article
              key={base.id}
              className={
                "knowledge-row " + (base.id === selectedId ? "selected" : "")
              }
              onClick={() => setSelectedId(base.id)}
            >
              <span className={"knowledge-status " + base.status}>
                {base.status === "published"
                  ? "已发布"
                  : base.status === "draft"
                    ? "草稿"
                    : "已归档"}
              </span>
              <div>
                <b>{base.name}</b>
                <small>
                  {base.role_key} · v{base.version} · {base.embedding_model}
                </small>
              </div>
              <span>
                {new Date(base.created_at).toLocaleDateString("zh-CN")}
              </span>
              {base.status !== "published" && (
                <button
                  onClick={() => publisher.mutate(base.id)}
                  disabled={publisher.isPending}
                >
                  发布
                </button>
              )}
            </article>
          ))
        ) : (
          <div className="archive-empty">
            <I n="archive" s={25} />
            <p>还没有知识包。先导入示例能力模型。</p>
          </div>
        )}
      </section>
      {selectedId && (
        <section className="developer-insights">
          <div className="panel-title">
            <div>
              <p className="eyebrow">VECTOR INDEX INSPECTOR</p>
              <h3>检索与切片状态</h3>
            </div>
            <span>{insights.isLoading ? "读取中…" : "开发者视图"}</span>
          </div>
          <div className="insight-metrics">
            <span>
              <b>{insights.data?.documents ?? 0}</b>参考资料
            </span>
            <span>
              <b>{insights.data?.chunks ?? 0}</b>文本切片
            </span>
            <span>
              <b>{insights.data?.vectors ?? 0}</b>已写入向量
            </span>
            <span>
              <b>{insights.data?.dimension ?? "—"}</b>向量维度
            </span>
          </div>
          <form
            className="developer-search"
            onSubmit={(event) => {
              event.preventDefault();
              if (searchText.trim()) search.mutate();
            }}
          >
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="输入例如：RAG、向量数据库、产品策略"
            />
            <button disabled={!searchText.trim() || search.isPending}>
              测试检索
            </button>
          </form>
          {search.data && (
            <div className="search-results">
              <p className="eyebrow">
                {search.data.mode.toUpperCase()} RESULTS
              </p>
              {search.data.results.length ? (
                search.data.results.map((result) => (
                  <article key={result.id}>
                    <span>Score {result.score}</span>
                    <p>{result.content}</p>
                    <small>
                      {result.vector_indexed
                        ? `向量 ${result.semantic_score}`
                        : `关键词命中 ${result.keyword_hits}`}
                    </small>
                  </article>
                ))
              ) : (
                <p>没有命中切片。请先导入参考资料，或调整检索词。</p>
              )}
            </div>
          )}
          <div className="chunk-samples">
            <p className="eyebrow">STORED CHUNKS</p>
            {insights.data?.sample_chunks.length ? (
              insights.data.sample_chunks.map((chunk) => (
                <article key={chunk.id}>
                  <i className={chunk.vector_indexed ? "indexed" : ""} />
                  <p>{chunk.content}</p>
                  <small>
                    {chunk.vector_indexed ? "已建立向量" : "仅文本切片"}
                  </small>
                </article>
              ))
            ) : (
              <p>该知识包尚未附加参考资料；技能与规则仍可用于确定性评分。</p>
            )}
          </div>
        </section>
      )}
    </Shell>
  );
}

function New() {
  const go = useNavigate(),
    [searchParams] = useSearchParams(),
    c = useQueryClient(),
    { data: list = [] } = useQuery({
      queryKey: ["resumes"],
      queryFn: () => resumes.all().then((r) => r.data),
    }),
    { data: roleProfiles = [] } = useQuery({
      queryKey: ["role-profiles"],
      queryFn: () => knowledge.profiles().then((r) => r.data),
    }),
    [resumeId, setResumeId] = useState(""),
    [roleProfileId, setRoleProfileId] = useState("auto"),
    [jd, setJd] = useState(""),
    [batch, setBatch] = useState<BatchUploadResult | null>(null);
  useEffect(() => {
    const requestedResume = searchParams.get("resume");
    if (requestedResume && list.some((resume) => resume.id === requestedResume)) {
      setResumeId(requestedResume);
    }
  }, [list, searchParams]);
  const up = useMutation({
      mutationFn: (f: File[]) => resumes.uploadBatch(f),
      onSuccess: (r) => {
        setBatch(r.data);
        c.invalidateQueries({ queryKey: ["resumes"] });
        if (r.data.imported[0]) setResumeId(r.data.imported[0].id);
      },
    }),
    create = useMutation({
      mutationFn: () =>
        analyses.create(
          resumeId,
          jd,
          roleProfileId === "auto" ? undefined : roleProfileId,
        ),
      onSuccess: (r) => go("/analysis/" + r.data.id),
    }),
    valid = !!resumeId && jd.trim().length >= 30;
  return (
    <Shell>
      <div className="workspace-head">
        <NavLink to="/resumes" className="back-link">
          ← 返回简历库
        </NavLink>
        <span>
          匹配工作台 <i>草稿自动保存</i>
        </span>
      </div>
      <section className="composer-head">
        <p className="eyebrow">NEW MATCH / 01</p>
        <h1>
          把目标岗位，<em>放到桌面上。</em>
        </h1>
        <p>一次只做一件事：让 Agent 比较一份真实简历与一个真实机会。</p>
      </section>
      <section className="match-composer">
        <div className="composer-side">
          <div className="step-chip active">
            <b>01</b>
            <span>
              资料
              <br />
              选择
            </span>
          </div>
          <i />
          <div className={"step-chip " + (resumeId ? "active" : "")}>
            <b>02</b>
            <span>
              岗位
              <br />
              描述
            </span>
          </div>
          <i />
          <div className={"step-chip " + (valid ? "active" : "")}>
            <b>03</b>
            <span>
              开始
              <br />
              分析
            </span>
          </div>
        </div>
        <div className="composer-main">
          <section className="source-block">
            <div className="block-heading">
              <span>01</span>
              <div>
                <p className="eyebrow">YOUR MATERIAL</p>
                <h2>选择一份简历</h2>
              </div>
              <small>PDF / DOCX，单次最多 10 份</small>
            </div>
            <label className="source-drop">
              <input
                type="file"
                multiple
                accept=".pdf,.docx"
                onChange={(e) =>
                  e.target.files && up.mutate(Array.from(e.target.files))
                }
              />
              <span className="upload-icon">
                <I n="upload" />
              </span>
              <b>{up.isPending ? "正在逐份读取…" : "导入简历资料"}</b>
              <small>拖入文件，或点击浏览</small>
            </label>
            {batch && (
              <div className="batch-note">
                <b>
                  <I n="check" s={15} /> 已导入 {batch.imported.length} 份资料
                </b>
                {batch.rejected.map((x) => (
                  <small key={x.file_name}>
                    未读取 {x.file_name}：{x.reason}
                  </small>
                ))}
              </div>
            )}
            <div className="resume-strip">
              {list.length ? (
                list.map((r: Resume) => (
                  <button
                    key={r.id}
                    className={
                      "resume-card " + (resumeId === r.id ? "selected" : "")
                    }
                    onClick={() => setResumeId(r.id)}
                  >
                    <I n="file" s={17} />
                    <span>{r.original_name}</span>
                    {resumeId === r.id && <I n="check" s={14} />}
                  </button>
                ))
              ) : (
                <p>导入的简历会出现在这里。</p>
              )}
            </div>
          </section>
          <section className="jd-block">
            <div className="block-heading">
              <span>02</span>
              <div>
                <p className="eyebrow">TARGET ROLE</p>
                <h2>描述目标岗位</h2>
              </div>
              <small>{jd.length} / 至少 30 个字符</small>
            </div>
            <textarea
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              placeholder={
                "粘贴岗位 JD\n\n可以包含：岗位职责、任职要求、技能偏好与团队背景。"
              }
            />
            <div className="role-profile-strip">
              <div>
                <p className="eyebrow">SCORING BASIS</p>
                <b>选择岗位评分模型</b>
                <small>
                  自动识别未命中专业模型时，会仅按当前 JD 建立通用评分项。
                </small>
              </div>
              <label>
                <span>评分模式</span>
                <select
                  value={roleProfileId}
                  onChange={(event) => setRoleProfileId(event.target.value)}
                >
                  <option value="auto">智能识别岗位（推荐）</option>
                  {roleProfiles.map((profile: RoleProfile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name} · 专业模型
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>
          <footer className="composer-footer">
            <div>
              <span className="privacy-dot" />{" "}
              你的资料只用于本次分析，不会出现在其他工作区。
            </div>
            <button
              className="primary-button"
              disabled={!valid || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? "正在建立证据…" : "开始匹配"}{" "}
              <I n="arrow" s={16} />
            </button>
          </footer>
          {create.isError && (
            <p className="composer-error" role="alert">
              {errorDetail(
                create.error,
                "分析任务未能创建，请检查模型设置与后台服务后重试。",
              )}
            </p>
          )}
        </div>
      </section>
      <section className="method-strip agent-method-strip">
        <p>Agent 评分</p>
        <span>
          <b>01</b> 知识标准化
        </span>
        <span>
          <b>02</b> 证据检索
        </span>
        <span>
          <b>03</b> 硬门槛
        </span>
        <span>
          <b>04</b> 固定权重
        </span>
        <small>总分只由岗位规则和可回链的简历证据决定。</small>
      </section>
    </Shell>
  );
}
function ReportView({ r }: { r: Report }) {
  const jdTitle = cleanReportLabel(r.jd_profile?.title) || "岗位需求解析";
  const requiredSkills = cleanReportList(r.jd_profile?.required_skills);
  const preferredSkills = cleanReportList(r.jd_profile?.preferred_skills);
  const visibleEvidence = r.evidence.filter(isUsefulEvidence).map(plainReportText);
  const visibleRequirements = (r.requirements ?? []).map((requirement) => ({
    ...requirement,
    name: cleanReportLabel(requirement.name) || "未命名要求",
    jd_targets: cleanReportList(requirement.jd_targets),
    evidence: requirement.evidence.filter((item) => isUsefulEvidence(item.quote)),
  }));
  return (
    <>
      <section className="report-hero">
        <div>
          <p className="eyebrow">MATCH REPORT / EVIDENCE BASED</p>
          <h2>
            {r.total >= 70
              ? "这个机会，值得认真投递。"
              : "这个机会，先补齐关键信号。"}
          </h2>
          <p>{plainReportText(r.summary)}</p>
        </div>
        <div className="report-score">
          <span>总匹配度</span>
          <strong>{r.total}</strong>
          <small>/ 100</small>
          <i>信心 {r.confidence ?? "—"}%</i>
        </div>
      </section>
      {r.scoring_basis && (
        <section className="scoring-basis-panel">
          <div className="basis-mark">
            <I n="check" s={17} />
          </div>
          <div>
            <p className="eyebrow">SCORING MODEL</p>
            <h3>{cleanReportLabel(r.scoring_basis.role_name) || "当前岗位 JD"}</h3>
            <p>{plainReportText(r.scoring_basis.description)}</p>
          </div>
          <span className={r.scoring_basis.reliability}>
            {r.scoring_basis.reliability === "specialist"
              ? "专业岗位模型"
              : "JD 自适应模型"}
          </span>
        </section>
      )}
      <section className="metric-list">
        {Object.entries(r.dimensions).map(([name, value], i) => (
          <article key={name}>
            <span>0{i + 1}</span>
            <b>{cleanReportLabel(name) || "综合能力"}</b>
            <strong>{value}</strong>
            <div>
              <i style={{ width: value + "%" }} />
            </div>
            <small>权重 {r.weights?.[name] ?? "—"}%</small>
          </article>
        ))}
      </section>
      {r.notice && (
        <div className="agent-notice">
          <I n="spark" s={15} />
          {plainReportText(r.notice)}
        </div>
      )}
      {r.jd_profile && (
        <section className="jd-profile-panel">
          <div>
            <p className="eyebrow">JD UNDERSTANDING</p>
            <h3>{jdTitle}</h3>
            <small>
              {r.jd_profile.experience_years != null
                ? `${r.jd_profile.experience_years} 年经验 · `
                : ""}
              {r.jd_profile.education || "学历不限或未明确"}
            </small>
          </div>
          <div className="jd-skill-groups">
            <p>
              <span>必需能力</span>
              {requiredSkills.length
                ? requiredSkills.join(" · ")
                : "JD 未明确列出"}
            </p>
            <p>
              <span>优先能力</span>
              {preferredSkills.length
                ? preferredSkills.join(" · ")
                : "JD 未明确列出"}
            </p>
          </div>
        </section>
      )}
      {r.fact_summary && (
        <section className="fact-summary-panel">
          <div>
            <p className="eyebrow">RESUME FACTS / TRACEABLE</p>
            <h3>Agent 从简历中确认的事实</h3>
            <small>只有能够定位到原文的事实才会进入评分。</small>
          </div>
          <div className="fact-summary-grid">
            <p><span>经验年限</span><b>{r.fact_summary.experience_years != null ? `${r.fact_summary.experience_years} 年` : "未明确"}</b></p>
            <p><span>学历</span><b>{cleanReportList(r.fact_summary.education).join(" · ") || "未识别"}</b></p>
            <p><span>岗位角色</span><b>{cleanReportList(r.fact_summary.roles).join(" · ") || "未识别"}</b></p>
            <p><span>量化成果</span><b>{r.fact_summary.quantified_outcomes.length} 条</b></p>
          </div>
        </section>
      )}
      {r.hard_gates && (
        <section
          className={
            "hard-gate-panel " + (r.hard_gates.passed ? "passed" : "blocked")
          }
        >
          <div>
            <p className="eyebrow">HARD GATES</p>
            <h3>
              {r.hard_gates.passed
                ? "核心门槛已具备证据"
                : "存在需要优先补齐的硬门槛"}
            </h3>
          </div>
          <p>
            {r.hard_gates.passed
              ? "未触发评分封顶。"
              : `缺失：${cleanReportList(r.hard_gates.missing).join("、")}；总分上限为 ${r.hard_gates.cap}。`}
          </p>
        </section>
      )}
      {r.requirements && (
        <section className="requirement-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">REQUIREMENT MAP</p>
              <h3>每一项分数的来处</h3>
            </div>
            <span>仅引用简历原始材料</span>
          </div>
          {visibleRequirements.map((requirement, index) => (
            <article key={`${requirement.name}-${index}`}>
              <span className={"requirement-status " + requirement.status}>
                {requirement.status === "matched"
                  ? "已匹配"
                  : requirement.status === "partial"
                    ? "部分匹配"
                    : "未匹配"}
              </span>
              <div>
                <b>{requirement.name}</b>
                <small>
                  权重 {requirement.weight}%{" "}
                  {requirement.required ? "· 硬门槛" : ""}
                </small>
                {!!requirement.jd_targets?.length && (
                  <small>JD 对应：{requirement.jd_targets.join("、")}</small>
                )}
                {requirement.evidence[0] && (
                  <p>“{plainReportText(requirement.evidence[0].quote)}”</p>
                )}
              </div>
            </article>
          ))}
        </section>
      )}
      <section className="report-grid">
        <article className="proof-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">PROOF TRAIL</p>
              <h3>简历中的证据</h3>
            </div>
            <span>仅引用原始材料</span>
          </div>
          {visibleEvidence.map((x, i) => (
            <blockquote key={i}>
              <b>0{i + 1}</b>
              <p>{x}</p>
            </blockquote>
          ))}
        </article>
        <article className="signal-panel">
          <p className="eyebrow">NEXT MOVE</p>
          <h3>
            优先补齐
            <br />
            <em>这些信号。</em>
          </h3>
          <div className="keyword-group">
            <span>待补齐</span>
            <div>
              {cleanReportList(r.missing_keywords).map((x) => (
                <i key={x}>{x}</i>
              ))}
            </div>
          </div>
          <div className="keyword-group matched">
            <span>已命中</span>
            <div>
              {cleanReportList(r.matched_keywords).map((x) => (
                <i key={x}>{x}</i>
              ))}
            </div>
          </div>
        </article>
      </section>
      {r.agent_trace && (
        <section className="agent-trace">
          <p className="eyebrow">AGENT TRACE</p>
          <h3>Agent 如何得出结论</h3>
          <div>
            {r.agent_trace.map((step, index) => (
              <span key={step.state + index}>
                <b>0{index + 1}</b>
                <strong>{step.state}</strong>
                <small>{plainReportText(step.detail)}</small>
              </span>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
function Result() {
  const { id = "" } = useParams(),
    queryClient = useQueryClient(),
    { data } = useQuery({
      queryKey: ["analysis", id],
      queryFn: () => analyses.one(id).then((r) => r.data),
      refetchInterval: (q) => {
        const terminal = ["completed", "needs_review", "failed"];
        return terminal.includes(q.state.data?.status ?? "") ? false : 2000;
      },
    });
  const { data: resume } = useQuery({
    queryKey: ["resume", data?.resume_id],
    queryFn: () => resumes.one(data!.resume_id).then((response) => response.data),
    enabled: Boolean(data?.resume_id),
  });
  const { data: sourceFile } = useQuery({
    queryKey: ["resume-file", data?.resume_id],
    queryFn: () => resumes.file(data!.resume_id).then((response) => response.data),
    enabled: Boolean(data?.resume_id && resume?.file_type === "pdf"),
  });
  const [previewUrl, setPreviewUrl] = useState("");
  const [optimized, setOptimized] = useState<OptimizationDraft | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!sourceFile) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(sourceFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sourceFile]);
  const retry = useMutation({
    mutationFn: () => analyses.retry(id).then((response) => response.data),
    onSuccess: (analysis) => {
      queryClient.setQueryData(["analysis", id], analysis);
      queryClient.invalidateQueries({ queryKey: ["analysis", id] });
    },
  });
  const optimize = useMutation({
    mutationFn: () =>
      resumes
        .createOptimization(data!.resume_id, id)
        .then((response) => response.data),
    onSuccess: setOptimized,
  });
  const decide = useMutation({
    mutationFn: ({
      changeId,
      decision,
    }: {
      changeId: string;
      decision: "accepted" | "rejected";
    }) =>
      optimizations
        .decide(optimized!.id, changeId, decision)
        .then((response) => response.data),
    onSuccess: setOptimized,
  });
  const publish = useMutation({
    mutationFn: () => optimizations.publish(optimized!.id),
    onSuccess: (response) =>
      setOptimized((current) =>
        current
          ? {
              ...current,
              status: "published",
              optimized_markdown: response.data.markdown,
            }
          : current,
      ),
  });
  const isDone =
    (data?.status === "completed" || data?.status === "needs_review") &&
    Boolean(data.report);
  const allChangesDecided =
    optimized?.changes.every((change) => change.decision !== "pending") ?? false;
  const printPdf = (target: "report" | "resume") => {
    document.body.classList.remove("print-report", "print-optimized");
    document.body.classList.add(target === "resume" ? "print-optimized" : "print-report");
    window.print();
    window.setTimeout(
      () => document.body.classList.remove("print-report", "print-optimized"),
      400,
    );
  };
  const copyOptimized = async () => {
    if (!optimized) return;
    await navigator.clipboard.writeText(optimized.optimized_markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  return (
    <Shell>
      {!isDone ? (
        <div className={"processing " + (data?.status === "failed" ? "failed" : "")}>
          <div className="process-orbit">
            <I n="spark" s={26} />
          </div>
          <p className="eyebrow">
            {data?.status === "failed" ? "ANALYSIS INTERRUPTED" : "AGENT IS READING"}
          </p>
          <h1>
            {data?.status === "failed" ? "这次分析" : "正在建立"}
            <br />
            <em>{data?.status === "failed" ? "没有完成。" : "证据轨迹。"}</em>
          </h1>
          <span>
            {data?.status === "failed"
              ? (data.error_message ?? "分析失败")
              : "这通常只需要片刻，请不要关闭页面。"}
          </span>
          {data?.status === "failed" && (
            <div className="retry-block">
              <button
                className="primary-button"
                onClick={() => retry.mutate()}
                disabled={retry.isPending}
              >
                <span>{retry.isPending ? "正在重新提交…" : "重新尝试"}</span>
                <I n="arrow" s={16} />
              </button>
              {retry.isError && (
                <small>
                  {errorDetail(retry.error, "任务仍未能提交，请检查后台 Worker。")}
                </small>
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="workspace-head">
            <NavLink to="/history" className="back-link">
              ← 返回分析档案
            </NavLink>
            <span>
              分析已完成 <i>证据报告</i>
            </span>
          </div>
          <Title kicker="ANALYSIS COMPLETE / EVIDENCE REPORT">
            答案不止是一个分数，
            <br />
            <em>还有它的来处。</em>
          </Title>
          <div className="analysis-toolbar">
            <div>
              <span className="live-dot" /> 已完成确定性评分
              <small>分数只来自岗位规则与可定位证据</small>
            </div>
            <button type="button" onClick={() => printPdf("report")}>
              导出分析 PDF
            </button>
          </div>
          <section className="analysis-workbench">
            <aside className="document-preview-panel">
              <header>
                <div>
                  <p className="eyebrow">SOURCE RESUME</p>
                  <b>{resume?.original_name ?? "正在读取源简历…"}</b>
                </div>
                <span>{resume?.file_type?.toUpperCase() ?? "FILE"}</span>
              </header>
              {resume?.file_type === "pdf" && previewUrl ? (
                <iframe src={previewUrl} title={`${resume.original_name} 预览`} />
              ) : (
                <pre>{resume?.content ?? "正在提取文档内容…"}</pre>
              )}
            </aside>
            <div className="analysis-report-column">
              <ReportView r={data!.report!} />
              <section className="targeted-optimizer">
                <header>
                  <div>
                    <p className="eyebrow">JD-TARGETED OPTIMIZATION</p>
                    <h2>针对这个岗位，重排已有证据。</h2>
                    <p>
                      只突出简历中真实存在且与当前 JD 相关的经历；缺失能力不会被补写成“已具备”。
                    </p>
                  </div>
                  {!optimized && (
                    <button
                      className="primary-button"
                      onClick={() => optimize.mutate()}
                      disabled={optimize.isPending}
                    >
                      <span>{optimize.isPending ? "正在对照 JD…" : "生成定向草稿"}</span>
                      <I n="spark" s={15} />
                    </button>
                  )}
                </header>
                {optimize.isError && (
                  <div className="inline-error" role="alert">
                    {errorDetail(
                      optimize.error,
                      "定向优化失败，请检查模型配置后重新尝试。",
                    )}
                  </div>
                )}
                {optimized && (
                  <div className="targeted-result">
                    <div className="optimizer-summary">
                      <span>{optimized.status === "published" ? "版本已发布" : "待你确认"}</span>
                      <div>
                        <h3>{optimized.headline}</h3>
                        <p>{optimized.summary}</p>
                      </div>
                    </div>
                    <div className="targeted-changes">
                      {optimized.changes.map((change, index) => (
                        <article key={change.id} className={change.decision}>
                          <span>0{index + 1}</span>
                          <div>
                            <h4>{change.title}</h4>
                            <p>{change.rationale}</p>
                            <blockquote>原文证据：“{change.evidence_quote}”</blockquote>
                            <div className="rewrite-pair">
                              <div className="rewrite-card before">
                                <span>优化前</span>
                                <del>{change.original_text}</del>
                              </div>
                              <div className="rewrite-card after">
                                <span>优化后 · 针对当前 JD</span>
                                <ins>{change.suggested_text}</ins>
                              </div>
                            </div>
                            <div className="change-actions">
                              <button
                                disabled={decide.isPending || optimized.status === "published"}
                                onClick={() =>
                                  decide.mutate({ changeId: change.id!, decision: "accepted" })
                                }
                              >
                                {change.decision === "accepted" ? "✓ 已接受" : "接受修改"}
                              </button>
                              <button
                                disabled={decide.isPending || optimized.status === "published"}
                                onClick={() =>
                                  decide.mutate({ changeId: change.id!, decision: "rejected" })
                                }
                              >
                                {change.decision === "rejected" ? "已保留原文" : "保留原文"}
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                    <div className="optimizer-publish">
                      <button type="button" onClick={copyOptimized}>
                        {copied ? "已复制" : "复制 Markdown"}
                      </button>
                      <button
                        type="button"
                        onClick={() => printPdf("resume")}
                        disabled={!optimized.optimized_markdown}
                      >
                        导出优化简历 PDF
                      </button>
                      <button
                        className="primary-button"
                        disabled={
                          !allChangesDecided ||
                          publish.isPending ||
                          optimized.status === "published"
                        }
                        onClick={() => publish.mutate()}
                      >
                        {optimized.status === "published"
                          ? "新版本已发布"
                          : publish.isPending
                            ? "正在发布…"
                            : "确认并发布新版本"}
                      </button>
                    </div>
                    {(publish.isError || decide.isError) && (
                      <div className="inline-error">
                        请先接受或拒绝每一项修改，再发布新版本。
                      </div>
                    )}
                  </div>
                )}
              </section>
            </div>
          </section>
          {optimized && (
            <section className="optimized-print-sheet">
              <header>
                <span>JOBPILOT / JD-TARGETED RESUME</span>
                <h1>{optimized.headline}</h1>
              </header>
              <pre>{optimized.optimized_markdown}</pre>
            </section>
          )}
        </>
      )}
    </Shell>
  );
}
function History() {
  const client = useQueryClient();
  const { data: list = [] } = useQuery({
    queryKey: ["history"],
    queryFn: () => analyses.all().then((r) => r.data),
  });
  const [deleteTarget, setDeleteTarget] = useState<Analysis | null>(null);
  const removeAnalysis = useMutation({
    mutationFn: (id: string) => analyses.remove(id),
    onSuccess: () => {
      setDeleteTarget(null);
      client.invalidateQueries({ queryKey: ["history"] });
      client.invalidateQueries({ queryKey: ["analyses"] });
    },
  });
  return (
    <Shell>
      <Title kicker="ANALYSIS ARCHIVE / PRIVATE">
        每一次判断，
        <br />
        <em>都值得回看。</em>
      </Title>
      <section className="archive-head">
        <span>{list.length} 份分析记录</span>
        <NavLink to="/new" className="small-action">
          新建匹配 <I n="plus" s={15} />
        </NavLink>
      </section>
      <section className="archive-list">
        {list.length ? (
          list.map((x) => <Task key={x.id} x={x} onDelete={setDeleteTarget} />)
        ) : (
          <div className="archive-empty">
            <I n="archive" s={25} />
            <p>你的分析档案还是空的。</p>
            <NavLink to="/new">开始第一份匹配 →</NavLink>
          </div>
        )}
      </section>
      {deleteTarget && (
        <ConfirmDialog
          title="删除这份分析档案？"
          description="评分报告、证据引用和 Agent 执行轨迹会被删除；原始简历仍会保留。"
          confirmLabel="确认删除分析"
          pending={removeAnalysis.isPending}
          error={
            removeAnalysis.isError
              ? errorDetail(removeAnalysis.error, "删除失败，请稍后重试。")
              : undefined
          }
          onCancel={() => !removeAnalysis.isPending && setDeleteTarget(null)}
          onConfirm={() => removeAnalysis.mutate(deleteTarget.id)}
        />
      )}
    </Shell>
  );
}
function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/resumes" element={<ResumeLibrary />} />
      <Route path="/new" element={<New />} />
      <Route path="/history" element={<History />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/developer" element={<DeveloperConsole />} />
      <Route path="/analysis/:id" element={<Result />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={qc}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </QueryClientProvider>,
);
