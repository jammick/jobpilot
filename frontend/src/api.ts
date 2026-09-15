import axios from "axios";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  withCredentials: true,
  headers: { "X-JobPilot-Client": "web" },
});
api.interceptors.request.use((c) => {
  const t = localStorage.getItem("jobpilot_token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
export type Resume = { id: string; original_name: string; created_at: string };
export type ResumeDetail = Resume & {
  content: string;
  file_type: "pdf" | "docx";
};
export type BatchUploadResult = {
  imported: Resume[];
  rejected: { file_name: string; reason: string }[];
};
export type ResumeOptimization = {
  headline: string;
  summary: string;
  improvements: string[];
  optimized_markdown: string;
};
export type OptimizationChange = {
  id: string;
  title: string;
  original_text: string;
  suggested_text: string;
  rationale: string;
  evidence_quote: string;
  decision: "pending" | "accepted" | "rejected";
};
export type OptimizationDraft = ResumeOptimization & {
  id: string;
  status: string;
  changes: OptimizationChange[];
};
export type KnowledgeBase = {
  id: string;
  name: string;
  role_key: string;
  version: string;
  status: string;
  embedding_model: string;
  created_at: string;
  manifest?: { rules?: { name: string; weight: number; required: boolean }[] };
  document_count?: number;
  validation?: string[];
};
export type RoleProfile = {
  id: string;
  name: string;
  role_key: string;
  knowledge_base_id: string;
  version: string;
};
export type DeveloperStatus = {
  database: string;
  vector_database: boolean;
  embedding_model: string;
  embedding_configured: boolean;
  task_mode: string;
  queue_configured: boolean;
};
export type AgentObservability = {
  total_runs: number;
  success_rate: number;
  failed_runs: number;
  needs_review_runs: number;
  average_duration_ms: number;
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  average_node_duration_ms: Record<string, number>;
  recent_runs: {
    id: string;
    analysis_id: string;
    status: string;
    duration_ms?: number;
    error_code?: string;
    created_at: string;
  }[];
};
export type EvaluationRun = {
  id: string;
  status: string;
  dataset_version: string;
  metrics: {
    total_cases?: number;
    passed_cases?: number;
    score_accuracy?: number;
    status_accuracy?: number;
    evidence_validity?: number;
    deterministic_rate?: number;
    optimization_guard_accuracy?: number;
    metamorphic_pass_rate?: number;
  };
  failures: unknown[];
  error_code?: string;
  created_at: string;
};
export type KnowledgeInsights = {
  knowledge_base_id: string;
  documents: number;
  chunks: number;
  vectors: number;
  dimension: number | null;
  sample_chunks: { id: string; content: string; vector_indexed: boolean }[];
};
export type KnowledgeSearch = {
  mode: string;
  results: {
    id: string;
    content: string;
    score: number;
    keyword_hits: number;
    semantic_score: number;
    vector_indexed: boolean;
  }[];
};
export type Analysis = {
  id: string;
  resume_id: string;
  status: string;
  total_score?: number;
  error_message?: string;
  role_profile_id?: string;
  attempt_count: number;
  started_at?: string;
  finished_at?: string;
  created_at: string;
  report?: Report;
};
export type Report = {
  total: number;
  dimensions: Record<string, number>;
  weights?: Record<string, number>;
  confidence?: number;
  matched_keywords: string[];
  missing_keywords: string[];
  evidence: string[];
  summary: string;
  improvements: string[];
  interview_questions: string[];
  fact_summary?: {
    counts: Record<string, number>;
    experience_years?: number | null;
    education: string[];
    roles: string[];
    organizations: string[];
    quantified_outcomes: string[];
  };
  jd_profile?: {
    title: string;
    required_skills: string[];
    preferred_skills: string[];
    responsibilities: string[];
    experience_years?: number | null;
    education?: string | null;
    keywords: string[];
  };
  hard_gates?: { missing: string[]; cap: number; passed: boolean };
  scoring_basis?: {
    mode: "role_profile" | "jd_adaptive";
    role_name: string;
    version: string;
    engine_version?: string;
    reliability: "specialist" | "adaptive";
    description: string;
  };
  requirements?: {
    name: string;
    required: boolean;
    weight: number;
    status: string;
    evidence: { quote: string }[];
    jd_targets?: string[];
    source?: "jd+role_profile" | "role_profile" | "jd";
  }[];
  knowledge_base?: { id: string; version: string };
  agent_trace?: { state: string; detail: string }[];
  notice?: string | null;
};
export type ModelSettings = {
  base_url?: string;
  chat_model: string;
  api_key_configured: boolean;
  api_key_hint?: string;
};
export const auth = {
  register: (email: string, password: string) =>
    api.post("/auth/register", { email, password }),
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  me: () => api.get("/auth/me"),
};
export type Workspace = {
  mode: "local" | "anonymous";
  workspace_code: string;
  expires_at?: string;
};
export const workspace = {
  current: () => api.get<Workspace>("/workspace"),
  clear: () => api.delete("/workspace"),
};
export const resumes = {
  all: () => api.get<Resume[]>("/resumes"),
  one: (id: string) => api.get<ResumeDetail>(`/resumes/${id}`),
  file: (id: string) =>
    api.get<Blob>(`/resumes/${id}/file`, { responseType: "blob" }),
  upload: (file: File) => {
    const f = new FormData();
    f.append("file", file);
    return api.post<Resume>("/resumes", f);
  },
  uploadBatch: (files: File[]) => {
    const f = new FormData();
    files.forEach((file) => f.append("files", file));
    return api.post<BatchUploadResult>("/resumes/batch", f);
  },
  createOptimization: (id: string, analysis_id: string) =>
    api.post<OptimizationDraft>(`/resumes/${id}/optimizations`, {
      analysis_id,
    }),
  versions: (id: string) => api.get(`/resumes/${id}/versions`),
  remove: (id: string) => api.delete(`/resumes/${id}`),
};
export const analyses = {
  all: () => api.get<Analysis[]>("/analyses"),
  one: (id: string) => api.get<Analysis>(`/analyses/${id}`),
  create: (
    resume_id: string,
    job_description: string,
    role_profile_id?: string,
  ) =>
    api.post<Analysis>("/analyses", {
      resume_id,
      job_description,
      role_profile_id,
    }),
  retry: (id: string) => api.post<Analysis>(`/analyses/${id}/retry`),
  trace: (id: string) =>
    api.get<{ trace: { state: string; detail: string }[] }>(
      `/analyses/${id}/trace`,
    ),
  download: (id: string) =>
    api.get(`/analyses/${id}/export`, { responseType: "blob" }),
  remove: (id: string) => api.delete(`/analyses/${id}`),
};
export const settings = {
  model: () => api.get<ModelSettings>("/settings/model"),
  updateModel: (payload: {
    api_key?: string;
    base_url?: string;
    chat_model: string;
  }) => api.put<ModelSettings>("/settings/model", payload),
};
export const knowledge = {
  all: () => api.get<KnowledgeBase[]>("/knowledge-bases"),
  one: (id: string) => api.get<KnowledgeBase>(`/knowledge-bases/${id}`),
  import: (manifest: File, documents: File[]) => {
    const form = new FormData();
    form.append("manifest", manifest);
    documents.forEach((file) => form.append("documents", file));
    return api.post<KnowledgeBase>("/knowledge-bases/import", form);
  },
  publish: (id: string) =>
    api.post<KnowledgeBase>(`/knowledge-bases/${id}/publish`),
  validate: (id: string) =>
    api.post<KnowledgeBase>(`/knowledge-bases/${id}/validate`),
  profiles: () => api.get<RoleProfile[]>("/role-profiles"),
};
function developerOptions(adminKey: string) {
  return { headers: { "X-Knowledge-Admin-Key": adminKey } };
}
export const developer = {
  status: (adminKey: string) =>
    api.get<DeveloperStatus>("/developer/status", developerOptions(adminKey)),
  observability: (adminKey: string) =>
    api.get<AgentObservability>("/developer/observability", developerOptions(adminKey)),
  evaluations: (adminKey: string) =>
    api.get<EvaluationRun[]>("/developer/evaluations", developerOptions(adminKey)),
  runEvaluation: (adminKey: string) =>
    api.post<EvaluationRun>("/developer/evaluations", undefined, developerOptions(adminKey)),
  bases: (adminKey: string) =>
    api.get<KnowledgeBase[]>("/knowledge-bases", developerOptions(adminKey)),
  insights: (id: string, adminKey: string) =>
    api.get<KnowledgeInsights>(
      `/knowledge-bases/${id}/insights`,
      developerOptions(adminKey),
    ),
  search: (id: string, query: string, adminKey: string) =>
    api.post<KnowledgeSearch>(
      `/knowledge-bases/${id}/search`,
      { query },
      developerOptions(adminKey),
    ),
  import: (manifest: File, documents: File[], adminKey: string) => {
    const form = new FormData();
    form.append("manifest", manifest);
    documents.forEach((file) => form.append("documents", file));
    return api.post<KnowledgeBase>(
      "/knowledge-bases/import",
      form,
      developerOptions(adminKey),
    );
  },
  publish: (id: string, adminKey: string) =>
    api.post<KnowledgeBase>(
      `/knowledge-bases/${id}/publish`,
      undefined,
      developerOptions(adminKey),
    ),
};
export const optimizations = {
  one: (id: string) => api.get<OptimizationDraft>(`/optimizations/${id}`),
  decide: (
    draftId: string,
    changeId: string,
    decision: "accepted" | "rejected",
  ) =>
    api.post<OptimizationDraft>(
      `/optimizations/${draftId}/changes/${changeId}/decision`,
      { decision },
    ),
  publish: (id: string) => api.post(`/optimizations/${id}/publish`),
};
