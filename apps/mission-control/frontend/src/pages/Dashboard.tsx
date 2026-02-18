import { useWorkflows, useWorkers, useAgents, useRalphStatus } from '../hooks/useAPI'
import HILQueue from '../components/HILQueue'
import NodeStatus from '../components/NodeStatus'
import CollectorStatus from '../components/CollectorStatus'
import { Activity, Workflow, Users, Bot, Zap } from 'lucide-react'
import clsx from 'clsx'

export default function Dashboard() {
  const { data: workflows } = useWorkflows()
  const { data: workers } = useWorkers()
  const { data: agents } = useAgents()
  const { data: ralph } = useRalphStatus()

  const stats = [
    {
      label: 'Workflows',
      value: workflows?.workflows?.length || 0,
      icon: Workflow,
      color: 'text-blue-400',
      bgColor: 'bg-blue-900/30',
    },
    {
      label: 'Workers',
      value: workers?.count || 0,
      icon: Users,
      color: 'text-purple-400',
      bgColor: 'bg-purple-900/30',
    },
    {
      label: 'Agents',
      value: agents?.agents?.length || 0,
      icon: Bot,
      color: 'text-green-400',
      bgColor: 'bg-green-900/30',
    },
    {
      label: 'Ralph',
      value: ralph?.status || 'offline',
      icon: Zap,
      color: ralph?.running ? 'text-yellow-400' : 'text-gray-400',
      bgColor: ralph?.running ? 'bg-yellow-900/30' : 'bg-gray-800',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <Activity className="w-7 h-7 text-primary-500" />
            Mission Control Dashboard
          </h1>
          <p className="text-gray-500 mt-1">40+ Autonomous Capabilities</p>
        </div>
        <div className="text-right text-sm text-gray-500">
          <p>Last updated: {new Date().toLocaleTimeString()}</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color, bgColor }) => (
          <div key={label} className={clsx('card', bgColor)}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">{label}</p>
                <p className={clsx('text-2xl font-bold mt-1', color)}>{value}</p>
              </div>
              <Icon className={clsx('w-8 h-8', color)} />
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* HIL Queue - Takes 2 columns */}
        <div className="col-span-2">
          <HILQueue />
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          <NodeStatus />
          <CollectorStatus />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Quick Actions</h3>
        <div className="grid grid-cols-4 gap-3">
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            Start Ralph Loop
          </button>
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            Scan for Repos
          </button>
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            Check PLC Health
          </button>
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            View Workflows
          </button>
        </div>
      </div>
    </div>
  )
}
