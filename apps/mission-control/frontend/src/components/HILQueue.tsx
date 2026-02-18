import { useHILQueue, useHILAction, HILAction } from '../hooks/useAPI'
import { AlertCircle, Check, X, Clock, Shield } from 'lucide-react'
import clsx from 'clsx'

export default function HILQueue() {
  const { data, isLoading } = useHILQueue()
  const actionMutation = useHILAction()

  if (isLoading) return <div className="card animate-pulse">Loading HIL queue...</div>

  const pending = data?.pending || []

  if (pending.length === 0) {
    return (
      <div className="card text-center text-gray-500 py-8">
        <Shield className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p>No pending approvals</p>
        <p className="text-sm mt-1">All clear for autonomous operations</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-yellow-500" />
          Awaiting Approval ({pending.length})
        </h2>
      </div>

      <div className="space-y-3">
        {pending.map((action: HILAction) => (
          <HILActionCard
            key={action.id}
            action={action}
            onApprove={() => actionMutation.mutate({ actionId: action.id, decision: 'approve' })}
            onReject={() => actionMutation.mutate({ actionId: action.id, decision: 'reject' })}
            isLoading={actionMutation.isPending}
          />
        ))}
      </div>
    </div>
  )
}

function HILActionCard({
  action,
  onApprove,
  onReject,
  isLoading
}: {
  action: HILAction
  onApprove: () => void
  onReject: () => void
  isLoading: boolean
}) {
  const riskColors = {
    low: 'border-green-500 bg-green-900/20',
    medium: 'border-yellow-500 bg-yellow-900/20',
    high: 'border-red-500 bg-red-900/20',
    critical: 'border-red-600 bg-red-900/30',
  }

  const actionLabels: Record<string, string> = {
    jhc_resurrect: 'Jesus H Christ - Repo Resurrection',
    deploy: 'Production Deployment',
    git_push: 'Git Push',
    git_force_push: 'Git Force Push',
    delete: 'Delete Operation',
    plc_write: 'PLC Write Operation',
  }

  return (
    <div className={clsx(
      'card border-2',
      riskColors[action.risk_level as keyof typeof riskColors] || riskColors.medium
    )}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold">
            {actionLabels[action.action_type] || action.action_type}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-sm text-gray-400">
            <Clock className="w-3 h-3" />
            <span>{new Date(action.requested_at).toLocaleString()}</span>
            <span className={clsx(
              'px-2 py-0.5 rounded text-xs font-medium uppercase',
              action.risk_level === 'high' || action.risk_level === 'critical'
                ? 'bg-red-600 text-white'
                : action.risk_level === 'medium'
                ? 'bg-yellow-600 text-black'
                : 'bg-green-600 text-white'
            )}>
              {action.risk_level} risk
            </span>
          </div>
        </div>
      </div>

      {/* Payload Preview */}
      <div className="bg-gray-900 rounded p-3 mb-4 text-sm font-mono">
        <pre className="whitespace-pre-wrap text-gray-300">
          {JSON.stringify(action.payload, null, 2)}
        </pre>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={onApprove}
          disabled={isLoading}
          className="btn btn-success flex items-center gap-2 flex-1 justify-center"
        >
          <Check className="w-4 h-4" />
          Approve
        </button>
        <button
          onClick={onReject}
          disabled={isLoading}
          className="btn btn-danger flex items-center gap-2 flex-1 justify-center"
        >
          <X className="w-4 h-4" />
          Reject
        </button>
      </div>
    </div>
  )
}
