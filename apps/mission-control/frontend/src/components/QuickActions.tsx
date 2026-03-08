import { useState } from 'react'
import { useQuickActions, useShellExec, QuickAction, ShellResult } from '../hooks/useAPI'
import { Zap, Loader2, CheckCircle, XCircle } from 'lucide-react'
import clsx from 'clsx'

interface ActionState {
  loading: boolean
  result?: ShellResult
  error?: string
}

export default function QuickActions() {
  const { data } = useQuickActions()
  const shellExec = useShellExec()
  const [actionStates, setActionStates] = useState<Record<string, ActionState>>({})
  const [expandedAction, setExpandedAction] = useState<string | null>(null)

  const actions = data?.actions || []

  const runAction = (action: QuickAction) => {
    setActionStates(prev => ({ ...prev, [action.id]: { loading: true } }))
    setExpandedAction(action.id)

    shellExec.mutate(
      { nodeId: action.node, command: action.command },
      {
        onSuccess: (result) => {
          setActionStates(prev => ({ ...prev, [action.id]: { loading: false, result } }))
        },
        onError: (err) => {
          setActionStates(prev => ({ ...prev, [action.id]: { loading: false, error: String(err) } }))
        },
      }
    )
  }

  const riskColors: Record<string, string> = {
    low: 'border-gray-700 hover:border-green-600 hover:bg-green-900/10',
    medium: 'border-gray-700 hover:border-yellow-600 hover:bg-yellow-900/10',
    high: 'border-gray-700 hover:border-red-600 hover:bg-red-900/10',
  }

  const riskDot: Record<string, string> = {
    low: 'bg-green-500',
    medium: 'bg-yellow-500',
    high: 'bg-red-500',
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3 flex items-center gap-2">
        <Zap className="w-4 h-4" />
        Quick Actions
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {actions.map((action) => {
          const state = actionStates[action.id]
          return (
            <button
              key={action.id}
              onClick={() => runAction(action)}
              disabled={state?.loading}
              className={clsx(
                'p-3 rounded-lg border text-left transition-all text-sm',
                riskColors[action.risk] || riskColors.low,
                state?.loading && 'opacity-60 cursor-wait'
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-white text-xs">{action.label}</span>
                {state?.loading ? (
                  <Loader2 className="w-3 h-3 animate-spin text-gray-400" />
                ) : state?.result ? (
                  state.result.exit_code === 0 ? (
                    <CheckCircle className="w-3 h-3 text-green-500" />
                  ) : (
                    <XCircle className="w-3 h-3 text-red-500" />
                  )
                ) : (
                  <div className={clsx('w-2 h-2 rounded-full', riskDot[action.risk])} />
                )}
              </div>
              <div className="text-xs text-gray-500 truncate">{action.node}</div>
            </button>
          )
        })}
      </div>

      {/* Expanded result */}
      {expandedAction && actionStates[expandedAction]?.result && (
        <div className="mt-3 bg-gray-950 rounded-lg p-3 font-mono text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400">
              {actions.find(a => a.id === expandedAction)?.label}
            </span>
            <button
              onClick={() => setExpandedAction(null)}
              className="text-gray-600 hover:text-gray-400 text-xs"
            >
              close
            </button>
          </div>
          <pre className="text-gray-300 whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
            {actionStates[expandedAction].result!.stdout || actionStates[expandedAction].result!.stderr || '(no output)'}
          </pre>
        </div>
      )}

      {expandedAction && actionStates[expandedAction]?.error && (
        <div className="mt-3 bg-red-950/30 rounded-lg p-3 font-mono text-xs text-red-400">
          {actionStates[expandedAction].error}
        </div>
      )}
    </div>
  )
}
