import { useState } from 'react'
import { message } from 'antd'
import { Link } from 'react-router-dom'
import { Radar } from 'lucide-react'
import { Modal, FormField } from './Modal'
import { ingestUrl, getErrorMessage } from '../api'
import type { IngestResult } from '../types'

/** 手动 URL 分析入口（数据源页 / 企业库空状态共用）。 */
export function IngestModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone?: () => void }) {
  const [url, setUrl] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reset = () => { setUrl(''); setNote(''); setResult(null); setError(null) }
  const close = () => { reset(); onClose() }

  const submit = async () => {
    if (!url.trim()) { message.warning('请输入公开网页 URL'); return }
    setBusy(true); setError(null); setResult(null)
    try {
      const data = await ingestUrl(url.trim(), note.trim())
      setResult(data)
      message.success(data.duplicate ? '该内容已采集过，已复用现有记录' : '采集完成')
      onDone?.()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="分析网页" subtitle="输入真实公开网页 URL，采集后自动建立 SourceRecord → 企业 → 信号 → 证据 数据链">
      {!result ? (
        <>
          <FormField label="公开网页 URL" hint="仅支持 http/https 公网地址">
            <input className="text-input" value={url} placeholder="https://…" onChange={(e) => setUrl(e.target.value)} />
          </FormField>
          <FormField label="备注（可选）">
            <input className="text-input" value={note} placeholder="为什么采集这个页面…" onChange={(e) => setNote(e.target.value)} />
          </FormField>
          {error && <div className="form-error">{error}</div>}
          <div className="modal-actions">
            <button className="secondary-btn" onClick={close}>取消</button>
            <button className="primary-btn" disabled={busy} onClick={submit}><Radar size={15}/>{busy ? '采集中…' : '开始分析'}</button>
          </div>
        </>
      ) : (
        <>
          <div className="ingest-result">
            <div><span>SourceRecord</span><strong>已保存{result.duplicate ? '（内容去重，复用记录）' : ''}</strong></div>
            <div><span>识别企业</span><strong>{result.company_id ? '已创建/匹配' : '未能可靠识别（可人工关联）'}</strong></div>
            <div><span>商业信号</span><strong>{result.signal_ids.length} 条（规则引擎 · 事实）</strong></div>
            <div><span>AI 增强分析</span><strong className={result.llm_configured ? 'ok' : ''}>{result.llm_configured ? '已执行' : '未配置'}</strong></div>
          </div>
          <p className="form-hint">规则信号均带原始证据，可在「商业信号」与「企业详情」页查看并追溯。</p>
          <div className="modal-actions">
            {result.company_id && <Link className="secondary-btn" to={`/companies/${result.company_id}`} onClick={close}>查看企业详情</Link>}
            <button className="primary-btn" onClick={close}>完成</button>
          </div>
        </>
      )}
    </Modal>
  )
}
