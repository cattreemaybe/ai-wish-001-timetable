import { useState } from 'react'
import { BookOpenCheck, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, Modal, PageHeader } from '../components/UI'
import { subjectStyle } from '../theme'
import type { CourseComponent, CourseConfig } from '../types'

export default function Courses() {
  const { scenario, setScenario, notify } = useApp()
  const [editingSubject, setEditingSubject] = useState<string | null>(null)
  const [draft, setDraft] = useState<CourseComponent[]>([])

  if (!scenario) return <div className="loading-block">正在加载课程配置…</div>
  const config = scenario.course_config
  const subjects = Object.keys(config)
  const totalFor = (subject: string) => config[subject].reduce((sum, c) => sum + Number(c.hours || 0), 0)
  const baseSubjects = ['语文', '数学', '英语', '日语']
  const electiveSubjects = ['物理', '历史', '生物', '化学', '地理', '政治']

  const startEdit = (subject: string) => {
    setEditingSubject(subject)
    setDraft(config[subject].map(c => ({ ...c })))
  }

  const save = async () => {
    if (!editingSubject) return
    if (draft.some(c => !c.name.trim() || Number(c.hours) < 0)) {
      notify('error', '细分课程名称不能为空，课时不能为负')
      return
    }
    const next: CourseConfig = { ...config, [editingSubject]: draft }
    try {
      const updated = await api.putCourseConfig(scenario.id, next)
      setScenario(updated)
      setEditingSubject(null)
      notify('success', `${editingSubject} 课时配置已更新，请重新求解`)
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  const removeComponent = (idx: number) => setDraft(d => d.filter((_, i) => i !== idx))
  const addComponent = () => setDraft(d => [...d, { name: '新细分课程', hours: 1, kind: 'practice' }])

  const renderCards = (list: string[]) => (
    <div className="course-grid">
      {list.map(subject => (
        <div className="course-card" key={subject} style={{ borderTopColor: subjectStyle(subject).fg }}>
          <div className="course-head">
            <div>
              <span className="course-subject" style={{ color: subjectStyle(subject).fg }}>{subject}</span>
              <small>{subject === '语文' || subject === '数学' ? '行政班基础课' : subject === '英语' || subject === '日语' ? '外语走班' : '再选走班'}</small>
            </div>
            <Badge tone="neutral">{totalFor(subject)} 节/周</Badge>
          </div>
          <div className="component-list">
            {config[subject].map(c => (
              <div key={c.name}>
                <span>{c.name}</span>
                <em>{c.kind === 'lecture' ? '正课' : c.kind === 'practice' ? '落实' : '专题'}</em>
                <strong>{c.hours}</strong>
              </div>
            ))}
          </div>
          <button className="btn btn-sm btn-ghost course-edit" onClick={() => startEdit(subject)}><Pencil size={14} />编辑课时</button>
        </div>
      ))}
    </div>
  )

  return (
    <>
      <PageHeader eyebrow="基础数据" title="课程课时配置"
        description="默认按需求资料配置。每名学生每周合计 31 节：语文 5、数学 8、外语 6、首选 4、两门再选各 4。"
        actions={<Badge tone="blue"><BookOpenCheck size={14} /> {subjects.length} 个科目</Badge>} />

      <Card title="行政班基础与外语" subtitle="语文、数学、外语由行政班或外语教学班组织">
        {renderCards(baseSubjects)}
      </Card>
      <Card title="首选与再选科目" subtitle="每科正课 2 节 + 落实课 2 节；走班教学班组织">
        {renderCards(electiveSubjects)}
      </Card>

      <Modal open={!!editingSubject} title={`编辑 ${editingSubject} 课时`}
        subtitle="保存后课程任务数量改变；若与31节总时段不一致，求解会如实报告不可行或数据错误。"
        onClose={() => setEditingSubject(null)}
        footer={<><button className="btn btn-ghost" onClick={() => setEditingSubject(null)}>取消</button><button className="btn btn-primary" onClick={save}>保存配置</button></>}>
        <div className="component-editor">
          {draft.map((c, i) => (
            <div className="component-edit-row" key={i}>
              <input value={c.name} onChange={e => setDraft(d => d.map((x, xi) => xi === i ? { ...x, name: e.target.value } : x))} placeholder="细分课程" />
              <select value={c.kind} onChange={e => setDraft(d => d.map((x, xi) => xi === i ? { ...x, kind: e.target.value } : x))}>
                <option value="lecture">正课</option><option value="practice">落实</option><option value="seminar">专题</option>
              </select>
              <input type="number" min={0} max={12} value={c.hours} onChange={e => setDraft(d => d.map((x, xi) => xi === i ? { ...x, hours: Number(e.target.value) } : x))} />
              <button className="icon-btn danger" onClick={() => removeComponent(i)}><Trash2 size={15} /></button>
            </div>
          ))}
          <button className="btn btn-sm btn-ghost" onClick={addComponent}><Plus size={14} />新增细分课程</button>
          <div className="form-note">合计：{draft.reduce((s, c) => s + Number(c.hours || 0), 0)} 节/周</div>
        </div>
      </Modal>
    </>
  )
}
