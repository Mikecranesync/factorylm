import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const API_BASE = '/api'

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

// Workers
export function useWorkers() {
  return useQuery({
    queryKey: ['workers'],
    queryFn: () => fetchAPI<{ workers: Worker[]; count: number }>('/workers'),
  })
}

export function useWorkerTasks(worker: string) {
  return useQuery({
    queryKey: ['worker-tasks', worker],
    queryFn: () => fetchAPI<{ tasks: Task[] }>(`/workers/${worker}/tasks`),
    enabled: !!worker,
  })
}

export function useScaleWorker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ worker, action, n }: { worker: string; action: 'grow' | 'shrink'; n: number }) =>
      fetchAPI(`/workers/${worker}/pool/${action}?n=${n}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workers'] }),
  })
}

// Ralph
export function useRalphStatus() {
  return useQuery({
    queryKey: ['ralph-status'],
    queryFn: () => fetchAPI<RalphStatus>('/ralph/status'),
    refetchInterval: 3000,
  })
}

export function useRalphControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ action, params }: { action: string; params?: object }) =>
      fetchAPI(`/ralph/${action}`, { method: 'POST', body: params ? JSON.stringify(params) : undefined }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ralph-status'] }),
  })
}

// Agents
export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => fetchAPI<{ agents: Agent[] }>('/agents'),
  })
}

export function useAgentControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ agent, action }: { agent: string; action: 'start' | 'stop' }) =>
      fetchAPI(`/agents/${agent}/${action}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  })
}

// Collectors
export function useCollectors() {
  return useQuery({
    queryKey: ['collectors'],
    queryFn: () => fetchAPI<{ collectors: Collector[] }>('/collectors'),
  })
}

// Workflows
export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: () => fetchAPI<{ workflows: Workflow[] }>('/workflows'),
  })
}

// HIL Queue
export function useHILQueue() {
  return useQuery({
    queryKey: ['hil-queue'],
    queryFn: () => fetchAPI<{ pending: HILAction[]; count: number }>('/hil/pending'),
    refetchInterval: 5000,
  })
}

export function useHILAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ actionId, decision }: { actionId: string; decision: 'approve' | 'reject' }) =>
      fetchAPI(`/hil/${actionId}/${decision}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hil-queue'] }),
  })
}

// Jarvis Nodes
export function useNodes() {
  return useQuery({
    queryKey: ['nodes'],
    queryFn: () => fetchAPI<{ nodes: JarvisNode[] }>('/nodes'),
  })
}

// JHC
export function useJHCScan() {
  return useMutation({
    mutationFn: ({ org, minScore }: { org: string; minScore: number }) =>
      fetchAPI(`/tools/jhc/scan?org=${org}&min_score=${minScore}`, { method: 'POST' }),
  })
}

export function useJHCResurrect() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: JHCResurrectRequest) =>
      fetchAPI('/tools/jhc/resurrect', { method: 'POST', body: JSON.stringify(request) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hil-queue'] }),
  })
}

// Types
export interface Worker {
  name: string
  file?: string
  status: string
  source?: string
}

export interface Task {
  id: string
  name: string
  state: string
  received?: string
}

export interface RalphStatus {
  status: string
  running: boolean
  session_id?: string
  iterations?: number
  circuit_breaker?: {
    failures: number
    threshold: number
    state: string
  }
}

export interface Agent {
  name: string
  type: string
  location: string
  description: string
  status: string
  controls: string[]
}

export interface Collector {
  name: string
  type: string
  status: string
  protocol: string
  last_poll: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  steps: number
  path: string
  type: string
}

export interface HILAction {
  id: string
  action_type: string
  payload: object
  requested_at: string
  risk_level: string
}

export interface JarvisNode {
  id: string
  name: string
  host: string
  port: number
  status: string
}

export interface JHCResurrectRequest {
  repo_url: string
  aggression: string
  allow_dep_upgrades: boolean
  allow_ci_edits: boolean
}
