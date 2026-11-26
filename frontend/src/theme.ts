export const SUBJECT_COLORS: Record<string, { bg: string; fg: string; border: string }> = {
  语文: { bg: '#FFF1E7', fg: '#9A3412', border: '#FDBA74' },
  数学: { bg: '#EAF0FF', fg: '#1E40AF', border: '#93B4F8' },
  英语: { bg: '#E7F7F2', fg: '#0F766E', border: '#7DD3C7' },
  日语: { bg: '#E8F7FB', fg: '#0E7490', border: '#7DD3EA' },
  物理: { bg: '#F2ECFF', fg: '#6D28D9', border: '#C4B5FD' },
  历史: { bg: '#FFF5E5', fg: '#92400E', border: '#FCD34D' },
  生物: { bg: '#EAF8EC', fg: '#166534', border: '#86EFAC' },
  化学: { bg: '#FFF0F2', fg: '#9F1239', border: '#FDA4AF' },
  地理: { bg: '#E9F4FF', fg: '#075985', border: '#7DD3FC' },
  政治: { bg: '#F6EEFF', fg: '#7E22CE', border: '#D8B4FE' },
}

export const PHASE_COLORS: Record<string, { bg: string; fg: string; label: string }> = {
  elective: { bg: '#ECFDF5', fg: '#047857', label: '走班' },
  foreign: { bg: '#EFF6FF', fg: '#1D4ED8', label: '外语' },
  base: { bg: '#F8FAFC', fg: '#475569', label: '基础' },
}

export const KIND_LABELS: Record<string, string> = {
  admin_base: '行政班基础课',
  foreign: '外语走班',
  elective_first: '首选走班',
  elective_second: '再选走班',
}

export const BAND_LABELS: Record<string, string> = {
  base: '基础课',
  foreign: '外语',
  first: '首选段',
  second_a: '再选 A 段',
  second_b: '再选 B 段',
}

export const CONSTRAINT_LABELS: [string, string][] = [
  ['teacher_no_overlap', '教师同一时间只承担一个教学任务'],
  ['student_no_overlap', '学生同一时间只参加一门课程'],
  ['room_no_overlap', '教室同一时间只安排一个教学班'],
  ['room_capacity', '教学班人数不超过教室容量'],
  ['prescribed_hours', '每名学生满足规定课时'],
  ['teacher_unavailable', '不占用教师不可排时间'],
  ['forbid_non_teaching_slots', '不占用自习、周测和放假时段'],
  ['fixed_component_teacher', '同一教学班同一细分课程教师固定'],
  ['max_two_same_subject_per_day', '同一天同一科目最多两节'],
  ['math_lecture_practice_alternate', '数学正课与落实课按周内顺序交替'],
  ['physics_only_with_history', '物理只与历史进行同步走班'],
  ['foreign_only_with_foreign', '外语只与外语同步走班'],
  ['second_choice_max_three_subjects', '再选科目每段最多三科同步，禁止四科'],
]

export function subjectStyle(subject: string) {
  return SUBJECT_COLORS[subject] || { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' }
}
