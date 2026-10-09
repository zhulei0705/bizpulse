export type HealthStatus = {
  status: string
  service: string
  environment: string
}

export * from './validation'

export type SystemInfo = {
  name: string
  version: string
  environment: string
  database: string
  no_fake_data: boolean
}

// ---------------------------------------------------------------------------
// 共享业务枚举（与 backend/app/core/constants.py 保持一致）
// ---------------------------------------------------------------------------

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  HIRING: '招聘扩张',
  SALES_HIRING: '销售招聘',
  CUSTOMER_SERVICE_HIRING: '客服招聘',
  FINANCE_HIRING: '财务招聘',
  AI_HIRING: 'AI人才招聘',
  FUNDING: '融资事件',
  EXPANSION: '业务扩张',
  OVERSEAS_EXPANSION: '海外扩张',
  NEW_PRODUCT: '新产品发布',
  NEW_MARKET: '新市场进入',
  PROCUREMENT: '采购需求',
  TENDER: '招标信息',
  CRM_DEMAND: 'CRM需求',
  ERP_DEMAND: 'ERP需求',
  CUSTOMER_COMPLAINT: '客户投诉',
  COST_PRESSURE: '成本压力',
  EFFICIENCY_PROBLEM: '效率问题',
  DIGITAL_TRANSFORMATION: '数字化转型',
  AI_TRANSFORMATION: 'AI转型',
  MANUAL_WORK: '人工操作痛点',
  DATA_PROBLEM: '数据问题',
}

export const OPPORTUNITY_STAGE_LABELS: Record<string, string> = {
  NEW: '新发现',
  REVIEW: '待审核',
  READY: '准备验证',
  CONTACTED: '已联系',
  REPLIED: '已回复',
  MEETING: '已会议',
  QUOTED: '已报价',
  PILOT: '已试点',
  WON: '已成交',
  REJECTED: '已拒绝',
}

export const OPPORTUNITY_STAGES = Object.keys(OPPORTUNITY_STAGE_LABELS)

export const GRADE_LABELS: Record<string, string> = { S: 'S级', A: 'A级', B: 'B级', C: 'C级', D: 'D级' }

// 机会候选拒绝原因（与 backend OPPORTUNITY_REJECT_REASONS 一致，复盘用）
export const OPPORTUNITY_REJECT_REASONS: Record<string, string> = {
  NO_REAL_PROBLEM: '无真实问题',
  WEAK_EVIDENCE: '证据不足',
  WRONG_INTERPRETATION: '解读有误',
  LOW_VALUE: '价值过低',
  NO_BUDGET_SIGNAL: '无预算信号',
  NOT_REACHABLE: '无法触达',
  DUPLICATE: '重复机会',
  BAD_TIMING: '时机不对',
  OTHER: '其他',
}

export const SOURCE_GRADE_LABELS: Record<string, string> = {
  A: '官方/权威来源',
  B: '招聘平台/权威媒体',
  C: '社区/公开平台',
  D: '转载/待确认',
}

// ---------------------------------------------------------------------------
// 数据模型
// ---------------------------------------------------------------------------

export type PageData<T> = { items: T[]; total: number; page: number; page_size: number; stats?: Record<string, number>; counts?: Record<string, number> }

export type Company = {
  id: string
  company_name: string
  normalized_name: string
  website: string | null
  domain: string | null
  industry: string | null
  sub_industry: string | null
  country: string | null
  province: string | null
  city: string | null
  employee_range: string | null
  business_model: string | null
  main_products: string[]
  main_markets: string[]
  company_description: string | null
  pulse_score: number | null
  opportunity_level: string | null
  status: string
  source_count: number
  created_at: string
  updated_at: string
  signal_count?: number
  opportunity_count?: number
}

export type Evidence = {
  source_record_id: string
  url: string
  title: string | null
  published_at: string | null
  collected_at: string
  excerpt: string | null
  source_name: string | null
  reliability_grade: string | null
  reliability_score: number | null
  verification_status?: string
  last_verified_at?: string | null
}

