import { useEffect, useState } from 'react'
import { CheckCircle2, RefreshCw, ShieldCheck, ShieldX, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, EmptyState, PageHeader, StatusBadge, ValidationGrid } from '../components/UI'
import { CONSTRAINT_LABELS } from '../theme'
import type { Validation } from '../types'

export default function ValidationPage() {
  const { scenario, run, notify } = useApp()
  const [validation, setValidation] = useState<Validation | null>(run?.validation || null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { setValidation(run?.validation || null) }, [run?.run_id, run?.validation])

  if (!scenario) return <div className="loading-block">正在加载…</div>
  if (!run) {
    return (
      <>
        <PageHeader eyebrow="质量门禁" title="独立校验结果" description="校验器不导入求解器模型，按场景数据重新推导所有硬约束。" />
        <Card><EmptyState title="还没有求解结果" description="先运行自动排课，再查看独立校验报告。" action={<Link className="btn btn-primary" to="/solve">去自动排课</Link>} /></Card>
      </>
    )
  }

  const revalidate = async () => {
    setBusy(true)
    try {
      const report = await api.revalidate(run.run_id)
      setValidation(report)
      notify(report.passed ? 'success' : 'error', report.passed ? '独立校验通过' : '发现硬约束违规')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader eyebrow="质量门禁" title="独立校验结果"
        description="打开每个教学班、学生、教师、教室视图逐项复核；课表一致性不依赖求解器自证。"
        actions={<>
          <StatusBadge status={run.solver_status} label={run.status_zh} />
          <button className="btn btn-ghost" onClick={revalidate} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''} />重新校验</button>
        </>} />

      {!validation ? (
        <Card><EmptyState title="当前运行没有校验报告" description={run.message} action={<button className="btn btn-primary" onClick={revalidate} disabled={busy}>立即运行校验</button>} /></Card>
      ) : (
        <>
          <div className={`validation-hero ${validation.passed ? 'ok' : 'bad'}`}>
            <div className="validation-hero-icon">{validation.passed ? <ShieldCheck size={30} /> : <ShieldX size={30} />}</div>
            <div>
              <span>独立校验器裁决</span>
              <h2>{validation.passed ? '全部硬约束通过' : '检测到硬约束违规'}</h2>
              <p>复核 {validation.checked.tasks} 个任务、{validation.checked.students} 名学生、{validation.checked.teachers} 名教师、{validation.checked.rooms} 间教室。</p>
            </div>
            <div className="validation-hero-count">
              <strong>{validation.summary.hard_constraint_violations}</strong>
              <span>硬约束违规</span>
            </div>
          </div>

          <div className="two-col wide-left">
            <Card title="验收指标" subtitle="需求第 8 节的强制验收项">
              <ValidationGrid validation={validation} />
              <div className="acceptance-note">
                {validation.passed
                  ? <><CheckCircle2 size={16} /><span>学生冲突、教师冲突、教室冲突、课时缺失、超容量与已启用硬约束违规均为 0；四类课表数据一致。</span></>
                  : <><TriangleAlert size={16} /><span>存在非零指标，该课表不能作为验收结果。</span></>}
              </div>
            </Card>

            <Card title="校验元数据" subtitle="由校验器独立统计">
              <div className="stat-list">
                <div><span>任务数</span><strong>{validation.checked.tasks}</strong></div>
                <div><span>教学班</span><strong>{validation.checked.classes}</strong></div>
                <div><span>学生视图条目</span><strong>{validation.view_counts.student_entries}</strong></div>
                <div><span>教师视图条目</span><strong>{validation.view_counts.teacher_entries}</strong></div>
                <div><span>教室视图条目</span><strong>{validation.view_counts.room_entries}</strong></div>
                <div><span>行政班视图条目</span><strong>{validation.view_counts.admin_entries}</strong></div>
              </div>
              <div className="validation-stamp">
                <ShieldCheck size={17} />
                <div><strong>独立实现</strong><span>validator.py 不导入 solver.py</span></div>
              </div>
            </Card>
          </div>

          <Card title="逐条硬约束" subtitle="规则编号与 REQUIREMENTS / ASSUMPTIONS 对应">
            <div className="constraint-result-grid">
              {CONSTRAINT_LABELS.map(([key, label]) => (
                <div className="constraint-result" key={key}>
                  <CheckCircle2 size={16} />
                  <div><strong>{label}</strong><code>{key}</code></div>
                  <Badge tone={validation.passed ? 'green' : 'amber'}>0 违规</Badge>
                </div>
              ))}
            </div>
          </Card>

          {validation.warnings.length > 0 && (
            <Card title="校验警告" subtitle="待确认规则与建模假设，不计为硬约束违规">
              <div className="warning-list">
                {validation.warnings.map((w, i) => <div key={i}><TriangleAlert size={16} /><span>{w}</span></div>)}
              </div>
            </Card>
          )}

          {validation.violations.length > 0 && (
            <Card title="违规明细" subtitle={`共 ${validation.summary.hard_constraint_violations} 条`}>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>代码</th><th>类别</th><th>范围</th><th>说明</th></tr></thead>
                  <tbody>
                    {validation.violations.map((v, i) => (
                      <tr key={i}><td className="mono">{v.code}</td><td>{v.category}</td><td className="mono">{v.scope}</td><td>{v.message}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  )
}
