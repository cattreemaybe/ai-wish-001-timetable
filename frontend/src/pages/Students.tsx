import { useMemo, useState } from 'react'
import { Filter, Pencil, Search, UsersRound } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, Modal, PageHeader } from '../components/UI'
import type { Student } from '../types'

const LANGS = ['英语', '日语']
const FIRST = ['物理', '历史']
const SECONDS = ['生物', '化学', '地理', '政治']
const PAGE_SIZE = 40

export default function Students() {
  const { scenario, setScenario, notify } = useApp()
  const [search, setSearch] = useState('')
  const [klass, setKlass] = useState('')
  const [language, setLanguage] = useState('')
  const [first, setFirst] = useState('')
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState<Student | null>(null)

  const filtered = useMemo(() => {
    if (!scenario) return []
    const q = search.trim().toLowerCase()
    return scenario.students.filter(s =>
      (!q || s.id.toLowerCase().includes(q) || s.name.includes(q)) &&
      (!klass || s.admin_class === klass) &&
      (!language || s.language === language) &&
      (!first || s.first_subject === first)
    )
  }, [scenario, search, klass, language, first])

  if (!scenario) return <div className="loading-block">正在加载学生数据…</div>
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pages - 1)
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)
  const classes = [...new Set(scenario.students.map(s => s.admin_class))].sort()

  const save = async () => {
    if (!editing) return
    if (editing.second_subjects[0] === editing.second_subjects[1]) {
      notify('error', '两门再选科目不能相同')
      return
    }
    try {
      const updated = await api.patchStudent(scenario.id, editing.id, {
        language: editing.language,
        first_subject: editing.first_subject,
        second_subjects: editing.second_subjects,
        admin_class: editing.admin_class,
      })
      setScenario(updated)
      setEditing(null)
      notify('success', '学生选科已更新；旧课表已标记为待重算')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
      <PageHeader eyebrow="基础数据" title="学生及选科管理"
        description="行政班已固定。每名学生选择外语、首选科目和两门再选科目；修改后需要重新排课。"
        actions={<Badge tone="blue"><UsersRound size={14} /> {scenario.students.length} 名学生</Badge>} />

      <div className="filter-bar">
        <div className="search-box"><Search size={16} /><input placeholder="搜索学号或姓名" value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} /></div>
        <div className="filter-group"><Filter size={15} />
          <select value={klass} onChange={e => { setKlass(e.target.value); setPage(0) }}>
            <option value="">全部行政班</option>{classes.map(c => <option key={c}>{c}</option>)}
          </select>
          <select value={language} onChange={e => { setLanguage(e.target.value); setPage(0) }}>
            <option value="">全部外语</option>{LANGS.map(x => <option key={x}>{x}</option>)}
          </select>
          <select value={first} onChange={e => { setFirst(e.target.value); setPage(0) }}>
            <option value="">全部首选</option>{FIRST.map(x => <option key={x}>{x}</option>)}
          </select>
        </div>
        <span className="filter-count">筛选出 {filtered.length} 人</span>
      </div>

      <Card>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>学号</th><th>姓名</th><th>行政班</th><th>外语</th><th>首选</th><th>再选科目</th><th>组合</th><th /></tr>
            </thead>
            <tbody>
              {rows.map(s => (
                <tr key={s.id}>
                  <td className="mono">{s.id}</td>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.admin_class}</td>
                  <td><Badge tone={s.language === '日语' ? 'purple' : 'blue'}>{s.language}</Badge></td>
                  <td><Badge tone={s.first_subject === '物理' ? 'purple' : 'amber'}>{s.first_subject}</Badge></td>
                  <td>{s.second_subjects.join(' + ')}</td>
                  <td className="muted">{s.first_subject} + {s.second_subjects.join(' + ')}</td>
                  <td><button className="icon-btn" onClick={() => setEditing({ ...s })}><Pencil size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>第 {safePage + 1} / {pages} 页</span>
          <div>
            <button className="btn btn-sm btn-ghost" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>上一页</button>
            <button className="btn btn-sm btn-ghost" disabled={safePage >= pages - 1} onClick={() => setPage(safePage + 1)}>下一页</button>
          </div>
        </div>
      </Card>

      <Modal open={!!editing} title="编辑学生选科" subtitle={editing ? `${editing.id} · ${editing.name}` : ''}
        onClose={() => setEditing(null)}
        footer={<><button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button><button className="btn btn-primary" onClick={save}>保存修改</button></>}>
        {editing && (
          <div className="form-grid">
            <label className="field"><span>姓名</span><input value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} /></label>
            <label className="field"><span>行政班</span><input value={editing.admin_class} onChange={e => setEditing({ ...editing, admin_class: e.target.value })} /></label>
            <label className="field"><span>外语</span><select value={editing.language} onChange={e => setEditing({ ...editing, language: e.target.value })}>{LANGS.map(x => <option key={x}>{x}</option>)}</select></label>
            <label className="field"><span>首选科目</span><select value={editing.first_subject} onChange={e => setEditing({ ...editing, first_subject: e.target.value })}>{FIRST.map(x => <option key={x}>{x}</option>)}</select></label>
            <label className="field"><span>再选科目 1</span><select value={editing.second_subjects[0]} onChange={e => setEditing({ ...editing, second_subjects: [e.target.value, editing.second_subjects[1]] })}>{SECONDS.map(x => <option key={x}>{x}</option>)}</select></label>
            <label className="field"><span>再选科目 2</span><select value={editing.second_subjects[1]} onChange={e => setEditing({ ...editing, second_subjects: [editing.second_subjects[0], e.target.value] })}>{SECONDS.map(x => <option key={x}>{x}</option>)}</select></label>
            <div className="form-note span-2">修改学生选科会改变教学班构成和课时任务。保存后请重新运行自动排课，旧课表不会被伪装成新结果。</div>
          </div>
        )}
      </Modal>
    </>
  )
}
