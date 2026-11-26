import {
  ArrowRight, BookOpenCheck, CheckCircle2, Clock3, DoorOpen, GitBranch,
  PlayCircle, ShieldCheck, Sparkles, TriangleAlert, UserRound, UsersRound,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'
import { subjectStyle } from '../theme'
import { Badge, Card, EmptyState, MetricCard, PageHeader, StatusBadge, ValidationGrid } from '../components/UI'
import PreparationPanel from '../components/PreparationPanel'

function pct(n: number) {
  return `${Math.round(n * 100)}%`
}

export default function Dashboard() {
  const { scenario, run, solve, solving, isStale } = useApp()
  if (!scenario) return <div className="loading-block">正在加载场景…</div>
  const a = scenario.analysis
  const metrics = run?.metrics
  const topCombos = a.combinations.slice(0, 8)
  const maxCombo = Math.max(1, ...topCombos.map(x => x.count))

  return (
    <>
      <PageHeader
        eyebrow={`AI-WISH-001 / 场景 ${scenario.id}`}
        title="新高考智能走班排课工作台"
        description="用真实约束求解器生成课表，再由独立校验器复核学生、教师、教室与走班规则。"
        actions={<>
          <Link className="btn btn-ghost" to="/rules">查看规则</Link>
          <button className="btn btn-primary" onClick={() => solve()} disabled={solving}>
            {solving ? '求解中…' : <><PlayCircle size={16} />开始自动排课</>}
          </button>
        </>}
      />

      <section className="hero-card">
        <div className="hero-glow" />
        <div className="hero-main">
          <div className="hero-kicker"><Sparkles size={14} /> 当前演示场景</div>
          <h2>{scenario.name}</h2>
          <p>{scenario.description}</p>
          <div className="hero-tags">
            <span>{a.student_count} 名学生</span>
            <span>{a.admin_class_count} 个行政班</span>
            <span>{a.combination_count} 种选科组合</span>
            <span>种子 {scenario.seed}</span>
          </div>
        </div>
        <div className="hero-side">
          <div className="hero-status-label">最近求解</div>
          {run ? (
            <>
              <StatusBadge status={run.solver_status} label={run.status_zh} />
              <div className="hero-time"><Clock3 size={15} /> {run.solve_seconds.toFixed(2)} 秒</div>
              {isStale && <div className="hero-stale">数据已修改，当前课表为旧版本</div>}
            </>
          ) : <div className="hero-time">尚未求解</div>}
          <div className="hero-foot">
            <ShieldCheck size={15} />
            <span>校验 {run?.validation?.passed ? '全部通过' : run ? '未通过' : '待执行'}</span>
          </div>
        </div>
      </section>

      <PreparationPanel compact />

      <div className="metrics-grid">
        <MetricCard label="学生" value={a.student_count} hint={`${a.admin_class_count} 个行政班`} icon={<UsersRound size={18} />} />
        <MetricCard label="教师" value={a.teacher_count} hint="10 个学科" icon={<UserRound size={18} />} tone="teal" />
        <MetricCard label="教室" value={a.room_count} hint="30 / 45 / 60 座" icon={<DoorOpen size={18} />} />
        <MetricCard label="教学班" value={metrics?.teaching_class_count ?? '—'} hint={run ? `合班 ${metrics?.merged_class_count ?? 0} 个` : '求解后生成'} icon={<BookOpenCheck size={18} />} tone="violet" />
        <MetricCard label="走班学生" value={metrics ? metrics.walking_student_count : '—'} hint={metrics ? `${pct(metrics.walking_student_ratio)} 覆盖` : '按教学班重组计算'} icon={<GitBranch size={18} />} tone="amber" />
        <MetricCard label="教师空堂" value={metrics ? metrics.teacher_idle_periods : '—'} hint="目标：尽量压缩" icon={<Clock3 size={18} />} />
      </div>

      <div className="two-col">
        <Card title="硬约束校验" subtitle="来自独立校验器，不复用求解器判断"
          actions={<Link className="text-link" to="/validation">完整报告 <ArrowRight size={14} /></Link>}>
          {run?.validation ? (
            <>
              <div className="validation-banner">
                <div className={`round-check ${run.validation.passed ? 'ok' : 'bad'}`}>
                  {run.validation.passed ? <CheckCircle2 size={24} /> : <TriangleAlert size={24} />}
                </div>
                <div>
                  <strong>{run.validation.passed ? '全部硬约束通过' : '存在硬约束违规'}</strong>
                  <p>共复核 {run.validation.checked.tasks} 个任务、{run.validation.checked.students} 名学生、{run.validation.checked.teachers} 名教师。</p>
                </div>
                <Badge tone={run.validation.passed ? 'green' : 'red'}>{run.validation.summary.hard_constraint_violations} 违规</Badge>
              </div>
              <ValidationGrid validation={run.validation} />
            </>
          ) : (
            <EmptyState title="还没有可校验的课表" description="运行自动排课后，系统会自动调用独立校验器。"
              action={<button className="btn btn-primary" onClick={() => solve()} disabled={solving}>开始排课</button>} />
          )}
        </Card>

        <Card title="选科结构" subtitle="首选、再选与外语分布"
          actions={<Link className="text-link" to="/students">学生数据 <ArrowRight size={14} /></Link>}>
          <div className="structure-grid">
            <div>
              <div className="mini-title">首选科目</div>
              {Object.entries(a.first_subject_counts).map(([subject, count]) => (
                <div className="bar-row" key={subject}>
                  <span className="bar-label" style={{ color: subjectStyle(subject).fg }}>{subject}</span>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${count / Math.max(1, a.student_count) * 100}%`, background: subjectStyle(subject).fg }} /></div>
                  <span className="bar-value">{count}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="mini-title">外语</div>
              {Object.entries(a.language_counts).sort((x, y) => y[1] - x[1]).map(([subject, count]) => (
                <div className="bar-row" key={subject}>
                  <span className="bar-label" style={{ color: subjectStyle(subject).fg }}>{subject}</span>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${count / Math.max(1, a.student_count) * 100}%`, background: subjectStyle(subject).fg }} /></div>
                  <span className="bar-value">{count}</span>
                </div>
              ))}
            </div>
          </div>
          {a.capacity_warnings.length > 0 && (
            <div className="inline-warning"><TriangleAlert size={15} /><span>{a.capacity_warnings[0]}</span></div>
          )}
        </Card>
      </div>

      {run?.status === 'solved' && metrics ? (
        <div className="two-col wide-left">
          <Card title="教学班与走班" subtitle="教学班划分结果，合并班表示跨行政班合班">
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>教学班</th><th>科目</th><th>人数</th><th>行政班</th><th>走班段</th><th>教师 / 教室</th></tr></thead>
                <tbody>
                  {run.classes.filter(c => c.kind.startsWith('elective')).slice(0, 9).map(c => (
                    <tr key={c.id}>
                      <td><strong>{c.name}</strong>{c.is_merged && <Badge tone="blue">合班</Badge>}</td>
                      <td><span className="subject-dot" style={{ background: subjectStyle(c.subject).fg }} />{c.subject}</td>
                      <td>{c.size}</td>
                      <td className="muted">{c.admin_classes.join('、')}</td>
                      <td><Badge tone="neutral">{c.band === 'first' ? '首选段' : c.band === 'second_a' ? '再选 A' : '再选 B'}</Badge></td>
                      <td className="muted">{c.teacher_name} · {c.room_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Link className="text-link block-link" to="/classes">查看全部 {run.classes.length} 个教学班 <ArrowRight size={14} /></Link>
          </Card>

          <Card title="走班结构" subtitle="求解后的走班与资源指标">
            <div className="stat-list">
              <div><span>学生走班总人次</span><strong>{metrics.student_walk_transitions}</strong></div>
              <div><span>合班教学班</span><strong>{metrics.merged_class_count}</strong></div>
              <div><span>再选走班教学班</span><strong>{metrics.merged_elective_class_count}</strong></div>
              <div><span>平均教学班人数</span><strong>{metrics.avg_class_size}</strong></div>
              <div><span>排课任务</span><strong>{metrics.weekly_task_count}</strong></div>
              <div><span>覆盖时段</span><strong>{metrics.scheduled_slots} / 31</strong></div>
            </div>
            <div className="band-list">
              {Object.entries(metrics.elective_band_subjects).map(([band, subjects]) => (
                <div key={band} className="band-item">
                  <span>{band === 'first' ? '首选段' : band === 'second_a' ? '再选 A 段' : '再选 B 段'}</span>
                  <div>{subjects.map(s => <em key={s} style={{ background: subjectStyle(s).bg, color: subjectStyle(s).fg }}>{s}</em>)}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : (
        <Card title="场景数据概览" subtitle={run?.status === 'infeasible' ? '该场景被证明无解，未生成课表' : '运行求解后查看教学班与走班结果'}>
          {run?.status === 'infeasible' ? (
            <div className="infeasible-panel">
              <TriangleAlert size={28} />
              <div>
                <strong>{run.status_zh}</strong>
                <p>{run.message}</p>
                <p className="muted">系统没有放宽任何硬约束。请在资源、规则或数据中调整后重新求解。</p>
              </div>
            </div>
          ) : (
            <div className="overview-strip">
              <div><span>行政班规模</span><strong>{Object.values(a.admin_class_sizes)[0] || 0} 人 / 班</strong></div>
              <div><span>再选科目</span><strong>{Object.keys(a.second_subject_counts).length} 科</strong></div>
              <div><span>教学时段</span><strong>{a.time_model_summary.active_slots} 节</strong></div>
              <div><span>走班段</span><strong>3 段</strong></div>
              <div><span>教室容量</span><strong>30 / 45 / 60</strong></div>
            </div>
          )}
        </Card>
      )}

      <div className="two-col">
        <Card title="高频选科组合" subtitle="按学生人数排序的 Top 8">
          <div className="combo-list">
            {topCombos.map((c, i) => (
              <div className="combo-row" key={`${c.language}-${c.first}-${c.seconds.join('')}-${i}`}>
                <span className="combo-name">
                  <em>{c.language}</em>{c.first} + {c.seconds.join(' + ')}
                </span>
                <div className="combo-track"><div style={{ width: `${c.count / maxCombo * 100}%` }} /></div>
                <strong>{c.count}</strong>
              </div>
            ))}
          </div>
        </Card>
        <Card title="演示路径" subtitle="从数据到可验证课表">
          <div className="steps">
            <Link to="/students"><span>01</span><div><strong>检查选科数据</strong><p>24 种组合、班内走班与外语分组</p></div><ArrowRight size={16} /></Link>
            <Link to="/solve"><span>02</span><div><strong>运行 CP-SAT 求解</strong><p>分阶段建班、资源预分配、时间求解</p></div><ArrowRight size={16} /></Link>
            <Link to="/validation"><span>03</span><div><strong>独立校验</strong><p>冲突、课时、容量、四视图一致性</p></div><ArrowRight size={16} /></Link>
            <Link to="/timetable/admin"><span>04</span><div><strong>查看四类课表</strong><p>行政班、学生、教师、教室</p></div><ArrowRight size={16} /></Link>
          </div>
        </Card>
      </div>
    </>
  )
}
