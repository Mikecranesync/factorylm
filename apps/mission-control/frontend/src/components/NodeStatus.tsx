import { useNodes, JarvisNode } from '../hooks/useAPI'
import { Server, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'

export default function NodeStatus() {
  const { data, isLoading } = useNodes()

  if (isLoading) return <div className="card animate-pulse h-32" />

  const nodes = data?.nodes || []

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3 flex items-center gap-2">
        <Server className="w-4 h-4" />
        Jarvis Nodes
      </h3>
      <div className="space-y-2">
        {nodes.map((node: JarvisNode) => (
          <div
            key={node.id}
            className={clsx(
              'flex items-center justify-between p-3 rounded-lg',
              node.status === 'online' ? 'bg-green-900/20' : 'bg-red-900/20'
            )}
          >
            <div className="flex items-center gap-3">
              {node.status === 'online' ? (
                <Wifi className="w-4 h-4 text-green-500" />
              ) : (
                <WifiOff className="w-4 h-4 text-red-500" />
              )}
              <div>
                <p className="font-medium text-sm">{node.name}</p>
                <p className="text-xs text-gray-500">{node.host}:{node.port}</p>
              </div>
            </div>
            <span className={clsx(
              'text-xs uppercase font-medium',
              node.status === 'online' ? 'text-green-400' : 'text-red-400'
            )}>
              {node.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
