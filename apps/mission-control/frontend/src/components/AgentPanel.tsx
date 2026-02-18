import { useAgents, useAgentControl, Agent } from '../hooks/useAPI'
import { Bot, Play, Square, Cpu, Video, HardDrive, Cross } from 'lucide-react'
import clsx from 'clsx'

const AGENT_ICONS: Record<string, React.ReactNode> = {
  ralph: <Cpu className="w-5 h-5" />,
  cosmos: <Video className="w-5 h-5" />,
  media_offload: <HardDrive className="w-5 h-5" />,
  jesus_h_christ: <span>&#128591;</span>,
}

export default function AgentPanel() {
  const { data, isLoading, error } = useAgents()
  const controlMutation = useAgentControl()

  if (isLoading) return <div className="card animate-pulse">Loading agents...</div>
  if (error) return <div className="card text-red-400">Error loading agents</div>

  const agents = data?.agents || []

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Bot className="w-6 h-6 text-primary-500" />
        Autonomous Agents ({agents.length})
      </h2>

      <div className="grid gap-4">
        {agents.map((agent: Agent) => (
          <AgentCard
            key={agent.name}
            agent={agent}
            onStart={() => controlMutation.mutate({ agent: agent.name, action: 'start' })}
            onStop={() => controlMutation.mutate({ agent: agent.name, action: 'stop' })}
            isLoading={controlMutation.isPending}
          />
        ))}
      </div>
    </div>
  )
}

function AgentCard({
  agent,
  onStart,
  onStop,
  isLoading
}: {
  agent: Agent
  onStart: () => void
  onStop: () => void
  isLoading: boolean
}) {
  const statusColors = {
    running: 'bg-green-500',
    starting: 'bg-yellow-500 animate-pulse',
    stopping: 'bg-yellow-500 animate-pulse',
    stopped: 'bg-gray-500',
    on_demand: 'bg-blue-500',
    unknown: 'bg-gray-600',
  }

  const isActive = agent.status === 'running' || agent.status === 'starting'
  const isOnDemand = agent.status === 'on_demand'

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className={clsx(
            'p-3 rounded-lg',
            isActive ? 'bg-green-900/30' : 'bg-gray-800'
          )}>
            {AGENT_ICONS[agent.name] || <Bot className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">{formatAgentName(agent.name)}</h3>
              <span className={clsx(
                'w-2 h-2 rounded-full',
                statusColors[agent.status as keyof typeof statusColors] || statusColors.unknown
              )} />
              <span className="text-xs text-gray-500 uppercase">{agent.status}</span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{agent.description}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs px-2 py-0.5 bg-gray-700 rounded">{agent.type}</span>
              <span className="text-xs text-gray-500">{agent.location}</span>
            </div>
          </div>
        </div>

        {!isOnDemand && (
          <div className="flex items-center gap-2">
            {isActive ? (
              <button
                onClick={onStop}
                disabled={isLoading}
                className="btn btn-danger flex items-center gap-2"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            ) : (
              <button
                onClick={onStart}
                disabled={isLoading}
                className="btn btn-success flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Start
              </button>
            )}
          </div>
        )}

        {isOnDemand && (
          <span className="text-xs px-2 py-1 bg-blue-900/30 text-blue-400 rounded">
            On Demand
          </span>
        )}
      </div>

      {/* Controls */}
      {agent.controls && agent.controls.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-500 mb-2">Available Controls:</p>
          <div className="flex flex-wrap gap-2">
            {agent.controls.map((control: string) => (
              <span
                key={control}
                className="text-xs px-2 py-1 bg-gray-800 rounded border border-gray-700"
              >
                {control}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatAgentName(name: string): string {
  const names: Record<string, string> = {
    ralph: 'Ralph Loop',
    cosmos: 'Cosmos Agent',
    media_offload: 'Media Offload',
    jesus_h_christ: 'Jesus H Christ',
  }
  return names[name] || name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}