export type Signal = {
  id: string
  company_id: string
  company_name?: string | null
  source_record_id: string
  signal_type: string
  title: string
  description: string | null
  published_at: string | null
  collected_at: string
  confidence: number
  reliability_score: number
  heat_score: number | null
  status: string
  fact_or_inference: 'FACT' | 'INFERENCE' | string
  payload_json: Record<string, unknown>
  evidence?: Evidence | null
}

export type PainPoint = {
  id: string
  company_id: string
  category: string
  description: string
  confidence: number
  reason: string | null
  status: string
  created_at: string
  updated_at: string
}

export type Opportunity = {
  id: string
  company_id: string
  company_name?: string | null
  primary_signal_id: string | null
  title: string
  problem: string
  solution: string
  value_proposition: string | null
  trigger_event: string | null
  purchase_intent: string | null
  pain_score: number
  budget_score: number
  intent_score: number
  urgency_score: number
  agent_fit_score: number
  reachability_score: number
  evidence_score: number
  total_score: number
  grade: string
  confidence: number
  stage: string
  status: string
  owner: string | null
  review_status: string
  reviewed_at: string | null
  review_note: string | null
  reviewed_by: string | null
  evidence_count?: number
  created_at: string
  updated_at: string
  evidences?: OpportunityEvidenceRow[]
  // T06 真实验证信息
  observed_intent?: string | null
  confirmed_budget?: string | null
  last_contacted_at?: string | null
  contact_count?: number
}

export type OpportunityEvidenceRow = {
  id: string
  source_record_id: string | null
  signal_id: string | null
  evidence_type: string
  evidence_excerpt: string | null
  weight: number
  url?: string | null
  title?: string | null
}

// ---------------------------------------------------------------------------
// T05 机会判断引擎：候选（AI 生成 → 人工审核 → 转正式机会）
// ---------------------------------------------------------------------------

export const OPPORTUNITY_CANDIDATE_STATUS_LABELS: Record<string, string> = {
  DETECTED: '已发现',
  REVIEW: '待审核',
  NEED_MORE_EVIDENCE: '证据不足',
  APPROVED: '已通过',
  CONVERTED: '已转机会',
  REJECTED: '已拒绝',
}

export type CandidateEvidenceRef = {
  signal_id: string
  source_record_id: string | null
  polarity: string
  grade: string | null
  excerpt: string
  url?: string | null
}

export type OpportunityCandidate = {
  id: string
  company_id: string
  company_name?: string | null
  bundle_id: string | null
  pain_point_id: string | null
  title: string
  problem_hypothesis: string
  solution_hypothesis: string
  value_hypothesis: string | null
  trigger_summary: string | null
  why_now: string | null
  evidence_summary: string | null
  recommended_next_action: string | null
  signal_ids: string[]
  pain_category: string | null
  pain_category_label?: string | null
  solution_category: string | null
  pain_score: number
  budget_score: number
  intent_score: number
  urgency_score: number
  agent_fit_score: number
  reachability_score: number
  evidence_score: number
  total_score: number
  grade: string
  grade_cap_reason: string | null
  confidence: number
  score_breakdown: Record<string, unknown>
  risk_notes: string[]
  validation_questions: string[]
  evidence_refs: CandidateEvidenceRef[]
  contradicting_evidence: CandidateEvidenceRef[]
  status: string
  generated_by: string | null
  prompt_version: string | null
  reject_reason: string | null
  review_note: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  opportunity_id: string | null
  created_at: string
  updated_at: string
}

export type SourceRecord = {
  id: string
  source_id: string
  company_id: string | null
  url: string
  title: string | null
  published_at: string | null
  collected_at: string
  content_hash: string
  http_status: number | null
  language: string | null
  verification_status: string
  source_reliability: string | null
  last_verified_at: string | null
  metadata_json: Record<string, unknown>
  excerpt?: string | null
  source?: { id: string; name: string; source_type: string; reliability_grade: string; reliability_score: number } | null
}

