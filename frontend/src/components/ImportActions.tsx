import { useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Plus, Upload } from 'lucide-react'
import { API_ROOT, templateUrl } from '../api'
import type { ImportSummary, Scenario } from '../types'
import { Badge, Modal } from './UI'

type SheetKey = 'students' | 'teachers' | 'rooms' | 'courses'

const LABELS: Record<SheetKey, string> = {
  students: '学生',
  teachers: '教师',
  rooms: '教室',
  courses: '课程配置',
}

export default function ImportActions({
  scenarioId, sheet, onImported, onManualAdd,
}: {
  scenarioId: string
  sheet: SheetKey
  onImported: (scenario: Scenario) => void
  onManualAdd?: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<{ summary: ImportSummary; errors: string[]; ok: boolean } | null>(null)

  const upload = async (file: File) => {
    setBusy(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_ROOT}/api/scenarios/${scenarioId}/import?mode=merge&sheet=${sheet}`, {
        method: 'POST', body: form,
      })
      const body = await res.json()
      if (!res.ok) {
        setReport({ summary: body.summary || emptySummary(), errors: body.errors || [body.detail || '导入失败'], ok: false })
        return
      }
      setReport({ summary: body.summary, errors: [], ok: true })
      onImported(body.scenario)
    } catch (e) {
      setReport({ summary: emptySummary(), errors: [e instanceof Error ? e.message : String(e)], ok: false })
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <>
      <div className="data-actions">
        <a className="btn btn-sm btn-ghost" href={templateUrl(scenarioId, sheet)} target="_blank" rel="noreferrer">
          <Download size={14} />下载模板
        </a>
        <button className="btn btn-sm btn-ghost" onClick={() => input.current?.click()} disabled={busy}>
          <Upload size={14} />{busy ? '导入中…' : '导入 Excel'}
        </button>
        {onManualAdd && (
          <button className="btn btn-sm btn-primary" onClick={onManualAdd}>
            <Plus size={14} />手动新增
          </button>
        )}
        <input ref={input} type="file" accept=".xlsx,.xlsm" hidden
          onChange={e => { const f = e.target.files?.[0]; if (f) upload(f) }} />
      </div>
      <div className="data-action-note">只导入{LABELS[sheet]}表，不会覆盖其他类别数据。</div>

      <Modal open={!!report} title={report?.ok ? '导入完成' : '导入未通过'}
        subtitle={report ? `本次处理${LABELS[sheet]}数据` : ''} onClose={() => setReport(null)}
        footer={<button className="btn btn-primary" onClick={() => setReport(null)}>知道了</button>}>
        {report && (
          <div className="import-report">
            <div className={`import-report-banner ${report.ok ? 'ok' : 'bad'}`}>
              {report.ok ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
              <div>
                <strong>{report.ok ? '数据已写入当前方案' : '没有写入数据，原方案保持不变'}</strong>
                <span>{report.ok ? '旧课表会标记为待重算，请重新排课。' : '请按下面原因修正 Excel 后重试。'}</span>
              </div>
            </div>
            <div className="import-counts">
              <div><span>成功</span><strong>{report.ok ? countFor(report.summary, sheet) : 0}</strong></div>
              <div><span>失败行</span><strong>{report.summary.failed_rows || 0}</strong></div>
              <div><span>重复</span><strong>{report.summary.duplicates?.length || 0}</strong></div>
              <div><span>缺失字段 / 错误</span><strong>{report.errors.length}</strong></div>
            </div>
            {report.summary.duplicates?.length > 0 && (
              <div className="import-list"><strong>重复数据</strong>{report.summary.duplicates.map((x, i) => <p key={i}>{x}</p>)}</div>
            )}
            {report.summary.warnings?.length > 0 && (
              <div className="import-list warning"><strong>提示</strong>{report.summary.warnings.map((x, i) => <p key={i}>{x}</p>)}</div>
            )}
            {report.errors.length > 0 && (
              <div className="import-list error"><strong>失败记录及原因</strong>{report.errors.slice(0, 20).map((x, i) => <p key={i}>{x}</p>)}</div>
            )}
            {report.ok && (
              <div className="import-tip"><FileSpreadsheet size={15} /><span>成功导入 {countFor(report.summary, sheet)} 条{LABELS[sheet]}记录。若还有缺失，页面顶部的检查会继续提示。</span></div>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}

function emptySummary(): ImportSummary {
  return { students: 0, teachers: 0, rooms: 0, course_rows: 0, duplicates: [], warnings: [], failed_rows: 0 }
}

function countFor(summary: ImportSummary, sheet: SheetKey) {
  if (sheet === 'students') return summary.students
  if (sheet === 'teachers') return summary.teachers
  if (sheet === 'rooms') return summary.rooms
  return summary.course_rows
}
