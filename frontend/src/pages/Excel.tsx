import { useRef, useState } from 'react'
import { CheckCircle2, Download, FileSpreadsheet, Upload, TriangleAlert } from 'lucide-react'
import { useApp } from '../context'
import { API_ROOT } from '../api'
import { Badge, Card, PageHeader } from '../components/UI'
import type { ImportSummary } from '../types'

export default function Excel() {
  const { scenario, run, isStale, refreshScenario, notify } = useApp()
  const [mode, setMode] = useState('replace')
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [summary, setSummary] = useState<ImportSummary | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (!scenario) return <div className="loading-block">正在加载…</div>

  const upload = async (file: File) => {
    setBusy(true); setErrors([]); setSummary(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${API_ROOT}/api/scenarios/${scenario.id}/import?mode=${mode}`, { method: 'POST', body: form })
      const body = await res.json()
      if (!res.ok) {
        setErrors(body.errors || [body.detail || '导入失败'])
        notify('error', '导入失败，未写入数据')
      } else {
        setSummary(body.summary)
        await refreshScenario()
        notify('success', '基础数据导入成功，请重新求解')
      }
    } catch (e) {
      setErrors([e instanceof Error ? e.message : String(e)])
      notify('error', '导入失败')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <>
      <PageHeader eyebrow="数据交换" title="Excel 导入导出"
        description="整套导入导出与备份。学生、教师、教室页面已提供分项导入；本页用于整套备份/恢复。"
        actions={<Badge tone={run?.validation?.passed ? 'green' : 'neutral'}>{run ? '当前课表可导出' : '基础数据可导出'}</Badge>} />

      <div className="two-col">
        <Card title="导出" subtitle="生成带格式的 XLSX 文件"
          actions={<FileSpreadsheet size={18} className="muted" />}>
          <div className="export-actions">
            <a className="export-card" href={`${API_ROOT}/api/excel/template?sid=${scenario.id}`} target="_blank" rel="noreferrer">
              <div className="export-icon"><Download size={20} /></div>
              <div><strong>下载导入模板</strong><span>学生、教师、教室、课程配置四张表</span></div>
            </a>
            <a className="export-card" href={`${API_ROOT}/api/scenarios/${scenario.id}/export.xlsx`} target="_blank" rel="noreferrer">
              <div className="export-icon accent"><Download size={20} /></div>
              <div><strong>导出当前场景与课表</strong><span>含总览、四类课表、教学班、校验结果</span></div>
            </a>
          </div>
          <div className="form-note">
            导出文件可直接作为导入文件再次使用；导入器会识别标题行上方的说明行。
          </div>
          {isStale && run && <div className="inline-warning"><TriangleAlert size={16} /><span>基础数据已修改，当前课表为旧版本。导出文件会标注“课表是否过期”，建议先重新排课。</span></div>}
          <div className="excel-facts">
            <div><strong>{scenario.students.length}</strong><span>学生行</span></div>
            <div><strong>{scenario.teachers.length}</strong><span>教师行</span></div>
            <div><strong>{scenario.rooms.length}</strong><span>教室行</span></div>
            <div><strong>{run?.tasks.length || 0}</strong><span>课表任务</span></div>
          </div>
        </Card>

        <Card title="导入基础数据" subtitle="严格校验；错误行不会写入数据库">
          <div className="upload-zone" onClick={() => fileRef.current?.click()}>
            <Upload size={26} />
            <strong>{busy ? '正在解析…' : '点击选择 Excel 文件'}</strong>
            <span>支持 .xlsx / .xlsm，最大 20MB</span>
            <input ref={fileRef} type="file" accept=".xlsx,.xlsm" hidden
              onChange={e => { const f = e.target.files?.[0]; if (f) upload(f) }} />
          </div>
          <div className="form-grid">
            <label className="field"><span>导入模式</span>
              <select value={mode} onChange={e => setMode(e.target.value)}>
                <option value="replace">替换对应工作表数据</option>
                <option value="merge">按编号合并 / 更新</option>
              </select>
            </label>
            <div className="form-note">学生编号、教师工号、教室编号需唯一。导入后旧课表会标记为“待重算”。</div>
          </div>
          {summary && (
            <div className="inline-success"><CheckCircle2 size={16} /><span>已导入：学生 {summary.students}、教师 {summary.teachers}、教室 {summary.rooms}、课程配置 {summary.course_rows} 行</span></div>
          )}
          {summary && (summary.duplicates?.length > 0 || summary.failed_rows > 0) && (
            <div className="import-errors">
              <div className="error-head"><TriangleAlert size={16} /><strong>导入结果提示</strong></div>
              {summary.failed_rows > 0 && <p>失败行：{summary.failed_rows}</p>}
              {summary.duplicates?.map((x, i) => <p key={i}>{x}</p>)}
            </div>
          )}
          {errors.length > 0 && (
            <div className="import-errors">
              <div className="error-head"><TriangleAlert size={16} /><strong>导入未通过</strong></div>
              {errors.slice(0, 20).map((e, i) => <p key={i}>{e}</p>)}
            </div>
          )}
        </Card>
      </div>

      <Card title="导入表结构" subtitle="模板首行即表头">
        <div className="schema-grid">
          <div><strong>学生</strong><code>学号 · 姓名 · 行政班 · 外语 · 首选科目 · 再选1 · 再选2</code></div>
          <div><strong>教师</strong><code>工号 · 姓名 · 科目 · 不可排时间 · 候选科目 · 周课时上限</code></div>
          <div><strong>教室</strong><code>教室编号 · 教室名称 · 容量 · 楼栋</code></div>
          <div><strong>课程配置</strong><code>科目 · 细分课程 · 周课时 · 类型</code></div>
        </div>
      </Card>
    </>
  )
}
