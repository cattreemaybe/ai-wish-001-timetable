import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Clock3, Cpu, ExternalLink, Gauge, PlayCircle, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, EmptyState, PageHeader, Spinner, StatusBadge, ValidationGrid } from '../components/UI'

const STATUS_ROWS = [
  ['OPTIMAL', '已找到最优解', '在设定目标下由 CP-SAT 证明最优'],
  ['FEASIBLE', '已找到可行解', '满足全部已启用硬约束，但未证明最优'],
  ['INFEASIBLE', '已证明无解', '模型本身不可满足，不能等同于超时'],
  ['UNKNOWN', '超时且未找到可行解', '时间用尽；不代表无解'],
  ['MODEL_INVALID', '模型或数据错误', '数据、容量或时段配置有误'],
  ['PRECHECK_INFEASIBLE', '数据预检证明无解', '建班前即由容量/教师数量证明不可行'],
]

export default function Solve() {
  const { scenario, run, runs, solve, solving, refreshRuns, notify } = useApp()
  const [timeLimit, setTimeLimit] = useState(30)
  const [workers, setWorkers] = useState(8)
  const [weights, setWeights] = useState<Record<string, number>>({})

  useEffect(() => {
    if (scenario) {
      setTimeLimit(Number(scenario.rules.time_limit_seconds) || 30)
      setWorkers(Number(scenario.rules.num_workers) || 8)
      setWeights({ ...(scenario.rules.weights || {}) })
    }
  }, [scenario?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!scenario) return <div className="loading-block">正在加载场景…</div>

  const onSolve = async () => {
    await solve({ time_limit_seconds: timeLimit, num_workers: workers, weights })
    await refreshRuns()
  }

  const saveDefaults = async () => {
    try {
      await api.putRules(scenario.id, { time_limit_seconds: timeLimit, num_workers: workers, weights })
      notify('success', '求解参数已保存到当前场景')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
      <PageHeader eyebrow="求解器" title="自动排课与求解状态"
        description="教学班划分、教师/教室预分配后，由 OR-Tools CP-SAT 真实求解时间安排。超时不会被标记为无解。"
        actions={<button className="btn btn-primary" onClick={onSolve} disabled={solving}>
          {solving ? <Spinner label="CP-SAT 求解中" /> : <><PlayCircle size={16} />运行求解</>}
        </button>} />

      <div className="two-col wide-left">
        <Card title="开始排课" subtitle="默认参数已经适合大多数学校；高级选项通常不需要修改。">
          <div className="solve-cta">
            <div>
              <strong>准备好后，直接生成课表</strong>
              <p>系统会先检查数据、划分教学班，再调用 CP-SAT 并执行独立校验。</p>
            </div>
            <button className="btn btn-primary" onClick={onSolve} disabled={solving}>
              {solving ? <Spinner label="排课中" /> : <><PlayCircle size={16} />开始自动排课</>}
            </button>
          </div>
          <details className="advanced-settings">
            <summary><SlidersHorizontal size={15} />高级算法参数（一般无需修改）</summary>
            <div className="form-grid">
              <label className="field">
                <span>时间上限（秒）</span>
                <input type="number" min={1} max={300} value={timeLimit} onChange={e => setTimeLimit(Number(e.target.value))} />
                <small>到达上限且未找到解时标记为 UNKNOWN，不标记为无解。</small>
              </label>
              <label className="field">
                <span>并行 worker</span>
                <input type="number" min={1} max={32} value={workers} onChange={e => setWorkers(Number(e.target.value))} />
                <small>多 worker 可加速，但结果可能受调度时序影响。</small>
              </label>
            </div>
            <div className="weights-panel">
              <div className="mini-title"><SlidersHorizontal size={15} /> 软约束权重</div>
              <div className="weights-grid">
                {[
                  ['lecture_before_practice', '先正课后落实'],
                  ['teacher_idle', '减少教师空堂'],
                  ['student_walk', '减少学生走班'],
                  ['merge_small_classes', '合并小班'],
                  ['minimize_teaching_classes', '减少教学班'],
                  ['prefer_two_subject_walk', '优先两科走班'],
                ].map(([key, label]) => (
                  <label key={key} className="weight-field">
                    <span>{label}</span>
                    <input type="number" min={0} max={20} step={0.5} value={Number(weights[key] ?? 0)}
                      onChange={e => setWeights(w => ({ ...w, [key]: Number(e.target.value) }))} />
                  </label>
                ))}
              </div>
              <p className="form-note">这些是算法优化偏好，不是业务硬约束。普通排课保持默认即可。</p>
            </div>
            <div className="form-actions">
              <button className="btn btn-ghost" onClick={saveDefaults}>保存为场景默认参数</button>
            </div>
          </details>
        </Card>

        <Card title="求解结果" subtitle="最近一次运行">
          {run ? (
            <div className="result-panel">
              <div className="result-status">
                <StatusBadge status={run.solver_status} label={run.status_zh} />
                <span className="muted">{new Date(run.created_at).toLocaleString('zh-CN')}</span>
              </div>
              <p className="result-message">{run.message}</p>
              <div className="result-kpis">
                <div><Clock3 size={16} /><span>求解耗时</span><strong>{run.solve_seconds.toFixed(2)}s</strong></div>
                <div><Cpu size={16} /><span>变量 / 约束</span><strong>{run.model_stats ? `${run.model_stats.variables} / ${run.model_stats.constraints}` : '—'}</strong></div>
                <div><Gauge size={16} /><span>目标值</span><strong>{run.objective_value ?? '—'}</strong></div>
                <div><Activity size={16} /><span>状态</span><strong>{run.solver_status}</strong></div>
              </div>
              {run.validation && (
                <div className="inline-success">
                  <CheckCircle2 size={16} />
                  <span>独立校验 {run.validation.checked.tasks} 个任务：{run.validation.passed ? '全部通过' : '存在违规'}</span>
                  <Badge tone={run.validation.passed ? 'green' : 'red'}>{run.validation.summary.hard_constraint_violations} 违规</Badge>
                </div>
              )}
              {run.status === 'infeasible' && (
                <div className="inline-warning">
                  <AlertTriangle size={16} />
                  <span>{run.message} 未放宽任何硬约束。</span>
                </div>
              )}
              {run.validation && <ValidationGrid validation={run.validation} />}
              {run.status === 'solved' && (
                <div className="result-next">
                  <span>下一步</span>
                  <Link className="btn btn-sm btn-ghost" to="/timetable/admin"><ExternalLink size={14} />查看行政班课表</Link>
                  <Link className="btn btn-sm btn-ghost" to="/timetable/student"><ExternalLink size={14} />查看学生课表</Link>
                  <Link className="btn btn-sm btn-primary" to="/excel">导出 Excel</Link>
                </div>
              )}
            </div>
          ) : (
            <EmptyState title="尚未生成课表" description="点击“运行求解”，系统会先建班、再调用 CP-SAT、最后执行独立校验。" />
          )}
        </Card>
      </div>

      <div className="two-col">
        <Card title="求解状态语义" subtitle="严格区分可行、最优、无解和超时">
          <div className="status-table">
            {STATUS_ROWS.map(([code, label, desc]) => (
              <div key={code} className="status-row">
                <code>{code}</code>
                <strong>{label}</strong>
                <span>{desc}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="运行记录" subtitle="同一场景的历史求解快照">
          {runs.length ? (
            <div className="run-list">
              {runs.slice(0, 8).map(r => (
                <div key={r.run_id} className="run-row">
                  <StatusBadge status={r.solver_status} label={r.status === 'solved' ? '可行' : r.status === 'infeasible' ? '无解' : r.status === 'timeout' ? '超时' : '错误'} />
                  <div>
                    <strong>{r.run_id}</strong>
                    <span>{new Date(r.created_at).toLocaleString('zh-CN')} · {r.solve_seconds.toFixed(2)}s</span>
                  </div>
                  {r.is_stale && <Badge tone="amber">数据已变更</Badge>}
                </div>
              ))}
            </div>
          ) : <EmptyState title="暂无运行记录" />}
        </Card>
      </div>
    </>
  )
}
