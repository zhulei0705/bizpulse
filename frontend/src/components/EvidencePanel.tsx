import { ExternalLink, Globe2 } from 'lucide-react'
import type { Evidence, SourceRecord } from '../types'
import { SourceGradeChip } from './GradeChip'
import { EmptyState } from './EmptyState'

function fmt(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

/** 验证状态标签：人工审核通过后证据被标记为已验证。 */
export function VerificationTag({ status, verifiedAt }: { status?: string; verifiedAt?: string | null }) {
  if (status === 'VERIFIED') {
    return <span className="fact-tag fact" title={verifiedAt ? `最近验证：${new Date(verifiedAt).toLocaleString('zh-CN', { hour12: false })}` : '已人工验证'}>已验证</span>
  }
  return <span className="fact-tag inference" title="尚未经过人工验证">未验证</span>
}

/** Evidence Panel：原始证据（来源/等级/标题/URL/时间/摘要/可信度/验证状态 + 查看原始来源）。
 * 通用组件：接受 Signal.evidence 或 SourceRecord 两种输入。
 */
export function EvidencePanel({ evidences, emptyHint }: { evidences: (Evidence | SourceRecord)[]; emptyHint?: string }) {
  if (!evidences.length) {
    return <EmptyState title="暂无原始证据" description={emptyHint || '所有证据都来自真实公开网页，采集后自动归档。'} />
  }
  return (
    <div className="evidence-panel">
      {evidences.map((item, idx) => {
        const grade = (item as Evidence).reliability_grade || (item as SourceRecord).source?.reliability_grade || (item as SourceRecord).source_reliability || null
        const sourceName = (item as Evidence).source_name || (item as SourceRecord).source?.name || '未知来源'
        const published = (item as Evidence).published_at ?? (item as SourceRecord).published_at
        const verification = (item as Evidence).verification_status ?? (item as SourceRecord).verification_status
        const verifiedAt = (item as Evidence).last_verified_at ?? (item as SourceRecord).last_verified_at
        return (
          <div className="evidence-card" key={(item as Evidence).source_record_id || (item as SourceRecord).id || idx}>
            <div className="evidence-head">
              <span className="evidence-source"><Globe2 size={14}/>{sourceName}</span>
              {grade && <SourceGradeChip grade={grade} />}
              <VerificationTag status={verification} verifiedAt={verifiedAt}/>
            </div>
            <strong className="evidence-title">{item.title || item.url}</strong>
            {item.excerpt && <p className="evidence-excerpt">{item.excerpt}</p>}
            <div className="evidence-meta">
              <span>发布：{fmt(published)}</span>
              <span>采集：{fmt(item.collected_at)}</span>
              {item.url && (
                <a className="evidence-link" href={item.url} target="_blank" rel="noreferrer noopener">
                  查看原始来源 <ExternalLink size={13}/>
                </a>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
