export type ViewKey = 'admin' | 'student' | 'teacher' | 'room' | 'class'

export interface Student {
  id: string
  name: string
  admin_class: string
  language: string
  first_subject: string
  second_subjects: string[]
}

export interface Teacher {
  id: string
  name: string
  subject: string
  unavailable_slots: string[]
  candidate_subjects?: string[]
  max_weekly_periods?: number | null
}

export interface Room {
  id: string
  name: string
  capacity: number
  building: string
}

export interface CourseComponent {
  name: string
  hours: number
  kind: string
}

export type CourseConfig = Record<string, CourseComponent[]>

export interface TimeSlot {
  index: number
  day_index: number
  day: string
  period: number
  label: string
  active: boolean
  activity: string
  phase: string | null
  band: string | null
}

export interface TimeModel {
  name: string
  days: string[]
  periods_per_day: number
  assumption: string
  slots: TimeSlot[]
}

export interface Rules {
  [key: string]: unknown
  walk_group_admin_class_cap: number
  weights: Record<string, number>
  time_limit_seconds: number
  random_seed: number
  num_workers: number
  enabled_hard_constraints: string[]
}

export interface Analysis {
  student_count: number
  teacher_count: number
  room_count: number
  admin_class_count: number
  admin_class_sizes: Record<string, number>
  first_subject_counts: Record<string, number>
  second_subject_counts: Record<string, number>
  language_counts: Record<string, number>
  combination_count: number
  combinations: { language: string; first: string; seconds: string[]; count: number }[]
  teacher_counts: Record<string, number>
  elective_capacity_estimate: Record<string, { enrollment: number; teachers: number; sections_at_60: number }>
  capacity_warnings: string[]
  time_model_summary: {
    active_slots: number
    grid_slots: number
    phases: Record<string, number>
    assumption: string
  }
}

export interface Scenario {
  id: string
  name: string
  description: string
  seed: number
  notes: string
  assumption_tags: string[]
  time_model: TimeModel
  course_config: CourseConfig
  students: Student[]
  teachers: Teacher[]
  rooms: Room[]
  rules: Rules
  analysis: Analysis
  teacher_bindings?: Record<string, string>
  updated_at?: string
  _updated_at?: string
  latest_run?: {
    run_id: string
    status: string
    solver_status: string
    validation_passed: boolean | null
    is_stale: boolean
  } | null
}

export interface ScenarioSummary {
  id: string
  name: string
  description: string
  seed: number
  students: number
  teachers: number
  rooms: number
  admin_classes: number
  kind: string
  notes: string
  updated_at?: string
  student_count: number
  teacher_count: number
  room_count: number
  admin_class_count: number
  latest_run?: Scenario['latest_run']
}

export interface Task {
  id: string
  class_id: string
  class_name: string
  subject: string
  component: string
  kind: string
  sequence: number
  phase: string
  band: string
  student_ids: string[]
  admin_classes: string[]
  teacher_id: string
  teacher_name?: string
  room_id: string
  room_name?: string
  allowed_slots: string[]
  slot_label: string
  slot_index: number
  day: string
  day_index: number
  period: number
  activity: string
  is_elective: boolean
}

export interface ClassGroup {
  id: string
  name: string
  subject: string
  kind: string
  phase: string
  band: string
  student_ids: string[]
  admin_classes: string[]
  teacher_id: string
  teacher_name?: string
  room_id: string
  room_name?: string
  components: CourseComponent[]
  task_ids: string[]
  required_hours: number
  size: number
  is_merged: boolean
  note: string
  student_count?: number
}

export interface ValidationSummary {
  student_time_conflicts: number
  teacher_time_conflicts: number
  room_time_conflicts: number
  student_missing_hours: number
  room_capacity_violations: number
  teacher_unavailable_violations: number
  daily_limit_violations: number
  math_alternation_violations: number
  walk_rule_violations: number
  view_inconsistencies: number
  invalid_slots: number
  hard_constraint_violations: number
  passed: boolean
  [key: string]: number | boolean
}

export interface Validation {
  passed: boolean
  summary: ValidationSummary
  violation_counts: Record<string, number>
  violations: { code: string; category: string; scope: string; message: string }[]
  warnings: string[]
  checked: Record<string, number>
  view_counts: Record<string, number>
}

export interface Metrics {
  student_count: number
  teacher_count: number
  room_count: number
  admin_class_count: number
  teaching_class_count: number
  base_class_count: number
  foreign_class_count: number
  elective_class_count: number
  merged_class_count: number
  merged_elective_class_count: number
  walking_student_count: number
  walking_student_ratio: number
  student_walk_transitions: number
  teacher_idle_periods: number
  teacher_idle_teacher_days: number
  avg_class_size: number
  min_class_size: number
  max_class_size: number
  elective_band_subjects: Record<string, string[]>
  weekly_task_count: number
  scheduled_slots: number
  total_student_lessons: number
  room_utilization: number
  [key: string]: unknown
}

export interface RunResult {
  run_id: string
  scenario_id: string
  scenario_name: string
  seed: number
  created_at: string
  status: 'solved' | 'infeasible' | 'timeout' | 'error' | string
  solver_status: string
  status_zh: string
  message: string
  solve_seconds: number
  build_seconds: number
  total_seconds: number
  objective_value?: number | null
  model_stats?: { variables: number; constraints: number; hints: number }
  metrics: Metrics
  classes: ClassGroup[]
  tasks: Task[]
  pools: Record<string, string[]>
  validation?: Validation | null
  precheck?: { code: string; details: Record<string, unknown> }
  is_stale?: boolean
  solve_options?: Record<string, unknown>
  scenario_summary?: { id: string; name: string; description: string; seed: number; students: number; teachers: number; rooms: number }
}

export interface RunSummary {
  run_id: string
  status: string
  solver_status: string
  created_at: string
  is_stale: boolean
  solve_seconds: number
  message: string
  metrics: Metrics
  validation_passed: boolean | null
}

export interface TimetableTask {
  id: string
  class_id: string
  class_name: string
  subject: string
  component: string
  kind: string
  teacher_id: string
  teacher_name: string
  room_id: string
  room_name: string
  student_count: number
  student_names: string[]
  admin_classes: string[]
  is_elective: boolean
  band: string
}

export interface TimetableCell {
  day_index: number
  day: string
  period: number
  label: string
  active: boolean
  activity: string
  phase: string | null
  band: string | null
  tasks: TimetableTask[]
}

export interface TimetableResponse {
  view: ViewKey
  entity_id: string
  entity: Record<string, unknown>
  days: string[]
  periods: number[]
  cells: TimetableCell[]
  task_count: number
}

export interface EntityOption {
  id: string
  name: string
  [key: string]: unknown
}
