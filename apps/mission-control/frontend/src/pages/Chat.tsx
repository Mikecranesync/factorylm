import ChatRelay from '../components/ChatRelay'
import { useNodes } from '../hooks/useAPI'
import { MessageSquare, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'

export default function Chat() {
  const { data: nodesData } = useNodes()
  const nodes = nodesData?.nodes || []

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <MessageSquare className="w-7 h-7 text-primary-500" />
            Claude Code Relay
          </h1>
          <p className="text-gray-500 mt-1 text-sm">Paste prompts from Perplexity, send to Claude Code on any node</p>
        </div>
        <div className="flex items-center gap-2">
          {nodes.map(node => (
            <div key={node.id} className="flex items-center gap-1.5" title={`${node.name}: ${node.status}`}>
              {node.status === 'online' ? (
                <Wifi className={clsx('w-3 h-3', 'text-green-500')} />
              ) : (
                <WifiOff className={clsx('w-3 h-3', 'text-red-500')} />
              )}
              <span className="text-xs text-gray-500">{node.id}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Chat takes remaining height */}
      <div className="flex-1 min-h-0">
        <ChatRelay />
      </div>
    </div>
  )
}
