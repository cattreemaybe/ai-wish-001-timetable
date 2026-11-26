import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { RunResult, RunSummary, Scenario, ScenarioSummary } from './types'

interface Toast { id: number; kind: 'success' | 'error' | 'info'; text: string }

interface AppContextValue {
  scenarios: ScenarioSummary[]
  scenarioId: string
  setScenarioId: (id: string) => void
  scenario: Scenario | null
  run: RunResult | null
  runs: RunSummary[]
  loading: boolean
  solving: boolean
  error: string
  toast: Toast | null
  isStale: boolean
  refreshScenario: () => Promise<void>
  refreshRun: () => Promise<void>
  refreshRuns: () => Promise<void>
  solve: (options?: { time_limit_seconds?: number; num_workers?: number; weights?: Record<string, number> }) => Promise<void>
  createCustomScenario: (name?: string) => Promise<Scenario>
  setScenario: (scenario: Scenario) => void
  notify: (kind: Toast['kind'], text: string) => void
  clearToast: () => void
}

const Ctx = createContext<AppContextValue | null>(null)
const STORAGE_KEY = 'aiwish.selectedScenario'

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [scenarioId, setScenarioIdState] = useState<string>(() => localStorage.getItem(STORAGE_KEY) || 'F')
  const [scenario, setScenarioState] = useState<Scenario | null>(null)
  const [run, setRun] = useState<RunResult | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [solving, setSolving] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState<Toast | null>(null)
  const requestSeq = useRef(0)
  const toastSeq = useRef(0)

  const notify = useCallback((kind: Toast['kind'], text: string) => {
    toastSeq.current += 1
    setToast({ id: toastSeq.current, kind, text })
    window.setTimeout(() => setToast(t => (t && t.id === toastSeq.current ? null : t)), 4200)
  }, [])

  const loadScenario = useCallback(async (id: string) => {
    const seq = ++requestSeq.current
    setLoading(true)
    setError('')
    try {
      const [sc, runList] = await Promise.all([api.scenario(id), api.runs(id)])
      if (seq !== requestSeq.current) return
      setScenarioState(sc)
      setRuns(runList)
      let latest: RunResult | null = null
      const runId = sc.latest_run?.run_id || runList[0]?.run_id
      if (runId) {
        try { latest = await api.run(runId) } catch { latest = null }
      }
      if (seq !== requestSeq.current) return
      setRun(latest)
    } catch (e) {
      if (seq !== requestSeq.current) return
      setError(e instanceof Error ? e.message : String(e))
      setScenarioState(null)
      setRun(null)
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api.scenarios()
      .then(list => {
        if (cancelled) return
        setScenarios(list)
        const wanted = list.find(x => x.id === scenarioId) ? scenarioId : (list.find(x => x.id === 'F')?.id || list[0]?.id || 'F')
        setScenarioIdState(wanted)
        localStorage.setItem(STORAGE_KEY, wanted)
      })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!scenarios.length) return
    loadScenario(scenarioId)
  }, [scenarioId, scenarios.length, loadScenario])

  const setScenarioId = useCallback((id: string) => {
    setScenarioIdState(id)
    localStorage.setItem(STORAGE_KEY, id)
  }, [])

  const refreshScenario = useCallback(async () => {
    const sc = await api.scenario(scenarioId)
    setScenarioState(sc)
    if (sc.latest_run?.run_id) {
      try { setRun(await api.run(sc.latest_run.run_id)) } catch { /* keep current */ }
    }
    setRuns(await api.runs(scenarioId))
  }, [scenarioId])

  const refreshRun = useCallback(async () => {
    if (!run) return
    setRun(await api.run(run.run_id))
    setRuns(await api.runs(scenarioId))
  }, [run, scenarioId])

  const refreshRuns = useCallback(async () => {
    setRuns(await api.runs(scenarioId))
  }, [scenarioId])

  const createCustomScenario = useCallback(async (name?: string) => {
    const created = await api.createCustom(name)
    const list = await api.scenarios()
    setScenarios(list)
    setScenarioIdState(created.id)
    localStorage.setItem(STORAGE_KEY, created.id)
    setScenarioState(created)
    setRun(null)
    setRuns([])
    return created
  }, [])

  const solve = useCallback(async (options?: { time_limit_seconds?: number; num_workers?: number; weights?: Record<string, number> }) => {
    if (!scenario) return
    setSolving(true)
    setError('')
    try {
      const result = await api.solve(scenario.id, {
        time_limit_seconds: options?.time_limit_seconds ?? (Number(scenario.rules.time_limit_seconds) || 30),
        num_workers: options?.num_workers ?? (Number(scenario.rules.num_workers) || 8),
        weights: options?.weights ?? scenario.rules.weights,
      })
      setRun(result)
      await refreshScenario()
      notify(result.status === 'solved' ? 'success' : result.status === 'infeasible' ? 'error' : 'info',
        result.status === 'solved' ? `求解完成：${result.solver_status}，独立校验${result.validation?.passed ? '通过' : '未通过'}` : result.message)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setError(message)
      notify('error', message)
    } finally {
      setSolving(false)
    }
  }, [scenario, refreshScenario, notify])

  const value = useMemo<AppContextValue>(() => ({
    scenarios, scenarioId, setScenarioId, scenario, run, runs, loading, solving, error,
    toast, isStale: Boolean(scenario?.latest_run?.is_stale || run?.is_stale),
    refreshScenario, refreshRun, refreshRuns, solve, createCustomScenario,
    setScenario: setScenarioState,
    notify, clearToast: () => setToast(null),
  }), [scenarios, scenarioId, setScenarioId, scenario, run, runs, loading, solving, error,
    toast, refreshScenario, refreshRun, refreshRuns, solve, createCustomScenario, notify])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp() {
  const value = useContext(Ctx)
  if (!value) throw new Error('useApp 必须在 AppProvider 内使用')
  return value
}
