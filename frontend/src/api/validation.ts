// T06 商业验证与客户反馈系统 API
import { apiClient, unwrap } from './client'
import type {
  CompanyContact,
  Experiment,
  ExperimentTarget,
  FunnelData,
  Interaction,
  OpportunityFeedbackRow,
  PageData,
  Quote,
} from '../types'

type ListParams = Record<string, string | number | undefined>

// --- 实验生命周期 ---
export function getExperiments(params: ListParams = {}) {
  return apiClient.get('/experiments', { params }).then((r) => unwrap<PageData<Experiment>>(r.data))
}

export type ExperimentCreateInput = {
  name: string
  hypothesis: string
  description?: string
  target_customer?: string
  value_proposition?: string
  offer_description?: string
  price_amount?: number
  price_currency?: string
  price_type?: string
  target_contacts?: number
  target_replies?: number
  target_meetings?: number
  target_quotes?: number
  target_pilots?: number
  target_wins?: number
  success_criteria?: string
  failure_criteria?: string
  status?: string
}

export async function createExperiment(input: ExperimentCreateInput) {
  const res = await apiClient.post('/experiments', input)
  return unwrap<Experiment>(res.data)
}

export async function getExperiment(id: string) {
  const res = await apiClient.get(`/experiments/${id}`)
  return unwrap<Experiment>(res.data)
}

export async function startExperiment(id: string) {
  const res = await apiClient.post(`/experiments/${id}/start`)
  return unwrap<Experiment>(res.data)
}

export async function completeExperiment(id: string, conclusion: string, notes?: string) {
  const res = await apiClient.post(`/experiments/${id}/complete`, { conclusion, notes })
  return unwrap<Experiment>(res.data)
}

// --- 验证目标企业 ---
export async function getExperimentTargets(experimentId: string) {
  const res = await apiClient.get(`/experiments/${experimentId}/targets`)
  return unwrap<ExperimentTarget[]>(res.data)
}

export async function addTarget(experimentId: string, companyId: string, opportunityId?: string | null) {
  const res = await apiClient.post(`/experiments/${experimentId}/targets`, {
    company_id: companyId, opportunity_id: opportunityId || undefined,
  })
  return unwrap<ExperimentTarget>(res.data)
}

export type TargetUpdateInput = {
  status?: string
  reject_reason?: string
  contract_amount?: number
  force?: boolean
  notes?: string
  next_action?: string
  next_action_at?: string
  priority?: number
  assigned_to?: string
}

export async function updateTarget(targetId: string, input: TargetUpdateInput) {
  const res = await apiClient.patch(`/experiment-targets/${targetId}`, input)
  return unwrap<ExperimentTarget>(res.data)
}

// --- 互动 ---
export function getInteractions(params: ListParams = {}) {
  return apiClient.get('/interactions', { params }).then((r) => unwrap<PageData<Interaction>>(r.data))
}

export type InteractionCreateInput = {
  company_id: string
  experiment_id?: string | null
  target_id?: string | null
  opportunity_id?: string | null
  contact_id?: string | null
  interaction_type?: string
  direction?: string
  channel?: string
  occurred_at?: string
  subject?: string
  summary?: string
  result?: string
  next_action?: string
  next_action_at?: string
  evidence_attachment?: string
  revenue?: number
  quote_amount?: number
  reject_reason?: string
  notes?: string
}

export async function createInteraction(input: InteractionCreateInput) {
  const res = await apiClient.post('/interactions', input)
  return unwrap<Interaction>(res.data)
}

export async function updateInteraction(id: string, input: Partial<InteractionCreateInput>) {
  const res = await apiClient.patch(`/interactions/${id}`, input)
  return unwrap<Interaction>(res.data)
}

export async function confirmPain(interactionId: string, painPointId: string, note?: string) {
  const res = await apiClient.post(`/interactions/${interactionId}/confirm-pain`, { pain_point_id: painPointId, note })
  return unwrap<{ id: string; status: string; confirmed_by_interaction_id: string }>(res.data)
}

// --- 联系人 ---
export async function getCompanyContacts(companyId: string) {
  const res = await apiClient.get(`/companies/${companyId}/contacts`)
  return unwrap<CompanyContact[]>(res.data)
}

export type ContactCreateInput = {
  name?: string
  title?: string
  department?: string
  public_contact?: string
  email?: string
  phone?: string
  public_profile_url?: string
  source_url?: string
  source_type?: string
  verification_status?: string
  is_decision_maker?: boolean
  confidence?: number
}

export async function createContact(companyId: string, input: ContactCreateInput) {
  const res = await apiClient.post(`/companies/${companyId}/contacts`, input)
  return unwrap<CompanyContact>(res.data)
}

export async function updateContact(contactId: string, input: Partial<ContactCreateInput>) {
  const res = await apiClient.patch(`/contacts/${contactId}`, input)
  return unwrap<CompanyContact>(res.data)
}

// --- 报价 ---
export function getQuotes(params: ListParams = {}) {
  return apiClient.get('/quotes', { params }).then((r) => unwrap<PageData<Quote>>(r.data))
}

export type QuoteCreateInput = {
  company_id: string
  experiment_id?: string | null
  opportunity_id?: string | null
  target_id?: string | null
  amount: number
  currency?: string
  billing_type?: string
  scope?: string
  status?: string
}

export async function createQuote(input: QuoteCreateInput) {
  const res = await apiClient.post('/quotes', input)
  return unwrap<Quote>(res.data)
}

export async function updateQuote(id: string, input: { status?: string; response?: string; amount?: number }) {
  const res = await apiClient.patch(`/quotes/${id}`, input)
  return unwrap<Quote>(res.data)
}

// --- 漏斗与反馈 ---
export async function getExperimentFunnel(experimentId: string) {
  const res = await apiClient.get(`/experiments/${experimentId}/funnel`)
  return unwrap<FunnelData>(res.data)
}

export async function getOpportunityFeedback(opportunityId: string) {
  const res = await apiClient.get(`/opportunities/${opportunityId}/feedback`)
  return unwrap<OpportunityFeedbackRow[]>(res.data)
}

export async function addToExperiment(opportunityId: string, experimentId: string) {
  const res = await apiClient.post(`/opportunities/${opportunityId}/add-to-experiment`, { experiment_id: experimentId })
  return unwrap<{ experiment_id: string; opportunity_id: string; target_id: string; target_created: boolean }>(res.data)
}

export async function confirmBudget(opportunityId: string, budgetText: string, interactionId: string) {
  const res = await apiClient.post(`/opportunities/${opportunityId}/confirm-budget`, {
    budget_text: budgetText, interaction_id: interactionId,
  })
  return unwrap<{ id: string; confirmed_budget: string }>(res.data)
}
