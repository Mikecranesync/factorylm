import { useWorkers, useScaleWorker, Worker } from '../hooks/useAPI'
import { Cpu, Plus, Minus, RefreshCw, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

// Worker categories for organization
const WORKER_CATEGORIES: Record<string, string[]> = {
  'Core Operations': ['conductor', 'monkey', 'monkey_dispatcher', 'workflow_tracker', 'watchman'],
  'Knowledge': ['manual_hunter', 'synthetic_user', 'content_capture'],
  'Analysis': ['alarm_triage', 'weaver', 'photo_analyzer', 'maintenance_llm'],
  'Integration': ['integration', 'github_scrubber', 'cartographer'],
  'PLC': ['plc_sync', 's7_collector', 'ab_collector', 'modbus_collector'],
  'Content': ['article_publisher', 'obs_controller', 'demo_director'],
  'Development': ['polish', 'evolution', 'foreman', 'trace'],
  'Security': ['keymaster'],
}

export default function WorkerSwarm() {
  const { data, isLoading, error, refetch } = useWorkers()
  const scaleMutation = useScaleWorker()

  if (isLoading) return <div className="card animate-pulse">Loading workers...</div>
  if (error) return <div className="card text-red-400">Error loading workers</div>

  const workers = data?.workers || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Cpu className="w-6 h-6 text-primary-500" />
          Celery Worker Swarm ({workers.length} workers)
        </h2>
        <button
          onClick={() => refetch()}
          className="btn btn-primary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {Object.entries(WORKER_CATEGORIES).map(([category, workerNames]) => {
        const categoryWorkers = workers.filter((w: Worker) =>
          workerNames.some(name => w.name.toLowerCase().includes(name))
        )

        if (categoryWorkers.length === 0) return null

        return (
          <div key={category} className="card">
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
              {category} ({categoryWorkers.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {categoryWorkers.map((worker: Worker) => (
                <WorkerCard
                  key={worker.name}
                  worker={worker}
                  onScale={(action, n) =>
                    scaleMutation.mutate({ worker: worker.name, action, n })
                  }
                />
              ))}
            </div>
          </div>
        )
      })}

      {/* Uncategorized workers */}
      {workers.filter((w: Worker) =>
        !Object.values(WORKER_CATEGORIES).flat().some(name =>
          w.name.toLowerCase().includes(name)
        )
      ).length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Other</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {workers
              .filter((w: Worker) =>
                !Object.values(WORKER_CATEGORIES).flat().some(name =>
                  w.name.toLowerCase().includes(name)
                )
              )
              .map((worker: Worker) => (
                <WorkerCard
                  key={worker.name}
                  worker={worker}
                  onScale={(action, n) =>
                    scaleMutation.mutate({ worker: worker.name, action, n })
                  }
                />
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function WorkerCard({
  worker,
  onScale
}: {
  worker: Worker
  onScale: (action: 'grow' | 'shrink', n: number) => void
}) {
  const statusColor = {
    active: 'bg-green-500',
    running: 'bg-green-500',
    idle: 'bg-yellow-500',
    offline: 'bg-red-500',
    unknown: 'bg-gray-500',
  }[worker.status.toLowerCase()] || 'bg-gray-500'

  return (
    <div className="bg-gray-900 rounded-lg p-3 border border-gray-700 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className={clsx('w-2 h-2 rounded-full', statusColor)} />
        <div>
          <p className="font-medium text-sm">{formatWorkerName(worker.name)}</p>
          <p className="text-xs text-gray-500">{worker.status}</p>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onScale('shrink', 1)}
          className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
          title="Shrink pool"
        >
          <Minus className="w-4 h-4" />
        </button>
        <button
          onClick={() => onScale('grow', 1)}
          className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
          title="Grow pool"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function formatWorkerName(name: string): string {
  return name
    .replace(/_tasks?/g, '')
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
