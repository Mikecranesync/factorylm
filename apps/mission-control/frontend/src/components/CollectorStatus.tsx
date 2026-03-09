import { useCollectors, Collector } from '../hooks/useAPI'
import { Radio } from 'lucide-react'
import clsx from 'clsx'

const COLLECTOR_COLORS: Record<string, string> = {
  s7: 'from-blue-600 to-blue-800',
  ab: 'from-orange-600 to-orange-800',
  modbus: 'from-green-600 to-green-800',
}

export default function CollectorStatus() {
  const { data, isLoading } = useCollectors()

  if (isLoading) return <div className="card animate-pulse h-32" />

  const collectors = data?.collectors || []

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3 flex items-center gap-2">
        <Radio className="w-4 h-4" />
        PLC Collectors
      </h3>
      <div className="grid grid-cols-3 gap-3">
        {collectors.map((collector: Collector) => (
          <div
            key={collector.name}
            className={clsx(
              'p-3 rounded-lg bg-gradient-to-br text-center',
              COLLECTOR_COLORS[collector.name] || 'from-gray-600 to-gray-800'
            )}
          >
            <p className="font-bold text-sm">{collector.type}</p>
            <p className="text-xs text-white/70 mt-1">{collector.protocol}</p>
            <div className="flex items-center justify-center gap-1 mt-2">
              <span className={clsx(
                'w-2 h-2 rounded-full',
                collector.status === 'active' ? 'bg-green-400' :
                collector.status === 'unknown' ? 'bg-gray-500' : 'bg-red-400'
              )} />
              <span className="text-xs">{collector.status}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-600 mt-3 text-center">
        Connect PLC collectors to see live status
      </p>
    </div>
  )
}
