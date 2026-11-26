import { useMemo, useState } from 'react'
import { ArrowRight, ClipboardList, GitMerge, Search, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'
import { Badge, Card, EmptyState, MetricCard, Modal, PageHeader } from '../components/UI'
import { BAND_LABELS, KIND_LABELS, subjectStyle } from '../theme'
import type { ClassGroup } from '../types'

export default function Classes() {
  const { scenario, run } = useApp()
  const [kind, setKind] = useState('')
  const [search, setSearch] = useState('')
  const [detail, setDetail] = useState<ClassGroup | null>(null)

  const classes = useMemo(() => {
    if (!run) return []
    const q = search.trim()
    return run.classes.filter(c =>
      (!kind || c.kind === kind) &&
      (!q || c.name.includes(q) || c.subject.includes(q) || c.admin_classes.some(a => a.includes(q))) &&
      c.kind !== 'admin_base'
    )
  }, [run, kind, search])

  if (!scenario) return <div className="loading-block">正在加载…</div>
  if (!run || !run.classes.length) {
    return (
      <>
        <PageHeader eyebrow="走班与规则" title="走班教学班管理" description="教学班由分阶段建班算法生成，展示跨行政班合班、走班段与教师/教室归属。" />
        <Card><EmptyState title="暂无教学班" description={run?.message || '请先运行自动排课。'} action={<Link className="btn btn-primary" to="/solve">去自动排课</Link>} /></Card>
      </>
    )
  }

  const metrics = run.metrics
  const studentById = new Map(scenario.students.map(s => [s.id, s]))
  const taskById = new Map(run.tasks.map(t => [t.id, t]))
  const kinds = [...new Set(run.classes.filter(c => c.kind !== 'admin_base').map(c => c.kind))]
  const detailStudents = detail ? detail.student_ids.map(id => studentById.get(id)).filter(Boolean) : []
  const detailTasks = detail ? detail.task_ids.map(id => taskById.get(id)).filter(Boolean) : []

  return (
    <>
      <PageHeader eyebrow="走班与规则" title="走班教学班管理"
        description="每个教学班有固定任课教师和教室；走班学生按教学班重组，跨行政班合班会明确标注。"
        actions={<Badge tone="blue"><ClipboardList size={14} /> {run.classes.length} 个教学班</Badge>} />

      <div className="metrics-grid four">
        <MetricCard label="走班教学班" value={metrics.elective_class_count} hint="首选 + 再选" />
        <MetricCard label="合并教学班" value={metrics.merged_class_count} hint="跨行政班合班" tone="teal" icon={<GitMerge size={18} />} />
        <MetricCard label="走班学生" value={metrics.walking_student_count} hint={`${Math.round(metrics.walking_student_ratio * 100)}% 覆盖`} tone="amber" />
        <MetricCard label="平均班额" value={metrics.avg_class_size} hint={`最大 ${metrics.max_class_size} 人`} tone="violet" icon={<UsersRound size={18} />} />
      </div>

      <Card title="教学班清单" subtitle="后台基础班（语文/数学）不在此列表展示，可到行政班课表查看"
        actions={
          <div className="filter-inline">
            <div className="search-box small"><Search size={15} /><input placeholder="搜索教学班/科目/行政班" value={search} onChange={e => setSearch(e.target.value)} /></div>
            <select value={kind} onChange={e => setKind(e.target.value)}>
              <option value="">全部类型</option>
              {kinds.map(k => <option key={k} value={k}>{KIND_LABELS[k] || k}</option>)}
            </select>
          </div>
        }>
        <div className="table-wrap">
          <table>
            <thead><tr><th>教学班</th><th>科目</th><th>类型</th><th>人数</th><th>行政班构成</th><th>教师</th><th>教室</th><th>走班段</th><th /></tr></thead>
            <tbody>
              {classes.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong>{c.is_merged && <Badge tone="blue">合班</Badge>}</td>
                  <td><span className="subject-dot" style={{ background: subjectStyle(c.subject).fg }} />{c.subject}</td>
                  <td className="muted">{KIND_LABELS[c.kind] || c.kind}</td>
                  <td>{c.size}</td>
                  <td className="muted">{c.admin_classes.join('、')}</td>
                  <td>{c.teacher_name}</td>
                  <td>{c.room_name}</td>
                  <td><Badge tone="neutral">{BAND_LABELS[c.band] || c.band}</Badge></td>
                  <td><button className="text-link" onClick={() => setDetail(c)}>详情 <ArrowRight size={13} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal open={!!detail} wide title={detail?.name || ''} subtitle={detail ? `${detail.subject} · ${KIND_LABELS[detail.kind]} · ${detail.size} 人` : ''}
        onClose={() => setDetail(null)}>
        {detail && (
          <div className="class-detail">
            <div className="class-detail-meta">
              <div><span>任课教师</span><strong>{detail.teacher_name}</strong></div>
              <div><span>教室</span><strong>{detail.room_name}</strong></div>
              <div><span>走班段</span><strong>{BAND_LABELS[detail.band]}</strong></div>
              <div><span>行政班</span><strong>{detail.admin_classes.join('、')}</strong></div>
            </div>
            <div className="detail-section">
              <h4>课时构成</h4>
              <div className="chip-row">{detail.components.map(c => <span className="data-chip" key={c.name}>{c.name} · {c.hours} 节</span>)}</div>
            </div>
            <div className="detail-section">
              <h4>上课时段</h4>
              <div className="chip-row">{detailTasks.sort((a, b) => (a?.slot_index || 0) - (b?.slot_index || 0)).map(t => <span className="data-chip" key={t!.id}>{t!.slot_label} · {t!.component}</span>)}</div>
            </div>
            <div className="detail-section">
              <h4>学生名单 <small>{detailStudents.length} 人</small></h4>
              <div className="student-chips">
                {detailStudents.slice(0, 100).map(s => <span key={s!.id}>{s!.name}<em>{s!.admin_class}</em></span>)}
                {detailStudents.length > 100 && <span>… 共 {detailStudents.length} 人</span>}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
