import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, FlaskConical, LockKeyhole, Scale, Save } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../context'
import { Badge, Card, PageHeader } from '../components/UI'
import { CONSTRAINT_LABELS } from '../theme'

const WEIGHT_LABELS: Record<string, string> = {
  lecture_before_practice: '先正课后落实',
  teacher_idle: '减少教师空堂',
  student_walk: '减少学生走班',
  merge_small_classes: '合并小班',
  minimize_teaching_classes: '减少教学班',
  prefer_two_subject_walk: '优先两科走班',
}

export default function Rules() {
  const { scenario, setScenario, notify } = useApp()
  const [cap, setCap] = useState(0)
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (scenario) {
      setCap(Number(scenario.rules.walk_group_admin_class_cap) || 0)
      setWeights({ ...(scenario.rules.weights || {}) })
    }
  }, [scenario?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!scenario) return <div className="loading-block">正在加载规则…</div>

  const save = async () => {
    setSaving(true)
    try {
      const updated = await api.putRules(scenario.id, {
        walk_group_admin_class_cap: cap,
        weights,
      })
      setScenario(updated)
      notify('success', '规则已保存；请重新求解以生成新结果')
    } catch (e) {
      notify('error', e instanceof Error ? e.message : String(e))
    } finally { setSaving(false) }
  }

  return (
    <>
      <PageHeader eyebrow="走班与规则" title="排课规则配置"
        description="需求中已确认的硬约束全部固定启用。待确认规则和软约束权重允许调整，但任何改动都不会静默放宽硬约束。"
        actions={<button className="btn btn-primary" onClick={save} disabled={saving}><Save size={15} />{saving ? '保存中…' : '保存规则'}</button>} />

      <div className="two-col wide-left">
        <Card title="已启用硬约束" subtitle="V0.1 不接受关闭；求解器和独立校验器同时检查">
          <div className="rule-list">
            {CONSTRAINT_LABELS.map(([key, label], idx) => (
              <div className="rule-row" key={key}>
                <span className="rule-index">{String(idx + 1).padStart(2, '0')}</span>
                <div><strong>{label}</strong><code>{key}</code></div>
                <Badge tone="green"><CheckCircle2 size={12} /> 强制</Badge>
                <LockKeyhole size={14} className="locked" />
              </div>
            ))}
          </div>
        </Card>

        <div className="stack">
          <Card title="待确认规则" subtitle="来源需求明确标注为“暂定/待确认”">
            <label className="field">
              <span>物理/历史走班组最多行政班数</span>
              <select value={cap} onChange={e => setCap(Number(e.target.value))}>
                <option value={0}>未启用（V0.1 默认，待用户确认）</option>
                <option value={2}>2 个行政班（严格按原文暂定值）</option>
              </select>
            </label>
            {cap === 0 ? (
              <div className="inline-warning"><AlertTriangle size={16} /><span>该规则在需求中标注“待确认”。默认关闭并在校验报告中记录为警告，不冒充已满足。</span></div>
            ) : (
              <div className="inline-warning"><AlertTriangle size={16} /><span>启用后作为硬约束校验。综合场景 F 可能因仅 3 名物理教师而无法同时开出 4 个物理教学班，届时会如实报告无解。</span></div>
            )}
            <div className="form-note">“再选科目每段最多三科、禁止四科”为已实现结构规则：按固定科目顺序拆 A/B 两段，每段天然最多三科。</div>
          </Card>

          <Card title="软约束权重" subtitle="保存后作为 CP-SAT 目标函数权重；部分指标由分班阶段决定">
            <div className="weights-grid">
              {Object.keys(WEIGHT_LABELS).map(key => (
                <label key={key} className="weight-field">
                  <span>{WEIGHT_LABELS[key]}</span>
                  <input type="number" min={0} max={20} step={0.5} value={Number(weights[key] ?? 0)}
                    onChange={e => setWeights(w => ({ ...w, [key]: Number(e.target.value) }))} />
                </label>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <Card title="规则来源与建模口径" subtitle="未确认的业务规则必须可追溯">
        <div className="rule-notes">
          <div><FlaskConical size={18} /><strong>数学交替</strong><p>按周内数学课时间顺序严格交替“正课-落实课”，首个数学任务从正课开始；求解器对 8 个任务的时段施加严格递增约束。</p></div>
          <div><Scale size={18} /><strong>每日上限</strong><p>同一学生同一天同一科目最多 2 节。对教学班整体施加上限，独立校验器再逐学生复核。</p></div>
          <div><AlertTriangle size={18} /><strong>走班组上限</strong><p>原文标注“暂按最多两个行政班建模，待确认”。V0.1 提供开关，默认不启用；启用后由建班阶段和校验器共同强制。</p></div>
          <div><CheckCircle2 size={18} /><strong>无解不降级</strong><p>CP-SAT 返回 INFEASIBLE、UNKNOWN 或预检容量不足时，系统分别报告“无解 / 超时未找到解 / 数据预检无解”，不生成假课表。</p></div>
        </div>
      </Card>
    </>
  )
}
