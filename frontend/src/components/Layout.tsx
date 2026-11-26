import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BookOpenCheck, CalendarDays, CheckCircle2, ClipboardList, DoorOpen, FileSpreadsheet,
  GraduationCap, House, LayoutDashboard, ListChecks, PlayCircle, Settings2,
  Sparkles, Table2, UserRound, UsersRound, Wand2,
} from 'lucide-react'
import { useApp } from '../context'
import { StatusBadge, Spinner } from './UI'

const groups = [
  {
    label: '工作台',
    items: [
      { to: '/', label: '排课总览', icon: LayoutDashboard, end: true },
      { to: '/solve', label: '自动排课', icon: PlayCircle },
      { to: '/validation', label: '校验结果', icon: CheckCircle2 },
    ],
  },
  {
    label: '基础数据',
    items: [
      { to: '/students', label: '学生选科', icon: UsersRound },
      { to: '/teachers', label: '教师资源', icon: UserRound },
      { to: '/courses', label: '课程课时', icon: BookOpenCheck },
      { to: '/rooms', label: '教室资源', icon: DoorOpen },
      { to: '/time-model', label: '时间模型', icon: CalendarDays },
    ],
  },
  {
    label: '走班与规则',
    items: [
      { to: '/classes', label: '教学班', icon: ClipboardList },
      { to: '/rules', label: '排课规则', icon: Settings2 },
    ],
  },
  {
    label: '课表视图',
    items: [
      { to: '/timetable/admin', label: '行政班课表', icon: Table2 },
      { to: '/timetable/student', label: '学生课表', icon: GraduationCap },
      { to: '/timetable/teacher', label: '教师课表', icon: UserRound },
      { to: '/timetable/room', label: '教室课表', icon: House },
    ],
  },
  {
    label: '数据交换',
    items: [
      { to: '/excel', label: 'Excel 导入导出', icon: FileSpreadsheet },
    ],
  },
]

export default function Layout() {
  const { scenario, scenarioId, setScenarioId, scenarios, run, solving, solve, isStale, toast, clearToast, loading } = useApp()
  const navigate = useNavigate()
  const location = useLocation()

  const onSolve = async () => {
    await solve()
    if (!location.pathname.startsWith('/solve')) navigate('/solve')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Wand2 size={22} /></div>
          <div>
            <strong>走班排课</strong>
            <span>AI-WISH-001</span>
          </div>
        </div>
        <div className="brand-sub">
          <Sparkles size={13} />
          <span>真实 CP-SAT 求解 · 本地运行</span>
        </div>
        <nav className="nav">
          {groups.map(group => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.items.map(item => {
                const Icon = item.icon
                return (
                  <NavLink key={item.to} to={item.to} end={item.end}
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Icon size={17} />
                    <span>{item.label}</span>
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="side-status">
            <span className={`dot ${run?.validation?.passed ? 'green' : run ? 'amber' : 'gray'}`} />
            <div>
              <strong>{run ? run.status_zh : '等待首次求解'}</strong>
              <span>{run ? `独立校验${run.validation?.passed ? '通过' : '未通过'}` : '选择场景后开始'}</span>
            </div>
          </div>
          <p>V0.1 原型 · 模拟数据</p>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="scenario-switch">
            <label>当前场景</label>
            <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}>
              {scenarios.map(s => <option key={s.id} value={s.id}>{s.id} · {s.name.replace(/^[A-G] · /, '')}</option>)}
            </select>
            {loading && <Spinner />}
          </div>
          <div className="topbar-right">
            {isStale && <span className="stale-chip">数据已修改，课表待重算</span>}
            {run ? <StatusBadge status={run.solver_status} label={run.status_zh} /> : <StatusBadge status="unsolved" label="未求解" />}
            <button className="btn btn-primary" onClick={onSolve} disabled={solving || !scenario}>
              {solving ? <Spinner label="求解中" /> : <><PlayCircle size={16} />一键排课</>}
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>

      {toast && (
        <div className={`toast toast-${toast.kind}`} onClick={clearToast}>
          <span className="toast-dot" />
          <p>{toast.text}</p>
          <button onClick={clearToast} aria-label="关闭">×</button>
        </div>
      )}
    </div>
  )
}
