import { apiClient, unwrap } from './client'
import type {
  AuditLogRow,
  Company,
  CompanyOverview,
  DashboardSummary,
  IngestResult,
  Opportunity,
  PageData,
  RadarSummary,
  RadarSummaryData,
  Signal,
  Source,
  SourceRecord,
} from '../types'

type ListParams = Record<string, string | number | undefined>

async function getList<T>(path: string, params: ListParams = {}): Promise<PageData<T>> {
  const res = await apiClient.get(path, { params })
  return unwrap<PageData<T>>(res.data)
}

// system
export { getSystemInfo } from './system'

// dashboard
export async function getDashboard() {
  const res = await apiClient.get('/dashboard')
  return unwrap<DashboardSummary>(res.data)
}

export async function getRadarSummary() {
  const res = await apiClient.get('/radar/summary')
  return unwrap<RadarSummary>(res.data)
}

// opportunity radar（UI02）：筛选参数直接作用到后端 SQL
export async function getRadarOverview(params: ListParams = {}) {
  const res = await apiClient.get('/radar/summary', { params })
  return unwrap<RadarSummaryData>(res.data)
}

// companies
export function getCompanies(params: ListParams = {}) {
  return getList<Company>('/companies', params)
}

export async function getCompany(id: string) {
  const res = await apiClient.get(`/companies/${id}`)
  return unwrap<Company>(res.data)
}

export async function getCompanyOverview(id: string) {
  const res = await apiClient.get(`/companies/${id}/overview`)
  return unwrap<CompanyOverview>(res.data)
}

// signals
export function getSignals(params: ListParams = {}) {
  return getList<Signal>('/signals', params)
}

export async function getSignal(id: string) {
  const res = await apiClient.get(`/signals/${id}`)
  return unwrap<Signal>(res.data)
}

export type SignalCreateInput = {
  company_id: string
  signal_type: string
  title: string
  description?: string
  confidence?: number
  fact_or_inference?: 'FACT' | 'INFERENCE'
  source_record_id?: string
  evidence_url?: string
  evidence_title?: string
}

export async function createSignal(input: SignalCreateInput) {
  const res = await apiClient.post('/signals', input)
  return unwrap<Signal>(res.data)
}

// opportunities
export function getOpportunities(params: ListParams = {}) {
  return getList<Opportunity>('/opportunities', params)
}

export async function getOpportunity(id: string) {
  const res = await apiClient.get(`/opportunities/${id}`)
  return unwrap<Opportunity>(res.data)
}

export type OpportunityCreateInput = {
  company_id: string
  primary_signal_id?: string | null
  title: string
  problem: string
  solution: string
  value_proposition?: string
  trigger_event?: string
  pain_score?: number
  budget_score?: number
  intent_score?: number
  urgency_score?: number
  agent_fit_score?: number
  reachability_score?: number
  evidence_score?: number
}

export async function createOpportunity(input: OpportunityCreateInput) {
  const res = await apiClient.post('/opportunities', input)
  return unwrap<Opportunity>(res.data)
}

export type ReviewInput = { action: 'approve' | 'reject' | 'edit' | 'ready'; note?: string; updates?: Record<string, string | number> }

export async function reviewOpportunity(id: string, input: ReviewInput) {
  const res = await apiClient.post(`/opportunities/${id}/review`, input)
  return unwrap<Opportunity>(res.data)
}

export async function updateOpportunityStage(id: string, stage: string) {
  const res = await apiClient.patch(`/opportunities/${id}/stage`, { stage })
  return unwrap<Opportunity>(res.data)
}

// sources & records
export function getSources(params: ListParams = {}) {
  return getList<Source>('/sources', params)
}

export function getSourceRecords(params: ListParams = {}) {
  return getList<SourceRecord>('/source-records', params)
}

export async function getSourceRecord(id: string) {
  const res = await apiClient.get(`/source-records/${id}`)
  return unwrap<SourceRecord>(res.data)
}

// ingest
export async function ingestUrl(url: string, note = '') {
  const res = await apiClient.post('/ingest/url', { url, note })
  return unwrap<IngestResult>(res.data)
}

// collection（T03）
export async function runSource(id: string) {
  const res = await apiClient.post(`/sources/${id}/run`)
  return unwrap<{ job_id: string; status: string; items_found: number; items_created: number; items_updated: number; items_skipped: number; error_count: number }>(res.data)
}

export type CollectionJobRow = {
  id: string; name: string; job_type: string; status: string; items_found: number;
  items_created: number; items_updated: number; items_skipped: number; error_count: number;
  duration_seconds: number | null; created_at: string; finished_at: string | null;
  run_log?: { url: string; status: string; latency_ms?: number; error?: string }[];
}

export async function getJobs(params: ListParams = {}) {
  return getList<CollectionJobRow>('/jobs', params)
}

// audit logs
export function getAuditLogs(params: ListParams = {}) {
  return getList<AuditLogRow>('/logs/audit', params)
}
