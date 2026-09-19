// Typed client for the FastAPI backend (see backend/main.py).

export type RiskLevel = "high" | "medium" | "low";
export type RingStatus = "pending" | "confirmed" | "dismissed";
export type Decision = "confirm" | "dismiss" | "reset";

export interface JobStage {
  key: string;
  label: string;
  weight: number;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  message: string;
  started_at?: string;
  finished_at?: string;
}

export interface Job {
  id: string;
  dataset_id: string | null;
  kind: "synthetic" | "analyze" | "retrain";
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage: string | null;
  message: string | null;
  stages: JobStage[];
  error: string | null;
  result: { dataset_id: string; version: number; mode: string } | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface DatasetSummary {
  n_customers: number;
  n_links: number;
  n_edges: number;
  n_events: number;
  attribute_types: string[];
  has_labels: boolean;
  n_labeled: number;
  n_fraud_labels: number;
  label_mode: "train" | "evaluate" | null;
  mode: "supervised" | "transfer";
  tabular_features: string[];
  warnings: string[];
}

export interface FeedbackSummary {
  n_labels: number;
  fraud: number;
  legit: number;
  n_reviews: number;
  reviews_since_model: number;
  labels_in_model: number;
  retrain_recommended: boolean;
}

export interface DatasetListItem {
  id: string;
  name: string;
  source: "synthetic" | "upload";
  created_at: string;
  status: "processing" | "ready" | "failed";
  error: string | null;
  active_version: number;
  summary: DatasetSummary | null;
  active_job: Job | null;
}

export interface DatasetDetail extends DatasetListItem {
  mapping: Record<string, unknown> | null;
  model: { version: number; mode: string; threshold: number; created_at: string; n_feedback: number } | null;
  feedback: FeedbackSummary;
}

export interface CustomerBrief {
  customer_id: string;
  name: string;
  risk: number;
  risk_level: RiskLevel;
  rank: number;
  ring_id: string | null;
  degree: number;
  high_neighbors: number;
  top_reason: string;
  label: number | null;
  analyst_label: number | null;
}

export interface RingTruth {
  n_labeled: number;
  n_fraud: number;
  dominant_truth_ring: string | null;
  dominant_count: number;
}

export interface RingBrief {
  ring_id: string;
  size: number;
  n_edges: number;
  density: number;
  score: number;
  max_risk: number;
  n_high: number;
  suspected: boolean;
  shared_types: Record<string, number>;
  explanation: string;
  truth: RingTruth | null;
  open_span_days: number | null;
  status: RingStatus;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface Attribute {
  type: string;
  key: string;
  value: string;
  shared_with: number;
  ignored: boolean;
}

export interface RingMember extends CustomerBrief {
  suggested: boolean;
  open_date: string | null;
  attributes: Attribute[];
}

export interface GraphNode {
  id: string;
  name: string;
  risk: number;
  level: RiskLevel;
  ring_id: string | null;
  label: number | null;
  analyst_label: number | null;
  degree: number;
  hop?: number;
  member?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  types: string[];
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  center?: string;
  truncated?: boolean;
  rings?: Record<string, { suspected: boolean; score: number; status: RingStatus }>;
  n_rings_total?: number;
  n_rings_shown?: number;
}

export interface Evidence {
  attribute_type: string;
  value: string;
  members: number;
}

export interface ReviewHistoryItem {
  id: number;
  decision: Decision;
  note: string;
  created_at: string;
  included: string[];
  model_version: number;
}

export interface RingDetail extends RingBrief {
  evidence: Evidence[];
  members: RingMember[];
  graph: GraphData;
  threshold: number;
  history: ReviewHistoryItem[];
  included: string[] | null;
  previous_ring: string | null;
  next_ring: string | null;
}

export interface Reason {
  feature: string;
  label: string;
  value: number;
  direction: "up" | "down";
  impact: number;
  text: string;
}

export interface Contribution {
  feature: string;
  label: string;
  group: string;
  value: number;
  impact: number;
}

export interface Explanation {
  summary: string;
  score: number;
  baseline_score: number;
  reasons: Reason[];
  mitigating: Reason[];
  context: string[];
  top_reason: string;
  contributions: Contribution[];
}

export interface Connection {
  customer_id: string;
  name: string;
  risk: number;
  risk_level: RiskLevel;
  ring_id: string | null;
  label: number | null;
  analyst_label: number | null;
  types: string[];
  shared: { type: string; value: string }[];
}

export interface EventRow {
  event_date: string;
  event_type: string;
  credit_limit: number | null;
  utilization: number | null;
}

export interface CustomerDetail {
  customer_id: string;
  name: string;
  risk: number;
  risk_level: RiskLevel;
  rank: number;
  n_customers: number;
  threshold: number;
  mode: string;
  label: number | null;
  truth_ring: string | null;
  open_date: string | null;
  analyst_label: number | null;
  degree: number;
  high_neighbors: number;
  features: Record<string, number>;
  feature_labels: Record<string, string>;
  explanation: Explanation;
  attributes: Attribute[];
  connections: Connection[];
  ring: RingBrief | null;
  events: EventRow[];
  reviews: {
    id: number;
    target_type: "ring" | "customer";
    target_id: string;
    decision: Decision;
    note: string;
    created_at: string;
    included: boolean;
  }[];
}

export interface Evaluation {
  n: number;
  n_positive: number;
  threshold: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
  pr_auc: number | null;
  tn: number;
  fp: number;
  fn: number;
  tp: number;
  at_k: { k: number; precision: number; recall: number }[];
  roc_curve: [number, number][];
  pr_curve: [number, number][];
  scope: string;
  previous_version?: {
    version: number;
    roc_auc: number | null;
    pr_auc: number | null;
    precision: number;
    recall: number;
    f1: number;
  } | null;
}

export interface Experiment {
  model: string;
  experiment: string;
  n_features: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface HistogramBin {
  start: number;
  end: number;
  count: number;
  fraud?: number;
  legit?: number;
}

export interface RingDetection {
  n_candidates: number;
  n_suspected: number;
  truth: {
    precision: number | null;
    member_recall: number | null;
    n_fraud_customers: number;
    ring_recall: number | null;
    n_true_rings: number | null;
  } | null;
}

export interface GraphStats {
  n_nodes: number;
  n_edges: number;
  edges_by_type: Record<string, number>;
  linked_customers: number;
  hub_values_skipped: { attribute_type: string; value: string; customers: number }[];
  label_mix: { legit_legit: number; fraud_fraud: number; mixed: number } | null;
}

export interface Changes {
  previous_version: number;
  level_changes: number;
  newly_high: number;
  no_longer_high: number;
  mean_abs_score_change: number;
  rings_newly_suspected: number;
  rings_cleared: number;
}

export interface ReferenceInfo {
  source: string;
  n_train: number;
  features: string[];
  attribute_types: string[];
  reference_roc_auc: number;
}

export interface CurrentMetrics {
  mode: "supervised" | "transfer";
  model: string;
  features: string[];
  feature_labels: Record<string, string>;
  threshold: number;
  evaluation: Evaluation | null;
  experiments: Experiment[];
  experiment_split: { n_train: number; n_test: number; n_train_positive: number; n_test_positive: number } | null;
  feature_importance: { feature: string; label: string; group: string; importance: number }[];
  group_importance: { group: string; importance: number }[];
  risk_histogram: HistogramBin[];
  level_counts: Record<RiskLevel, number>;
  ring_detection: RingDetection;
  graph: GraphStats;
  reference: ReferenceInfo | null;
  notes: string[];
  feedback: { n_labels: number; fraud: number; legit: number };
  changes: Changes | null;
}

export interface VersionSummary {
  version: number;
  created_at: string;
  mode: string;
  threshold: number;
  n_feedback: number;
  feedback: { n_labels: number; fraud: number; legit: number } | null;
  roc_auc: number | null;
  pr_auc: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  level_counts: Record<RiskLevel, number> | null;
  n_suspected_rings: number | null;
  changes: Changes | null;
  evaluation_scope: string | null;
  previous_same_customers: {
    version: number;
    roc_auc: number | null;
    pr_auc: number | null;
    precision: number;
    recall: number;
    f1: number;
  } | null;
}

export interface MetricsResponse {
  version: number;
  mode: string;
  current: CurrentMetrics;
  history: VersionSummary[];
}

export interface Overview {
  dataset: { id: string; name: string; source: string; summary: DatasetSummary };
  model: {
    version: number;
    mode: "supervised" | "transfer";
    threshold: number;
    created_at: string;
    roc_auc: number | null;
    pr_auc: number | null;
    precision: number | null;
    recall: number | null;
    evaluation_scope: string | null;
    reference: ReferenceInfo | null;
  };
  level_counts: Record<RiskLevel, number>;
  risk_histogram: HistogramBin[];
  ring_detection: RingDetection;
  graph: GraphStats;
  group_importance: { group: string; importance: number }[];
  notes: string[];
  review_progress: { suspected: number; reviewed: number; confirmed: number; dismissed: number };
  top_rings: RingBrief[];
  top_customers: CustomerBrief[];
  feedback: FeedbackSummary;
  changes: Changes | null;
}

export interface ColumnProfile {
  name: string;
  n_unique: number;
  n_empty: number;
  examples: string[];
  numeric_share: number;
}

export interface FilePreview {
  filename: string;
  n_rows: number;
  columns: ColumnProfile[];
  sample_rows: Record<string, string>[];
  suggested_roles?: Record<string, string>;
  suggested_fields?: Record<string, string | null>;
}

export interface UploadResponse {
  upload_id: string;
  files: Partial<Record<"customers" | "links" | "events", FilePreview>>;
}

export interface SampleFile {
  name: string;
  bytes: number;
  description: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running (python -m backend)?");
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg: string }) => item.msg).join("; ");
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

const enc = encodeURIComponent;

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  datasets: () => request<DatasetListItem[]>("/api/datasets"),
  dataset: (id: string) => request<DatasetDetail>(`/api/datasets/${enc(id)}`),
  deleteDataset: (id: string) => request<void>(`/api/datasets/${enc(id)}`, { method: "DELETE" }),
  createSynthetic: (body: { name?: string; seed: number; n_legitimate: number; n_fraud: number }) =>
    request<{ dataset_id: string; job_id: string }>("/api/datasets/synthetic", json("POST", body)),
  upload: (files: { customers: File; links?: File | null; events?: File | null }) => {
    const form = new FormData();
    form.append("customers", files.customers);
    if (files.links) form.append("links", files.links);
    if (files.events) form.append("events", files.events);
    return request<UploadResponse>("/api/uploads", { method: "POST", body: form });
  },
  createDataset: (body: { upload_id: string; name: string; mapping: unknown }) =>
    request<{ dataset_id: string; job_id: string }>("/api/datasets", json("POST", body)),
  retrain: (id: string) => request<{ dataset_id: string; job_id: string }>(`/api/datasets/${enc(id)}/retrain`, { method: "POST" }),
  jobs: (datasetId?: string) => request<Job[]>(`/api/jobs${query({ dataset_id: datasetId, limit: 30 })}`),
  job: (id: string) => request<Job>(`/api/jobs/${enc(id)}`),
  overview: (id: string) => request<Overview>(`/api/datasets/${enc(id)}/overview`),
  metrics: (id: string) => request<MetricsResponse>(`/api/datasets/${enc(id)}/metrics`),
  customers: (
    id: string,
    params: { q?: string; level?: string; ring?: string; reviewed?: string; sort?: string; order?: string; limit?: number; offset?: number },
  ) => request<{ total: number; items: CustomerBrief[] }>(`/api/datasets/${enc(id)}/customers${query(params)}`),
  customer: (id: string, customerId: string) =>
    request<CustomerDetail>(`/api/datasets/${enc(id)}/customers/${enc(customerId)}`),
  customerGraph: (id: string, customerId: string, hops = 2) =>
    request<GraphData>(`/api/datasets/${enc(id)}/customers/${enc(customerId)}/graph${query({ hops })}`),
  reviewCustomer: (id: string, customerId: string, body: { decision: Decision; note?: string }) =>
    request<{ analyst_label: number | null; feedback: FeedbackSummary }>(
      `/api/datasets/${enc(id)}/customers/${enc(customerId)}/review`,
      json("POST", body),
    ),
  rings: (id: string, params: { status?: string; scope?: string; q?: string; limit?: number; offset?: number }) =>
    request<{ total: number; counts: Record<"all" | RingStatus, number>; items: RingBrief[] }>(
      `/api/datasets/${enc(id)}/rings${query(params)}`,
    ),
  ring: (id: string, ringId: string) => request<RingDetail>(`/api/datasets/${enc(id)}/rings/${enc(ringId)}`),
  reviewRing: (id: string, ringId: string, body: { decision: Decision; note?: string; include?: string[] }) =>
    request<{ ring_id: string; status: RingStatus; included: string[]; feedback: FeedbackSummary }>(
      `/api/datasets/${enc(id)}/rings/${enc(ringId)}/review`,
      json("POST", body),
    ),
  network: (id: string, params: { scope?: string; min_score?: number; types?: string; status?: string; max_nodes?: number }) =>
    request<GraphData>(`/api/datasets/${enc(id)}/graph${query(params)}`),
  samples: () => request<SampleFile[]>("/api/sample-data"),
};

export const exportUrl = (id: string) => `/api/datasets/${enc(id)}/export/customers.csv`;
export const sampleUrl = (name: string) => `/api/sample-data/${enc(name)}`;
export const jobStreamUrl = (jobId: string) => `/api/jobs/${enc(jobId)}/stream`;
