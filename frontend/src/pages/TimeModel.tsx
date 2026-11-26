import { useState } from 'react'
import { Braces, CalendarDays, Clock3, PencilRuler } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, MetricCard, Modal, PageHeader } from '../components/UI'
import { PHASE_COLORS } from '../theme'

export default function TimeModel() {
  const { scenario, setScenario, notify } = useApp()
  const [open, setOpen] = useState(false)
  const [json, setJson] = useState('')
  const [saving, setSaving] = useState(false)

  if (!scenario) return <div className="loading-block">正在加载时间模型…</div>
  const tm = scenario.time_model
  const active = tm.slots.filter(s => s.active)
  const byPhase = (phase: string) => active.filter(s => s.phase === phase).length
  const byBand = (band: string) => active.filter(s => s.band === band).length

  const openEditor = () => {
    setJson(JSON.stringify(tm.slots, null, 2))
    setOpen(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const slots = JSON.parse(json)
      const updated = await api.putTimeModel(scenario.id, slots)
      setScenario(updated)
      setOpen(false)
      notify('success', '时间模型已更新，请重新求解')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const phaseCell = (phase: string | null, active: boolean, activity: string) => {
    if (!active) return { bg: '#EEF1F5', fg: '#98A2B3', label: activity }
    const p = PHASE_COLORS[phase || 'base']
    return { bg: p.bg, fg: p.fg, label: p.label }
  }

  return (
    <>
      <PageHeader eyebrow="基础数据" title="每周时间模型"
        description="默认 31 个教学时段：每天 6 节，含周末非标准安排。时间模型可整体替换为 JSON，系统会重新校验时段数量与阶段。"
        actions={<button className="btn btn-ghost" onClick={openEditor}><Braces size={15} />JSON 编辑</button>} />

      <div className="metrics-grid four">
        <MetricCard label="教学时段" value={active.length} hint={`网格 ${tm.slots.length} 格`} icon={<Clock3 size={18} />} />
        <MetricCard label="基础课时段" value={byPhase('base')} hint="语文 / 数学" />
        <MetricCard label="外语时段" value={byPhase('foreign')} hint="英语 / 日语" tone="teal" />
        <MetricCard label="走班时段" value={`${byBand('first') + byBand('second_a') + byBand('second_b')}`} hint={`首选 ${byBand('first')} · 再选 A ${byBand('second_a')} · B ${byBand('second_b')}`} tone="violet" />
      </div>

      <Card title={tm.name} subtitle={tm.assumption}
        actions={<button className="btn btn-sm btn-ghost" onClick={openEditor}><PencilRuler size={14} />调整时段阶段</button>}>
        <div className="timetable-legend">
          {Object.entries(PHASE_COLORS).map(([key, p]) => (
            <span key={key}><i style={{ background: p.bg, borderColor: p.fg }} />{p.label}</span>
          ))}
          <span><i style={{ background: '#EEF1F5', borderColor: '#CBD5E1' }} />非教学</span>
        </div>
        <div className="time-model-grid">
          <div className="tm-head">节次</div>
          {tm.days.map(day => <div key={day} className="tm-head">{day}</div>)}
          {Array.from({ length: tm.periods_per_day }, (_, i) => i + 1).map(period => (
            <div className="tm-row" key={period}>
              <div className="tm-period">第 {period} 节</div>
              {tm.days.map((day, di) => {
                const slot = tm.slots.find(s => s.day_index === di && s.period === period)
                if (!slot) return <div key={day} className="tm-cell inactive">—</div>
                const style = phaseCell(slot.phase, slot.active, slot.activity)
                return (
                  <div key={day} className="tm-cell" style={{ background: style.bg, borderColor: style.fg + '55' }}>
                    <strong style={{ color: style.fg }}>{style.label}</strong>
                    <span>{slot.active ? (slot.band === 'first' ? '首选' : slot.band === 'second_a' ? '再选A' : slot.band === 'second_b' ? '再选B' : slot.label.split('第')[1]) : slot.activity}</span>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </Card>

      <Card title="为什么把时间切成阶段？" subtitle="V0.1 的工程选择">
        <div className="explain-grid">
          <div><strong>基础段</strong><p>语文与数学共 13 节。所有行政班在这些时段上基础课，保证每名学生每周 13 节。</p></div>
          <div><strong>外语段</strong><p>英语、日语共 6 节。外语只与外语同步，支持跨班外语教学班。</p></div>
          <div><strong>首选走班段</strong><p>物理、历史各 4 节。全年级 320 名学生同时按首选科目分流，符合“物理只与历史同步”。</p></div>
          <div><strong>再选两段</strong><p>按固定科目顺序把每人的两门再选拆到 A/B 段。A 段最多 3 科、B 段最多 3 科，绝不出现四科同时走班。</p></div>
        </div>
      </Card>

      <Modal open={open} wide title="编辑时间模型 JSON" subtitle="必须保留 42 个网格时段、31 个教学时段，且每段走班至少 4 节。"
        onClose={() => setOpen(false)}
        footer={<><button className="btn btn-ghost" onClick={() => setOpen(false)}>取消</button><button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? '保存中…' : '校验并保存'}</button></>}>
        <textarea className="json-editor" value={json} onChange={e => setJson(e.target.value)} spellCheck={false} />
        <div className="form-note">字段说明：active=是否教学；phase=base/foreign/elective；band=first/second_a/second_b。修改后系统重算 active index。</div>
      </Modal>
    </>
  )
}
