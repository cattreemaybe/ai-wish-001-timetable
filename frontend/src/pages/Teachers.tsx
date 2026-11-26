import { useEffect, useMemo, useState } from 'react'
import { CalendarOff, Pencil, Search, UserRound, UsersRound } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, Modal, PageHeader } from '../components/UI'
import ImportActions from '../components/ImportActions'
import type { Teacher } from '../types'

export default function Teachers() {
  const { scenario, setScenario, notify } = useApp()
  const [search, setSearch] = useState('')
  const [subject, setSubject] = useState('')
  const [editing, setEditing] = useState<Teacher | null>(null)
  const [adding, setAdding] = useState<{ name: string; subject: string } | null>(null)
  const [bindings, setBindings] = useState<Record<string, string>>({})
  const [bindingBusy, setBindingBusy] = useState(false)

  useEffect(() => {
    setBindings({ ...(scenario?.teacher_bindings || {}) })
  }, [scenario?.id, scenario?.teacher_bindings])

  const list = useMemo(() => {
    if (!scenario) return []
    const q = search.trim()
    return scenario.teachers.filter(t =>
      (!q || t.name.includes(q) || t.id.includes(q)) && (!subject || t.subject === subject))
  }, [scenario, search, subject])

  if (!scenario) return <div className="loading-block">正在加载教师数据…</div>
  const subjects = [...new Set(scenario.teachers.map(t => t.subject))]
  const loadBySubject = scenario.analysis.teacher_counts
  const admins = Object.keys(scenario.analysis.admin_class_sizes)
  const bySubject = (sub: string) => scenario.teachers.filter(t => t.subject === sub)
  const setBinding = (key: string, value: string) => {
    setBindings(prev => {
      const next = { ...prev }
      if (value) next[key] = value
      else delete next[key]
      return next
    })
  }
  const saveBindings = async () => {
    setBindingBusy(true)
    try {
      const updated = await api.putTeacherBindings(scenario.id, bindings)
      setScenario(updated)
      notify('success', '基础科教师绑定已保存；请重新求解')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setBindingBusy(false) }
  }

  const toggleSlot = (label: string) => {
    if (!editing) return
    const has = editing.unavailable_slots.includes(label)
    setEditing({
      ...editing,
      unavailable_slots: has ? editing.unavailable_slots.filter(x => x !== label) : [...editing.unavailable_slots, label],
    })
  }

  const saveNew = async () => {
    if (!adding) return
    if (!adding.name.trim()) {
      notify('error', '教师姓名不能为空')
      return
    }
    try {
      const updated = await api.addTeacher(scenario.id, { name: adding.name.trim(), subject: adding.subject })
      setScenario(updated)
      setAdding(null)
      notify('success', '教师已新增；可在列表中继续设置不可排时间')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  const save = async () => {
    if (!editing) return
    try {
      const updated = await api.patchTeacher(scenario.id, editing.id, {
        unavailable_slots: editing.unavailable_slots,
        max_weekly_periods: editing.max_weekly_periods || undefined,
      })
      setScenario(updated)
      setEditing(null)
      notify('success', '教师时间限制已更新')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
      <PageHeader eyebrow="基础数据" title="教师及可用时间管理"
        description="V0.1 优先采用预先绑定与自动分配。教师不可排时间会作为硬约束进入 CP-SAT，并在独立校验器中复核。"
        actions={<Badge tone="green"><UsersRound size={14} /> {scenario.teachers.length} 名候选教师</Badge>} />

      <div className="data-actions-bar">
        <ImportActions scenarioId={scenario.id} sheet="teachers"
          onImported={updated => { setScenario(updated); notify('success', '教师数据已导入；旧课表需重新排课') }}
          onManualAdd={() => setAdding({ name: '', subject: '语文' })} />
      </div>

      <div className="teacher-summary">
        {subjects.map(s => (
          <div key={s} className="teacher-stat">
            <span>{s}</span><strong>{loadBySubject[s] || 0}</strong><small>人</small>
          </div>
        ))}
      </div>

      <Card title="基础科教师绑定" subtitle="可选：把某个行政班的语文/数学课指定给具体教师；留空则自动分配"
        actions={<button className="btn btn-sm btn-primary" onClick={saveBindings} disabled={bindingBusy}>{bindingBusy ? '保存中…' : '保存绑定'}</button>}>
        <div className="binding-grid">
          {admins.map((admin, idx) => (
            <div className="binding-row" key={admin}>
              <span className="binding-index">{String(idx + 1).padStart(2, '0')}</span>
              <strong>{admin}</strong>
              <label>语文
                <select value={bindings[`语文|${admin}`] || ''} onChange={e => setBinding(`语文|${admin}`, e.target.value)}>
                  <option value="">自动分配</option>
                  {bySubject('语文').map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <label>数学
                <select value={bindings[`数学|${admin}`] || ''} onChange={e => setBinding(`数学|${admin}`, e.target.value)}>
                  <option value="">自动分配</option>
                  {bySubject('数学').map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
            </div>
          ))}
        </div>
        <div className="form-note">绑定是硬选择：如果指定教师在所需时段不可用，系统会如实报告，而不是自动换人。当前 UI 开放基础科绑定；外语/走班教学班绑定键已在数据层预留。</div>
      </Card>

      <div className="filter-bar">
        <div className="search-box"><Search size={16} /><input placeholder="搜索工号或姓名" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <div className="filter-group">
          <select value={subject} onChange={e => setSubject(e.target.value)}>
            <option value="">全部科目</option>{subjects.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <span className="filter-count">{list.length} 名教师</span>
      </div>

      <Card>
        <div className="table-wrap">
          <table>
            <thead><tr><th>工号</th><th>姓名</th><th>科目</th><th>不可排时间</th><th>周课时上限</th><th /></tr></thead>
            <tbody>
              {list.map(t => (
                <tr key={t.id}>
                  <td className="mono">{t.id}</td>
                  <td><strong>{t.name}</strong></td>
                  <td><Badge tone="neutral">{t.subject}</Badge></td>
                  <td>
                    {t.unavailable_slots.length ? (
                      <div className="slot-chips">
                        {t.unavailable_slots.slice(0, 4).map(s => <span key={s}>{s}</span>)}
                        {t.unavailable_slots.length > 4 && <em>+{t.unavailable_slots.length - 4}</em>}
                      </div>
                    ) : <span className="ok-text">全部时段可用</span>}
                  </td>
                  <td>{t.max_weekly_periods || <span className="muted">未设置</span>}</td>
                  <td><button className="icon-btn" onClick={() => setEditing({ ...t, unavailable_slots: [...t.unavailable_slots] })}><Pencil size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal open={!!adding} title="新增教师" subtitle="先录入基本信息，再在列表中设置不可排时间。"
        onClose={() => setAdding(null)}
        footer={<><button className="btn btn-ghost" onClick={() => setAdding(null)}>取消</button><button className="btn btn-primary" onClick={saveNew}>新增教师</button></>}>
        {adding && (
          <div className="form-grid">
            <label className="field"><span>姓名</span><input value={adding.name} placeholder="例如：王老师" onChange={e => setAdding({ ...adding, name: e.target.value })} /></label>
            <label className="field"><span>科目</span><select value={adding.subject} onChange={e => setAdding({ ...adding, subject: e.target.value })}>{['语文','数学','英语','日语','物理','历史','生物','化学','地理','政治'].map(s => <option key={s}>{s}</option>)}</select></label>
            <div className="form-note span-2">新教师默认全时段可用。保存后点列表里的编辑按钮，可以设置不可排时间。</div>
          </div>
        )}
      </Modal>

      <Modal open={!!editing} wide title="设置教师不可排时间"
        subtitle={editing ? `${editing.id} · ${editing.name} · ${editing.subject}` : ''}
        onClose={() => setEditing(null)}
        footer={<><button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button><button className="btn btn-primary" onClick={save}>保存时间限制</button></>}>
        {editing && (
          <>
            <div className="availability-head">
              <div><CalendarOff size={16} /><span>点击时段切换“不可排”。灰色非教学时段不影响求解。</span></div>
              <button className="btn btn-sm btn-ghost" onClick={() => setEditing({ ...editing, unavailable_slots: [] })}>清空</button>
            </div>
            <div className="availability-grid">
              {scenario.time_model.days.map((day, di) => (
                <div className="availability-day" key={day}>
                  <strong>{day}</strong>
                  {scenario.time_model.slots.filter(s => s.day_index === di).map(slot => {
                    const unavailable = editing.unavailable_slots.includes(slot.label)
                    return (
                      <button key={slot.label} disabled={!slot.active}
                        className={`slot-toggle ${unavailable ? 'off' : ''} ${!slot.active ? 'inactive' : ''}`}
                        onClick={() => toggleSlot(slot.label)}
                        title={slot.active ? `${slot.label} · ${slot.phase}` : slot.activity}>
                        <span>{slot.period}</span>
                        <em>{unavailable ? '不可排' : slot.active ? (slot.phase === 'base' ? '基础' : slot.phase === 'foreign' ? '外语' : '走班') : slot.activity}</em>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <div className="form-grid" style={{ marginTop: 18 }}>
              <label className="field"><span>周课时上限（可选）</span><input type="number" min={1} max={60} value={editing.max_weekly_periods || ''} placeholder="不设置"
                onChange={e => setEditing({ ...editing, max_weekly_periods: e.target.value ? Number(e.target.value) : null })} /></label>
              <div className="form-note">教师自动分配的业务规则仍待确认；当前系统按科目候选池自动预分配，指定教师可在后续数据版本中绑定。</div>
            </div>
          </>
        )}
      </Modal>
    </>
  )
}