export type Source = {
  id: string
  name: string
  source_type: string
  base_url: string | null
  reliability_grade: string
  reliability_score: number
  enabled: boolean
  collector_type: string | null
  collection_frequency: string | null
  last_run_at: string | null
  success_rate: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type CompanyOverview = {
  company: Company
  signals: Signal[]
  pain_points: PainPoint[]
  opportunities: Opportunity[]
  source_records: SourceRecord[]
  counts: { signals: number; pain_points: number; opportunities: number; source_records: number }
}

export type DashboardSummary = {
  company_count: number
  signal_count: number
  opportunity_count: number
  grade_a_or_higher: number
  pending_review: number
  validating: number
  won: number
  rejected: number
  active_sources: number
  running_jobs: number
  today_new_companies: number
  today_new_signals: number
  today_new_opportunities: number
  total_records: number
  verified_records: number
  llm_configured: boolean
  signal_trend: { date: string; count: number }[]
  recent_signals: { id: string; company_id: string | null; company_name: string | null; signal_type: string; title: string; confidence: number; collected_at: string; fact_or_inference: string; verification_status: string; reliability_grade: string | null; url: string | null }[]
  companies_to_watch: { company_id: string; company_name: string; industry: string | null; latest_signal_type: string; latest_signal_title: string; opportunity_level: string | null; top_opportunity_score: number | null; evidence_count: number; signal_count: number; updated_at: string }[]
}

export type RadarSummary = { potential_opportunities: number; high_priority: number; pending_review: number }

// ---------------------------------------------------------------------------
// 机会雷达（UI02）
// ---------------------------------------------------------------------------

export type RadarMetrics = {
  today_signals: number
  today_opportunities: number
  high_value_opportunities: number
  grade_a_or_higher: number
  pending_reviews: number
  potential_opportunities: number
}

export type RadarLocation = {
  company_id: string
  company_name: string | null
  country: string | null
  province: string | null
  city: string | null
  opportunity_count: number
  top_score: number
  top_grade: string
}

export type RadarSignal = {
  id: string
  company_id: string | null
  company_name: string | null
  signal_type: string
  title: string
  confidence: number
  collected_at: string
  fact_or_inference: string
  verification_status: string
  reliability_grade: string | null
  evidence_count: number
  url: string | null
  opportunity_score?: number | null
}

export type RadarOpportunity = {
  id: string
  company_id: string
  company_name: string | null
  title: string
  problem: string
  solution: string
  value_proposition: string | null
  trigger_event: string | null
  purchase_intent: string | null
  pain_score: number
  budget_score: number
  intent_score: number
  urgency_score: number
  agent_fit_score: number
  reachability_score: number
  evidence_score: number
  total_score: number
  grade: string
  stage: string
  review_status: string
  review_note: string | null
  reviewed_at: string | null
  evidence_count: number
  latest_signal_title: string | null
  created_at: string
  updated_at: string
}

export type IndustryHeatItem = {
  industry: string
  company_count: number
  signal_count: number
  opportunity_count: number
  average_score: number
}

export type ScoreDistributionItem = { range: string; label: string; count: number }

export type SourceDistributionItem = { source_type: string; label: string; count: number }

export type GradeDistributionItem = { grade: string; count: number }

export type RadarSummaryData = {
  metrics: RadarMetrics
  locations: RadarLocation[]
  latest_signals: RadarSignal[]
  top_opportunities: RadarOpportunity[]
  score_distribution: ScoreDistributionItem[]
  source_distribution: SourceDistributionItem[]
  grade_distribution: GradeDistributionItem[]
  pending_reviews: RadarOpportunity[]
  industry_options?: string[]
}

export type RadarFilters = {
  industry?: string
  country?: string
  grade?: string
  min_score?: number
  min_evidence?: number
  min_evidence_score?: number
  signal_type?: string
  days?: number
}

export type IngestResult = {
  source_id: string
  source_record_id: string
  company_id: string | null
  signal_ids: string[]
  pain_point_ids: string[]
  opportunity_ids: string[]
  llm_configured: boolean
  duplicate: boolean
}

export type AuditLogRow = {
  id: string
  action: string
  entity_type: string | null
  entity_id: string | null
  actor: string
  payload_json: Record<string, unknown>
  created_at: string
}
