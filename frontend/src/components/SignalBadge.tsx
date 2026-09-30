import { SIGNAL_TYPE_LABELS } from '../types'

const SIGNAL_COLORS: Record<string, string> = {
  HIRING: 'blue', SALES_HIRING: 'blue', CUSTOMER_SERVICE_HIRING: 'blue', FINANCE_HIRING: 'blue', AI_HIRING: 'purple',
  FUNDING: 'green', EXPANSION: 'green', OVERSEAS_EXPANSION: 'green',
  NEW_PRODUCT: 'cyan', NEW_MARKET: 'cyan',
  PROCUREMENT: 'orange', TENDER: 'orange',
  CRM_DEMAND: 'purple', ERP_DEMAND: 'purple',
  CUSTOMER_COMPLAINT: 'danger', COST_PRESSURE: 'danger', EFFICIENCY_PROBLEM: 'danger',
  DIGITAL_TRANSFORMATION: 'purple', AI_TRANSFORMATION: 'purple',
  MANUAL_WORK: 'danger', DATA_PROBLEM: 'danger',
}

/** Signal Badge：信号类型徽章（类型分组配色 + 中文标签）。 */
export function SignalBadge({ type, small }: { type: string; small?: boolean }) {
  const tone = SIGNAL_COLORS[type] || 'blue'
  return <span className={`signal-badge tone-${tone} ${small ? 'small' : ''}`}>{SIGNAL_TYPE_LABELS[type] || type}</span>
}
