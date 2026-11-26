import { useEffect, useState } from 'react'
import { CalendarDays, Download, Filter, Search } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, EmptyState, PageHeader, Spinner } from '../components/UI'
import { subjectStyle } from '../theme'
import type { EntityOption, TimetableResponse, ViewKey } from '../types'

const VIEW_META: Record<ViewKey, { title: string; desc: string; entityLabel: string; note: string }> = {
  admin: {
    title: '行政班课表', desc: '按行政班查看整体安排；走班时段同一格可能出现多个教学班。',
    entityLabel: '行政班', note: '行政班学生在该时段按教学班分流。',
  },
  student: {
    title: '学生个人课表', desc: '每名学生每周 31 节，逐一展示教学班、教师与教室。',
    entityLabel: '学生', note: '同一时段仅一门课程。',
  },
  teacher: {
    title: '教师个人课表', desc: '按教师查看授课安排、空堂与不可排时间约束。',
    entityLabel: '教师', note: '同一时段不会出现两个教学任务。',
  },
  room: {
    title: '教室使用课表', desc: '按教室查看占用情况，核对容量与时间冲突。',
    entityLabel: '教室', note: '同一时段只安排一个教学班。',
  },
  class: {
    title: '教学班课表', desc: '按教学班查看 4 节走班课程安排。',
    entityLabel: '教学班', note: '走班教学班固定教师与教室。',
  },
}

export default function TimetablePage({ view }: { view: ViewKey }) {
  const { scenario, run } = useApp()
  const meta = VIEW_META[view]
  const [entities, setEntities] = useState<EntityOption[]>([])
  const [entityId, setEntityId] = useState('')
  const [data, setData] = useState<TimetableResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    if (!run) return
    let cancelled = false
    setLoading(true)
    api.entities(run.run_id, view)
      .then(list => {
        if (cancelled) return
        setEntities(list)
        setEntityId(prev => list.some(x => x.id === prev) ? prev : (list[0]?.id || ''))
      })
      .catch(() => { if (!cancelled) { setEntities([]); setEntityId('') } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [run?.run_id, view])

  useEffect(() => {
    if (!run || !entityId) { setData(null); return }
    let cancelled = false
    setLoading(true)
    api.timetable(run.run_id, view, entityId)
      .then(d => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setData(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [run?.run_id, view, entityId])

  if (!scenario) return <div className="loading-block">正在加载…</div>

  if (!run || !run.tasks.length) {
    return (
      <>
        <PageHeader eyebrow="课表视图" title={meta.title} description={meta.desc} />
        <Card><EmptyState title="暂无课表" description={run?.message || '请先在自动排课页面运行求解。'} /></Card>
      </>
    )
  }

  const filteredEntities = entities.filter(e => {
    if (!q.trim()) return true
    const text = `${e.id} ${e.name} ${e.admin_class || ''}`.toLowerCase()
    return text.includes(q.trim().toLowerCase())
  })

  const subjects = [...new Set(data?.cells.flatMap(c => c.tasks.map(t => t.subject)) || [])]

  return (
    <>
      <PageHeader eyebrow="课表视图" title={meta.title} description={meta.desc}
        actions={<>
          <Badge tone={run.validation?.passed ? 'green' : 'amber'}>{run.validation?.passed ? '校验通过' : '校验异常'}</Badge>
          <button className="btn btn-ghost" onClick={() => window.print()}><Download size={15} />打印 / 另存 PDF</button>
        </>} />

      <Card>
        <div className="timetable-toolbar">
          <div className="entity-picker">
            <label>{meta.entityLabel}</label>
            <div className="search-box small"><Search size={15} /><input placeholder={`筛选${meta.entityLabel}`} value={q} onChange={e => setQ(e.target.value)} /></div>
            <select value={entityId} onChange={e => setEntityId(e.target.value)}>
              {filteredEntities.map(e => (
                <option key={e.id} value={e.id}>{e.id === e.name ? e.name : `${e.id} · ${e.name}`}{e.admin_class ? ` · ${e.admin_class}` : ''}</option>
              ))}
            </select>
          </div>
          <div className="timetable-meta">
            <span><CalendarDays size={15} /> {run.scenario_name}</span>
            <span><Filter size={15} /> {data?.task_count ?? 0} 个任务</span>
            {loading && <Spinner />}
          </div>
        </div>
        <div className="timetable-legend">
          {subjects.map(s => <span key={s}><i style={{ background: subjectStyle(s).bg, borderColor: subjectStyle(s).fg }} />{s}</span>)}
          <span><i style={{ background: '#EEF1F5', borderColor: '#CBD5E1' }} />非教学 / 空</span>
          <em>{meta.note}</em>
        </div>

        {data ? (
          <div className="timetable-scroll">
            <div className="tt-grid">
              <div className="tt-corner">节次</div>
              {data.days.map(day => <div className="tt-day" key={day}>{day}</div>)}
              {data.periods.map(period => (
                <div className="tt-row-fragment" key={period}>
                  <div className="tt-period"><strong>{period}</strong><span>第{period}节</span></div>
                  {data.days.map((_, di) => {
                    const cell = data.cells.find(c => c.day_index === di && c.period === period)
                    if (!cell) return <div className="tt-cell inactive" key={di}>—</div>
                    if (!cell.active) {
                      return <div className="tt-cell inactive" key={di}><span className="inactive-label">{cell.activity}</span></div>
                    }
                    return (
                      <div className={`tt-cell ${cell.tasks.length > 1 ? 'multi' : ''}`} key={di}>
                        {cell.tasks.map(t => {
                          const style = subjectStyle(t.subject)
                          return (
                            <div className="lesson-card" key={t.id} style={{ background: style.bg, borderColor: style.border }}>
                              <div className="lesson-top">
                                <strong style={{ color: style.fg }}>{t.subject}</strong>
                                {t.is_elective && <em>走班</em>}
                              </div>
                              <span>{t.component}</span>
                              <small>{t.class_name}</small>
                              <div className="lesson-foot"><span>{t.teacher_name}</span><span>{t.room_name}</span></div>
                              {view === 'admin' && <div className="lesson-students">{t.student_count} 人 · {t.admin_classes.join('、')}</div>}
                            </div>
                          )
                        })}
                        {!cell.tasks.length && <span className="empty-cell">空堂</span>}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        ) : <EmptyState title="正在读取课表…" />}
      </Card>
    </>
  )
}
