import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight, BookOpenCheck, CheckCircle2, CircleAlert, CircleDashed, DoorOpen,
  GraduationCap, PlayCircle, Settings2, ShieldCheck, Sparkles, UserRound, UsersRound,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { PreflightItem, PreflightResult, Scenario } from '../types'
import { Badge, Spinner } from './UI'

type Step = {
  key: string
  title: string
  desc: string
  link: string
  icon: React.ReactNode
  status: 'ok' | 'warn' | 'error' | 'pending'
  value: string
  detail: string
}

function subjectHours(scenario: Scenario, subject: string) {
  return (scenario.course_config[subject] || []).reduce((sum, c) => sum + Number(c.hours || 0), 0)
}

function buildSteps(scenario: Scenario, preflight: PreflightResult | null): Step[] {
  const a = scenario.analysis
  const students = scenario.students
  const maxClass = Math.max(0, ...Object.values(a.admin_class_sizes))
  const maxRoom = Math.max(0, ...scenario.rooms.map(r => r.capacity))
  const requiredSubjects = new Set(['语文', '数学'])
  if (students.length) {
    students.forEach(s => {
      requiredSubjects.add(s.language)
      requiredSubjects.add(s.first_subject)
      s.second_subjects.forEach(x => requiredSubjects.add(x))
    })
  } else {
    ['英语', '日语', '物理', '历史', '生物', '化学', '地理', '政治'].forEach(x => requiredSubjects.add(x))
  }
  const missingTeachers = [...requiredSubjects].filter(s => !scenario.teachers.some(t => t.subject === s))
  const totalHours = students.length
    ? Math.min(...students.map(s => (
      subjectHours(scenario, '语文') + subjectHours(scenario, '数学') +
      subjectHours(scenario, s.language) + subjectHours(scenario, s.first_subject) +
      s.second_subjects.reduce((sum, sub) => sum + subjectHours(scenario, sub), 0)
    )))
    : 31
  const active = scenario.time_model.slots.filter(s => s.active).length
  const sample = Boolean(scenario.is_sample)
  const base: Step[] = [
    {
      key: 'students', title: '学生与选科', desc: '行政班、外语、首选、再选',
      link: '/students', icon: <UsersRound size={19} />,
      status: students.length ? 'ok' : 'error',
      value: `${students.length} 人`,
      detail: students.length ? `${a.admin_class_count} 个班 · ${a.combination_count} 种组合` : '还没有学生数据',
    },
    {
      key: 'teachers', title: '教师与任课', desc: '教师名单、科目、不可排时间',
      link: '/teachers', icon: <UserRound size={19} />,
      status: !scenario.teachers.length || missingTeachers.length ? 'error' : 'ok',
      value: `${scenario.teachers.length} 人`,
      detail: missingTeachers.length ? `缺少 ${missingTeachers.join('、')} 教师` : '教师资源已录入',
    },
    {
      key: 'rooms', title: '教室资源', desc: '容量与楼栋',
      link: '/rooms', icon: <DoorOpen size={19} />,
      status: !scenario.rooms.length ? 'error' : maxRoom < maxClass ? 'warn' : 'ok',
      value: `${scenario.rooms.length} 间`,
      detail: scenario.rooms.length ? `最大 ${maxRoom} 座` : '还没有教室数据',
    },
    {
      key: 'courses', title: '课程与课时', desc: '正课、落实课、细分课程',
      link: '/courses', icon: <BookOpenCheck size={19} />,
      status: totalHours === 31 ? 'ok' : 'error',
      value: `${totalHours} 节/周`,
      detail: totalHours === 31 ? '每名学生每周合计31节' : '课程课时合计不等于31节',
    },
    {
      key: 'time', title: '上课时间', desc: '教学时段、自习、周末安排',
      link: '/time-model', icon: <GraduationCap size={19} />,
      status: active === 31 ? 'ok' : 'error',
      value: `${active} 个时段`,
      detail: active === 31 ? '42格 · 31个教学时段' : '时间模型不完整',
    },
    {
      key: 'rules', title: '排课规则', desc: '硬约束、走班分组、软约束权重',
      link: '/rules', icon: <Settings2 size={19} />,
      status: 'ok',
      value: '已启用',
      detail: intCap(scenario) ? `走班组上限 ${intCap(scenario)} 个班` : '硬约束全部启用；走班组上限待确认',
    },
  ]
  if (!preflight) return base
  const byKey = new Map(preflight.items.map(i => [i.key, i]))
  return base.map(step => {
    const p = byKey.get(step.key) as PreflightItem | undefined
    return p ? { ...step, status: p.status, value: p.value, detail: p.detail } : step
  })
}

function intCap(scenario: Scenario) {
  return Number(scenario.rules.walk_group_admin_class_cap) || 0
}

function StatusIcon({ status }: { status: Step['status'] }) {
  if (status === 'ok') return <CheckCircle2 size={18} className="step-ok" />
  if (status === 'warn') return <CircleAlert size={18} className="step-warn" />
  if (status === 'error') return <CircleAlert size={18} className="step-error" />
  return <CircleDashed size={18} className="step-pending" />
}

