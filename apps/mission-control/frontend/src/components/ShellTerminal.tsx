import { useState, useRef, useEffect } from 'react'
import { useShellExec, useNodes, ShellResult } from '../hooks/useAPI'
import { Terminal as TerminalIcon, Loader2 } from 'lucide-react'
import clsx from 'clsx'

interface HistoryEntry {
  command: string
  node: string
  nodeName: string
  result?: ShellResult
  error?: string
  timestamp: string
}

export default function ShellTerminal() {
  const [selectedNode, setSelectedNode] = useState('vps')
  const [command, setCommand] = useState('')
  const [timeout, setTimeout] = useState(30)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [cmdHistoryIdx, setCmdHistoryIdx] = useState(-1)
  const outputRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: nodesData } = useNodes()
  const shellExec = useShellExec()

  const nodes = nodesData?.nodes || []

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [history])

  const runCommand = () => {
    const cmd = command.trim()
    if (!cmd) return

    const node = nodes.find(n => n.id === selectedNode)
    const entry: HistoryEntry = {
      command: cmd,
      node: selectedNode,
      nodeName: node?.name || selectedNode,
      timestamp: new Date().toLocaleTimeString(),
    }

    setHistory(prev => [...prev, entry])
    setCommand('')
    setCmdHistoryIdx(-1)

    shellExec.mutate(
      { nodeId: selectedNode, command: cmd, timeout },
      {
        onSuccess: (result) => {
          setHistory(prev =>
            prev.map((e, i) => i === prev.length - 1 ? { ...e, result } : e)
          )
        },
        onError: (err) => {
          setHistory(prev =>
            prev.map((e, i) => i === prev.length - 1 ? { ...e, error: String(err) } : e)
          )
        },
      }
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      runCommand()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const cmds = history.map(h => h.command)
      if (cmds.length === 0) return
      const newIdx = cmdHistoryIdx === -1 ? cmds.length - 1 : Math.max(0, cmdHistoryIdx - 1)
      setCmdHistoryIdx(newIdx)
      setCommand(cmds[newIdx])
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const cmds = history.map(h => h.command)
      if (cmdHistoryIdx === -1) return
      const newIdx = cmdHistoryIdx + 1
      if (newIdx >= cmds.length) {
        setCmdHistoryIdx(-1)
        setCommand('')
      } else {
        setCmdHistoryIdx(newIdx)
        setCommand(cmds[newIdx])
      }
    }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3 flex items-center gap-2">
        <TerminalIcon className="w-4 h-4" />
        Shell Terminal
      </h3>

      {/* Controls */}
      <div className="flex gap-3 mb-3">
        <select
          value={selectedNode}
          onChange={e => setSelectedNode(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
        >
          {nodes.map(node => (
            <option key={node.id} value={node.id}>
              {node.name} {node.status === 'online' ? '' : '(offline)'}
            </option>
          ))}
        </select>
        <select
          value={timeout}
          onChange={e => setTimeout(Number(e.target.value))}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
        >
          <option value={10}>10s</option>
          <option value={30}>30s</option>
          <option value={60}>60s</option>
          <option value={120}>120s</option>
        </select>
      </div>

      {/* Output Area */}
      <div
        ref={outputRef}
        className="bg-gray-950 rounded-lg p-4 font-mono text-xs leading-relaxed max-h-96 overflow-y-auto mb-3 min-h-[200px]"
        onClick={() => inputRef.current?.focus()}
      >
        {history.length === 0 && (
          <span className="text-gray-600">Select a node and type a command below...</span>
        )}
        {history.map((entry, i) => (
          <div key={i} className="mb-3">
            <div className="text-gray-500">
              <span className="text-primary-400">{entry.nodeName}</span>
              <span className="text-gray-600"> {entry.timestamp}</span>
            </div>
            <div className="text-green-400">$ {entry.command}</div>
            {entry.result ? (
              <>
                {entry.result.stdout && (
                  <pre className="text-gray-300 whitespace-pre-wrap break-all">{entry.result.stdout}</pre>
                )}
                {entry.result.stderr && (
                  <pre className="text-red-400 whitespace-pre-wrap break-all">{entry.result.stderr}</pre>
                )}
                <div className={clsx(
                  'text-xs mt-1',
                  entry.result.exit_code === 0 ? 'text-gray-600' : 'text-red-500'
                )}>
                  exit {entry.result.exit_code} ({entry.result.duration_ms}ms)
                </div>
              </>
            ) : entry.error ? (
              <pre className="text-red-400 whitespace-pre-wrap">{entry.error}</pre>
            ) : (
              <div className="flex items-center gap-2 text-gray-500">
                <Loader2 className="w-3 h-3 animate-spin" />
                running...
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Command Input */}
      <div className="flex gap-2">
        <div className="flex-1 flex items-center bg-gray-800 border border-gray-700 rounded-lg px-3 focus-within:border-primary-500">
          <span className="text-green-400 font-mono text-sm mr-2">$</span>
          <input
            ref={inputRef}
            type="text"
            value={command}
            onChange={e => setCommand(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter command..."
            className="flex-1 bg-transparent py-2 text-sm font-mono focus:outline-none"
            disabled={shellExec.isPending}
          />
        </div>
        <button
          onClick={runCommand}
          disabled={shellExec.isPending || !command.trim()}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium text-sm transition-colors',
            shellExec.isPending || !command.trim()
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-primary-600 hover:bg-primary-500 text-white'
          )}
        >
          {shellExec.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Run'
          )}
        </button>
      </div>
    </div>
  )
}
