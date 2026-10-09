// ---------------------------------------------------------------------------
// T06 商业验证与客户反馈系统
// ---------------------------------------------------------------------------

export const EXPERIMENT_STATUS_LABELS: Record<string, string> = {
  DRAFT: '草稿', READY: '就绪', RUNNING: '进行中', PAUSED: '已暂停', COMPLETED: '已完成', CANCELLED: '已取消',
}

export const EXPERIMENT_CONCLUSION_LABELS: Record<string, string> = {
  KEEP: '继续推进', TEST_MORE: '继续验证', PAUSE: '暂停', DROP: '放弃',
}

export const TARGET_STATUS_LABELS: Record<string, string> = {
  NEW: '新加入', RESEARCHING: '研究中', READY_TO_CONTACT: '准备联系', CONTACTED: '已联系',
  REPLIED: '已回复', QUALIFIED: '已确认意向', MEETING: '已会议', QUOTED: '已报价',
  PILOT: '已试点', WON: '已成交', REJECTED: '已拒绝', NO_RESPONSE: '无回复', PAUSED: '已暂停',
}

export const TARGET_FLOW_STATUSES = ['NEW', 'RESEARCHING', 'READY_TO_CONTACT', 'CONTACTED', 'REPLIED', 'QUALIFIED', 'MEETING', 'QUOTED', 'PILOT', 'WON']

export const INTERACTION_TYPE_LABELS: Record<string, string> = {
  RESEARCH: '研究笔记', OUTREACH: '首次触达', FOLLOW_UP: '跟进', REPLY: '客户回复', MEETING: '会议',
  DEMO: '演示', PROPOSAL: '方案', QUOTE: '报价', NEGOTIATION: '谈判', PILOT: '试点',
  CONTRACT: '签约', PAYMENT: '收款', REJECTION: '客户拒绝', NOTE: '备注',
}

export const INTERACTION_CHANNEL_LABELS: Record<string, string> = {
  EMAIL: '邮件', PHONE: '电话', WECHAT: '微信', LINKEDIN: 'LinkedIn', FACEBOOK: 'Facebook',
  WHATSAPP: 'WhatsApp', WEBSITE_FORM: '官网表单', OFFLINE: '线下', MEETING: '会议', OTHER: '其他',
}

export const INTERACTION_DIRECTION_LABELS: Record<string, string> = {
  OUTBOUND: '我方发出', INBOUND: '客户来讯', INTERNAL: '内部记录',
}

export const REPLY_CATEGORY_LABELS: Record<string, string> = {
  POSITIVE: '积极', NEUTRAL: '中性', NEGATIVE: '消极', NEED_MORE_INFO: '需要更多信息', NOT_NOW: '时机不合适',
  WRONG_PERSON: '找错人', NO_NEED: '无需求', PRICE_CONCERN: '价格顾虑', ALREADY_HAVE_SOLUTION: '已有解决方案',
}

export const EXPERIMENT_REJECT_REASON_LABELS: Record<string, string> = {
  NO_NEED: '无需求', NO_BUDGET: '无预算', WRONG_PERSON: '接触对象不对', BAD_TIMING: '时机不对',
  PRICE_HIGH: '价格过高', ALREADY_HAVE_SOLUTION: '已有解决方案', NO_TRUST: '信任不足',
  PRODUCT_NOT_FIT: '产品不匹配', NOT_REACHABLE: '无法触达', NO_RESPONSE: '无回复',
  WEAK_VALUE_PROPOSITION: '价值主张不足', OTHER: '其他',
}

export const CONTACT_VERIFICATION_LABELS: Record<string, string> = {
  VERIFIED_PUBLIC: '公开信息已核实', USER_PROVIDED: '用户人工录入', UNVERIFIED: '未核实', STALE: '已过期', INVALID: '无效',
}

export const QUOTE_STATUS_LABELS: Record<string, string> = {
  DRAFT: '草稿', SENT: '已发送', VIEWED: '已查看', ACCEPTED: '已接受', REJECTED: '已拒绝', EXPIRED: '已过期', WITHDRAWN: '已撤回',
}