export default function PreparationPanel({ compact = false }: { compact?: boolean }) {
  const { scenario, solve, solving, createCustomScenario, notify, setScenarioId } = useApp()
  const navigate = useNavigate()
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [creating, setCreating] = useState(false)

  useEffect(() => { setPreflight(null) }, [scenario?.id, scenario?._updated_at, scenario?.updated_at])

  const steps = useMemo(() => scenario ? buildSteps(scenario, preflight) : [], [scenario, preflight])
  if (!scenario) return null
  const okCount = steps.filter(s => s.status === 'ok').length
  const sample = Boolean(scenario.is_sample)

  const runCheck = async () => {
    setChecking(true)
    try {
      const result = await api.preflight(scenario.id)
      setPreflight(result)
      if (result.ready) notify('success', result.message)
      else notify('error', result.message)
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setChecking(false) }
  }

  const createOwn = async () => {
    setCreating(true)
    try {
      const created = await createCustomScenario()
      notify('success', `已创建「${created.name}」，请先导入或录入基础数据`)
      navigate('/prepare')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setCreating(false) }
  }

  const startSolve = async () => {
    let result = preflight
    if (!result) {
      setChecking(true)
      try {
        result = await api.preflight(scenario.id)
        setPreflight(result)
      } catch (e) {
        notify('error', e instanceof Error ? e.message : String(e))
        setChecking(false)
        return
      } finally { setChecking(false) }
    }
    if (!result.ready) {
      notify('error', result.message)
      return
    }
    await solve()
    navigate('/solve')
  }

  return (
    <section className={`prepare-panel ${compact ? 'compact' : ''}`}>
      <div className="prepare-head">
        <div>
          <div className="eyebrow"><Sparkles size={13} /> 排课准备</div>
          <h2>按顺序把数据准备好，再开始排课</h2>
          <p>不需要理解算法。先完成下面六项，点击“排课前检查”，通过后即可自动排课。</p>
        </div>
        <div className="prepare-progress">
          <div className="progress-ring" style={{ background: `conic-gradient(var(--teal) ${okCount / 6 * 360}deg, #e7edf3 0deg)` }}>
            <span>{okCount}<small>/6</small></span>
          </div>
          <div><strong>{okCount === 6 ? '准备完成' : '准备中'}</strong><span>{okCount === 6 ? '可以开始排课' : '还差几项'}</span></div>
        </div>
      </div>

      {sample && (
        <div className="sample-banner">
          <div><Badge tone="amber">示例数据</Badge><span>当前是模拟场景「{scenario.name}」，不是你的学校数据，只用于体验完整流程。</span></div>
          <button className="btn btn-sm btn-ghost" onClick={createOwn} disabled={creating}>
            {creating ? '创建中…' : '创建我的方案'}
          </button>
        </div>
      )}

      <div className="prepare-steps">
        {steps.map((step, idx) => (
          <Link className={`prepare-step ${step.status}`} to={step.link} key={step.key}>
            <div className="step-top">
              <span className="step-num">{String(idx + 1).padStart(2, '0')}</span>
              <span className="step-icon">{step.icon}</span>
              <StatusIcon status={step.status} />
            </div>
            <strong>{step.title}</strong>
            <p>{step.desc}</p>
            <div className="step-meta">
              <span>{step.value}</span>
              <em>{step.detail}</em>
            </div>
            <span className="step-link">去准备 <ArrowRight size={13} /></span>
          </Link>
        ))}
      </div>

      {preflight && (
        <div className={`preflight-result ${preflight.status}`}>
          <div className="preflight-icon">
            {preflight.ready ? (preflight.warnings.length ? <CircleAlert size={20} /> : <ShieldCheck size={20} />) : <CircleAlert size={20} />}
          </div>
          <div className="preflight-main">
            <strong>{preflight.message}</strong>
            {preflight.blocking.length > 0 ? (
              <ul>{preflight.blocking.slice(0, 4).map((x, i) => <li key={i}>{x}</li>)}</ul>
            ) : preflight.warnings.length > 0 ? (
              <ul>{preflight.warnings.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}</ul>
            ) : <p>学生、教师、教室、课程、时间和规则都已就绪。</p>}
          </div>
          <Badge tone={preflight.ready ? 'green' : 'red'}>{preflight.ready ? '可以排课' : '暂不能排课'}</Badge>
        </div>
      )}

      <div className="prepare-actions">
        <button className="btn btn-ghost" onClick={runCheck} disabled={checking}>
          {checking ? <Spinner label="检查中" /> : <><ShieldCheck size={16} />排课前检查</>}
        </button>
        <button className="btn btn-primary" onClick={startSolve} disabled={solving || !steps.some(s => s.key === 'students' && s.status !== 'error')}>
          {solving ? <Spinner label="排课中" /> : <><PlayCircle size={16} />自动排课</>}
        </button>
        <button className="btn btn-ghost" onClick={createOwn} disabled={creating}>
          {creating ? '创建中…' : sample ? '从示例切换到我的方案' : '新建另一个方案'}
        </button>
      </div>
      {sample && (
        <div className="prepare-sample-note">
          示例场景仍保留在顶部场景切换中，随时可以切回体验；创建自己的方案不会覆盖示例数据。
        </div>
      )}
    </section>
  )
}
