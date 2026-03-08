import { useState } from 'react'
import { useRalphStatus, useRalphControl } from '../hooks/useAPI'
import { Play, Pause, Square, RefreshCw, Zap, Shield, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

export default function RalphControl() {
  const { data: status, isLoading, error } = useRalphStatus()
  const controlMutation = useRalphControl()
  const [projectPath, setProjectPath] = useState('')
  const [promptFile] = useState('.ralph/PROMPT.md')

  const handleStart = () => {
    if (!projectPath) return
    controlMutation.mutate({
      action: 'start',
      params: { project_path: projectPath, prompt_file: promptFile }
    })
  }

  if (isLoading) return <div className="card animate-pulse">Loading Ralph status...</div>
  if (error) return <div className="card text-red-400">Error loading Ralph status</div>

  const isRunning = status?.running || status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const circuitBreaker = status?.circuit_breaker

  return (
    <div className="space-y-6">
      {/* Status Header */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Zap className={clsx('w-6 h-6', isRunning ? 'text-green-500' : 'text-gray-500')} />
            Ralph Autonomous Loop
          </h2>
          <StatusBadge status={status?.status || 'unknown'} />
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-900 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-primary-400">{status?.iterations || 0}</p>
            <p className="text-xs text-gray-500">Iterations</p>
          </div>
          <div className="bg-gray-900 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-green-400">
              {status?.session_id?.slice(0, 8) || 'N/A'}
            </p>
            <p className="text-xs text-gray-500">Session ID</p>
          </div>
          <div className="bg-gray-900 rounded-lg p-3 text-center">
            <p className={clsx(
              'text-2xl font-bold',
              circuitBreaker?.state === 'open' ? 'text-red-400' : 'text-green-400'
            )}>
              {circuitBreaker?.state || 'closed'}
            </p>
            <p className="text-xs text-gray-500">Circuit Breaker</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {!isRunning ? (
            <>
              <input
                type="text"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="Project path (e.g., /path/to/project)"
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm"
              />
              <button
                onClick={handleStart}
                disabled={!projectPath || controlMutation.isPending}
                className="btn btn-success flex items-center gap-2 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                Start
              </button>
            </>
          ) : (
            <>
              {isPaused ? (
                <button
                  onClick={() => controlMutation.mutate({ action: 'resume' })}
                  className="btn btn-success flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Resume
                </button>
              ) : (
                <button
                  onClick={() => controlMutation.mutate({ action: 'pause' })}
                  className="btn btn-warning flex items-center gap-2"
                >
                  <Pause className="w-4 h-4" />
                  Pause
                </button>
              )}
              <button
                onClick={() => controlMutation.mutate({ action: 'stop' })}
                className="btn btn-danger flex items-center gap-2"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            </>
          )}
        </div>
      </div>

      {/* Circuit Breaker Details */}
      {circuitBreaker && (
        <div className={clsx(
          'card border-2',
          circuitBreaker.state === 'open' ? 'border-red-500' : 'border-green-500'
        )}>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Shield className="w-5 h-5" />
            Circuit Breaker
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-400">State</p>
              <p className={clsx(
                'font-medium',
                circuitBreaker.state === 'open' ? 'text-red-400' : 'text-green-400'
              )}>
                {circuitBreaker.state.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Failures</p>
              <p className="font-medium">{circuitBreaker.failures} / {circuitBreaker.threshold}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Health</p>
              <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
                <div
                  className={clsx(
                    'h-2 rounded-full transition-all',
                    circuitBreaker.failures === 0 ? 'bg-green-500' :
                    circuitBreaker.failures < circuitBreaker.threshold / 2 ? 'bg-yellow-500' :
                    'bg-red-500'
                  )}
                  style={{
                    width: `${100 - (circuitBreaker.failures / circuitBreaker.threshold) * 100}%`
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Safety Warning */}
      <div className="card bg-yellow-900/20 border-yellow-700">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-yellow-400">Autonomous Operation</h4>
            <p className="text-sm text-gray-400 mt-1">
              Ralph will autonomously modify code, run tests, and make commits.
              The circuit breaker will halt operations after too many consecutive failures.
              Monitor the session and be ready to intervene if needed.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors = {
    running: 'bg-green-500 text-white',
    paused: 'bg-yellow-500 text-black',
    stopped: 'bg-gray-500 text-white',
    error: 'bg-red-500 text-white',
    unknown: 'bg-gray-600 text-gray-300',
  }

  return (
    <span className={clsx(
      'px-3 py-1 rounded-full text-sm font-medium',
      colors[status as keyof typeof colors] || colors.unknown
    )}>
      {status.toUpperCase()}
    </span>
  )
}
