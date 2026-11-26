import React from 'react'
import { AlertTriangle, Check, Info, Loader2, X } from 'lucide-react'
import type { Validation } from '../types'

export function Card({ children, className = '', title, subtitle, actions }: {
  children: React.ReactNode
  className?: string
  title?: React.ReactNode
  subtitle?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function PageHeader({ eyebrow, title, description, actions }: {
  eyebrow?: string; title: string; description?: string; actions?: React.ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: {
  children: React.ReactNode
  tone?: 'neutral' | 'green' | 'red' | 'amber' | 'blue' | 'purple'
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const map: Record<string, string> = {
    solved: 'green', OPTIMAL: 'green', FEASIBLE: 'green',
    infeasible: 'red', INFEASIBLE: 'red', PRECHECK_INFEASIBLE: 'red',
    timeout: 'amber', UNKNOWN: 'amber', error: 'red', MODEL_INVALID: 'red',
    unsolved: 'neutral', UNSOLVED: 'neutral',
  }
  const tone = map[status] as 'green' | 'red' | 'amber' | 'neutral' | undefined
  return <span className={`status-badge status-${tone || 'neutral'}`}><i />{label || status}</span>
}

export function MetricCard({ label, value, hint, tone = 'default', icon }: {
  label: string; value: React.ReactNode; hint?: string; tone?: 'default' | 'teal' | 'amber' | 'violet'; icon?: React.ReactNode
}) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-top"><span>{label}</span>{icon}</div>
      <div className="metric-value">{value}</div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  )
}

export function Modal({ open, title, subtitle, onClose, children, footer, wide }: {
  open: boolean; title: string; subtitle?: string; onClose: () => void
  children: React.ReactNode; footer?: React.ReactNode; wide?: boolean
}) {
  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`}>
        <header>
          <div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>
          <button className="icon-btn" onClick={onClose} aria-label="关闭"><X size={18} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return <span className="spinner"><Loader2 size={18} className="spin" />{label}</span>
}

export function EmptyState({ title, description, action }: {
  title: string; description?: string; action?: React.ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-mark"><Info size={22} /></div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}

export function ValidationGrid({ validation }: { validation: Validation }) {
  const s = validation.summary
  const items: [string, number][] = [
    ['学生时间冲突', s.student_time_conflicts],
    ['教师时间冲突', s.teacher_time_conflicts],
    ['教室时间冲突', s.room_time_conflicts],
    ['学生课时缺失', s.student_missing_hours],
    ['教室超容量', s.room_capacity_violations],
    ['教师不可排时间', s.teacher_unavailable_violations],
    ['每日课时上限', s.daily_limit_violations],
    ['数学交替', s.math_alternation_violations],
    ['走班规则', s.walk_rule_violations],
    ['四视图一致性', s.view_inconsistencies],
    ['非法时段', s.invalid_slots],
  ]
  return (
    <div className="validation-grid">
      {items.map(([name, value]) => (
        <div key={name} className={`validation-item ${value === 0 ? 'ok' : 'bad'}`}>
          <span className="v-icon">{value === 0 ? <Check size={14} /> : <AlertTriangle size={14} />}</span>
          <span>{name}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  )
}