export const OBSERVED_INTENT_LABELS: Record<string, string> = {
  REPLIED: '回复了沟通', MEETING_BOOKED: '预约了会议', QUOTE_REQUESTED: '索要报价',
  PILOT_STARTED: '开始试点', NO_RESPONSE: '无回复', DECLINED: '明确拒绝',
}

export type Experiment = {
  id: string
  name: string
  description: string | null
  market_id: string | null
  hypothesis: string
  target_customer: string | null
  value_proposition: string | null
  offer_name: string | null
  offer_description: string | null
  pricing_hypothesis: string | null
  price_amount: number | null
  price_currency: string | null
  price_type: string | null
  start_at: string | null
  end_at: string | null
  target_company_count: number
  target_contacts: number
  target_replies: number
  target_meetings: number
  target_quotes: number
  target_pilots: number
  target_wins: number
  success_criteria: string | null
  failure_criteria: string | null
  status: string
  conclusion: string | null
  conclusion_notes: string | null
  started_at: string | null
  ended_at: string | null
  created_at: string
  updated_at: string
  metrics?: ExperimentMetricsData
  funnel?: FunnelData
  interaction_stats?: InteractionStats
}

export type ExperimentMetricsData = {
  targets: number
  researching: number
  contacted: number
  replied: number
  meetings: number
  quotes: number
  pilots: number
  wins: number
  rejected: number
  no_response: number
  contact_rate: number
  reply_rate: number
  meeting_rate: number
  quote_rate: number
  pilot_rate: number
  close_rate: number
  overall_close_rate: number
  contracted_revenue: number
  received_revenue: number
}

export type FunnelData = {
  targets: number; researching: number; ready_to_contact: number; contacted: number
  replied: number; qualified: number; meetings: number; quotes: number
  pilots: number; wins: number; rejected: number; no_response: number; paused: number
}

export type InteractionStats = { interactions_total: number; interactions_outbound: number; interactions_inbound: number; interactions_replies: number }

export type ExperimentTarget = {
  id: string
  experiment_id: string
  company_id: string
  company_name: string | null
  opportunity_id: string | null
  opportunity_title: string | null
  opportunity_score: number | null
  opportunity_grade: string | null
  priority: number
  status: string
  reached_stage: string
  assigned_to: string | null
  added_at: string | null
  last_interaction_at: string | null
  next_action_at: string | null
  next_action: string | null
  notes: string | null
}

export type Interaction = {
  id: string
  company_id: string
  company_name?: string | null
  opportunity_id: string | null
  experiment_id: string | null
  target_id: string | null
  contact_id: string | null
  interaction_type: string | null
  direction: string | null
  channel: string
  occurred_at: string | null
  subject: string | null
  summary: string | null
  result: string | null
  sentiment: string | null
  next_action: string | null
  next_action_at: string | null
  created_by: string | null
  evidence_attachment: string | null
  contact_name: string | null
  quote_amount: number | null
  deal: boolean
  revenue: number | null
  reject_reason: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type CompanyContact = {
  id: string
  company_id: string
  name: string | null
  title: string | null
  department: string | null
  public_contact: string | null
  email: string | null
  phone: string | null
  public_profile_url: string | null
  source_url: string | null
  source_type: string | null
  source_record_id: string | null
  verification_status: string
  is_decision_maker: boolean
  confidence: number
  verified_public: boolean
  created_at: string
  updated_at: string
}

export type Quote = {
  id: string
  experiment_id: string | null
  company_id: string
  company_name?: string | null
  opportunity_id: string | null
  target_id: string | null
  amount: number
  currency: string
  billing_type: string | null
  scope: string | null
  status: string
  sent_at: string | null
  valid_until: string | null
  response: string | null
  created_at: string
  updated_at: string
}

export type OpportunityFeedbackRow = {
  id: string
  target_id: string | null
  predicted_score: number
  predicted_grade: string | null
  actual_reply: boolean | null
  actual_meeting: boolean | null
  actual_quote: boolean | null
  actual_pilot: boolean | null
  actual_win: boolean | null
  actual_revenue: number | null
  reject_reason: string | null
  notes: string | null
  feedback_at: string | null
}