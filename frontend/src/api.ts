import type {
  RunResult, RunSummary, Scenario, ScenarioSummary, Student, Teacher,
  TimetableResponse, ViewKey, EntityOption, Validation, CourseConfig,
} from './types'

export const API_ROOT = window.location.pathname.startsWith('/plugins/aiwish/') ? '/plugins/aiwish' : ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_ROOT + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    let message = `请求失败 (${res.status})`
    try {
      const body = await res.json()
      message = body.detail || body.message || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export const api = {
  scenarios: () => request<ScenarioSummary[]>('/api/scenarios'),
  scenario: (sid: string) => request<Scenario>(`/api/scenarios/${sid}`),
  resetScenario: (sid: string) => request<Scenario>(`/api/scenarios/${sid}/reset`, { method: 'POST' }),
  solve: (sid: string, options?: { time_limit_seconds?: number; num_workers?: number; weights?: Record<string, number> }) =>
    request<RunResult>(`/api/scenarios/${sid}/solve`, {
      method: 'POST',
      body: JSON.stringify(options || {}),
    }),
  run: (runId: string) => request<RunResult>(`/api/runs/${runId}`),
  runs: (sid: string) => request<RunSummary[]>(`/api/scenarios/${sid}/runs`),
  revalidate: (runId: string) => request<Validation>(`/api/runs/${runId}/validate`, { method: 'POST' }),
  entities: (runId: string, view: ViewKey) =>
    request<EntityOption[]>(`/api/runs/${runId}/entities?view=${view}`),
  timetable: (runId: string, view: ViewKey, entityId: string) =>
    request<TimetableResponse>(`/api/runs/${runId}/timetable?view=${view}&entity_id=${encodeURIComponent(entityId)}`),
  patchStudent: (sid: string, studentId: string, patch: Partial<Student>) =>
    request<Scenario>(`/api/scenarios/${sid}/students/${studentId}`, {
      method: 'PATCH', body: JSON.stringify(patch),
    }),
  patchTeacher: (sid: string, teacherId: string, patch: Partial<Teacher>) =>
    request<Scenario>(`/api/scenarios/${sid}/teachers/${teacherId}`, {
      method: 'PATCH', body: JSON.stringify(patch),
    }),
  patchRoom: (sid: string, roomId: string, patch: { capacity?: number; name?: string; building?: string }) =>
    request<Scenario>(`/api/scenarios/${sid}/rooms/${roomId}`, {
      method: 'PATCH', body: JSON.stringify(patch),
    }),
  putRules: (sid: string, values: Record<string, unknown>) =>
    request<Scenario>(`/api/scenarios/${sid}/rules`, {
      method: 'PUT', body: JSON.stringify({ values }),
    }),
  putCourseConfig: (sid: string, config: CourseConfig) =>
    request<Scenario>(`/api/scenarios/${sid}/course-config`, {
      method: 'PUT', body: JSON.stringify(config),
    }),
  putTimeModel: (sid: string, slots: unknown[]) =>
    request<Scenario>(`/api/scenarios/${sid}/time-model`, {
      method: 'PUT', body: JSON.stringify({ slots }),
    }),
  putTeacherBindings: (sid: string, bindings: Record<string, string>) =>
    request<Scenario>(`/api/scenarios/${sid}/teacher-bindings`, {
      method: 'PATCH', body: JSON.stringify({ bindings }),
    }),
}

export function downloadUrl(path: string) {
  window.open(API_ROOT + path, '_blank')
}
