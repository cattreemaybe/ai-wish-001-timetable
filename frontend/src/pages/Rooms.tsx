import { useMemo, useState } from 'react'
import { DoorOpen, Pencil } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, MetricCard, Modal, PageHeader } from '../components/UI'
import type { Room } from '../types'

export default function Rooms() {
  const { scenario, setScenario, run, notify } = useApp()
  const [editing, setEditing] = useState<Room | null>(null)

  const usage = useMemo(() => {
    const map: Record<string, number> = {}
    run?.tasks.forEach(t => { map[t.room_id] = (map[t.room_id] || 0) + 1 })
    return map
  }, [run])

  if (!scenario) return <div className="loading-block">正在加载教室数据…</div>
  const totalSeats = scenario.rooms.reduce((s, r) => s + r.capacity, 0)
  const maxCap = Math.max(...scenario.rooms.map(r => r.capacity))
  const large = scenario.rooms.filter(r => r.capacity >= 60).length

  const save = async () => {
    if (!editing) return
    try {
      const updated = await api.patchRoom(scenario.id, editing.id, {
        capacity: editing.capacity, name: editing.name, building: editing.building,
      })
      setScenario(updated)
      setEditing(null)
      notify('success', '教室资源已更新；旧课表需重新校验')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
      <PageHeader eyebrow="基础数据" title="教室资源管理"
        description="走班教学班按最大班额 54 人配置到 60 座教室；容量变化会直接改变建班可行性。" />

      <div className="metrics-grid four">
        <MetricCard label="教室总数" value={scenario.rooms.length} hint="A/B/C 三座" icon={<DoorOpen size={18} />} />
        <MetricCard label="总座位" value={totalSeats} hint="全部教室容量之和" />
        <MetricCard label="最大教室" value={`${maxCap} 座`} hint={`${large} 间 ≥60 座`} tone="teal" />
        <MetricCard label="排课使用" value={Object.keys(usage).length} hint="本次课表涉及的教室" tone="violet" />
      </div>

      <Card title="教室清单" subtitle="点击编辑容量。V0.1 的教室分配在求解前完成，求解器再检查时间冲突。">
        <div className="room-grid">
          {scenario.rooms.map(r => (
            <div className="room-card" key={r.id}>
              <div className="room-icon"><DoorOpen size={19} /></div>
              <div className="room-main">
                <strong>{r.name}</strong>
                <span>{r.id} · {r.building}</span>
              </div>
              <div className="room-cap">{r.capacity}<small>座</small></div>
              <div className="room-usage">{usage[r.id] ? `${usage[r.id]} 节课` : '未使用'}</div>
              <button className="icon-btn" onClick={() => setEditing({ ...r })}><Pencil size={15} /></button>
            </div>
          ))}
        </div>
      </Card>

      <Modal open={!!editing} title="编辑教室"
        subtitle={editing ? editing.id : ''} onClose={() => setEditing(null)}
        footer={<><button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button><button className="btn btn-primary" onClick={save}>保存</button></>}>
        {editing && (
          <div className="form-grid">
            <label className="field"><span>教室名称</span><input value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} /></label>
            <label className="field"><span>容量</span><input type="number" min={1} max={500} value={editing.capacity} onChange={e => setEditing({ ...editing, capacity: Number(e.target.value) })} /></label>
            <label className="field"><span>楼栋</span><input value={editing.building} onChange={e => setEditing({ ...editing, building: e.target.value })} /></label>
            <div className="form-note">若降低容量导致某个教学班超过容量，毕业班会如实报告超容量，不会自动忽略。</div>
          </div>
        )}
      </Modal>
    </>
  )
}
