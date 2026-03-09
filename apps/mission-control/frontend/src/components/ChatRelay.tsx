import { useState, useRef, useEffect } from 'react'
import { useClaudeRelay, useNodes, ClaudeResult } from '../hooks/useAPI'
import { Send, Loader2, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'

interface ChatMessage {
  id: string
  type: 'prompt' | 'response'
  node: string
  nodeName: string
  projectPath: string
  content: string
  result?: ClaudeResult
  error?: string
  timestamp: string
  durationMs?: number
}

export default function ChatRelay() {
  const [selectedNode, setSelectedNode] = useState('vps')
  const [projectPath, setProjectPath] = useState('~/factorylm')
  const [prompt, setPrompt] = useState('')
  const [timeout, setTimeout] = useState(300)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [elapsed, setElapsed] = useState(0)
  const [expandedMsg, setExpandedMsg] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: nodesData } = useNodes()
  const claudeRelay = useClaudeRelay()
  const nodes = nodesData?.nodes || []

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (claudeRelay.isPending) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [claudeRelay.isPending])

  const sendPrompt = () => {
    const text = prompt.trim()
    if (!text) return

    const node = nodes.find(n => n.id === selectedNode)
    const msgId = Date.now().toString()

    const promptMsg: ChatMessage = {
      id: msgId,
      type: 'prompt',
      node: selectedNode,
      nodeName: node?.name || selectedNode,
      projectPath,
      content: text,
      timestamp: new Date().toLocaleTimeString(),
    }

    setMessages(prev => [...prev, promptMsg])
    setPrompt('')
    setExpandedMsg(null)

    claudeRelay.mutate(
      { nodeId: selectedNode, prompt: text, projectPath, timeout },
      {
        onSuccess: (result) => {
          const responseMsg: ChatMessage = {
            id: msgId + '-response',
            type: 'response',
            node: selectedNode,
            nodeName: node?.name || selectedNode,
            projectPath,
            content: result.stdout || result.stderr || '(no output)',
            result,
            timestamp: new Date().toLocaleTimeString(),
            durationMs: result.duration_ms,
          }
          setMessages(prev => [...prev, responseMsg])
          setExpandedMsg(msgId + '-response')
        },
        onError: (err) => {
          const errorMsg: ChatMessage = {
            id: msgId + '-error',
            type: 'response',
            node: selectedNode,
            nodeName: node?.name || selectedNode,
            projectPath,
            content: '',
            error: String(err),
            timestamp: new Date().toLocaleTimeString(),
          }
          setMessages(prev => [...prev, errorMsg])
        },
      }
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      sendPrompt()
    }
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    const s = Math.round(ms / 1000)
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 mt-20">
            <p className="text-lg mb-2">Paste a prompt from Perplexity or write your own</p>
            <p className="text-sm">It will be sent to Claude Code on the selected node</p>
            <p className="text-xs mt-4 text-gray-700">Ctrl+Enter to send</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={clsx(
            'rounded-lg',
            msg.type === 'prompt' ? 'bg-primary-900/20 border border-primary-800/30' : 'bg-gray-800 border border-gray-700'
          )}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700/50">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className={clsx(
                  'w-2 h-2 rounded-full',
                  msg.type === 'prompt' ? 'bg-primary-500' : msg.error ? 'bg-red-500' : 'bg-green-500'
                )} />
                <span className="font-medium text-gray-400">
                  {msg.type === 'prompt' ? 'You' : 'Claude Code'}
                </span>
                <span>{msg.nodeName}</span>
                <span>{msg.timestamp}</span>
                {msg.durationMs !== undefined && msg.durationMs > 0 && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(msg.durationMs)}
                  </span>
                )}
              </div>
              {msg.type === 'response' && msg.content.length > 200 && (
                <button
                  onClick={() => setExpandedMsg(expandedMsg === msg.id ? null : msg.id)}
                  className="text-gray-500 hover:text-gray-300"
                >
                  {expandedMsg === msg.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              )}
            </div>

            {/* Content */}
            <div className="px-4 py-3">
              {msg.error ? (
                <pre className="text-red-400 text-sm whitespace-pre-wrap">{msg.error}</pre>
              ) : msg.type === 'prompt' ? (
                <pre className="text-gray-300 text-sm whitespace-pre-wrap break-words">
                  {msg.content.length > 500 && expandedMsg !== msg.id
                    ? msg.content.slice(0, 500) + '...'
                    : msg.content}
                </pre>
              ) : (
                <pre className="text-gray-300 text-sm whitespace-pre-wrap break-words font-mono leading-relaxed">
                  {msg.content.length > 500 && expandedMsg !== msg.id
                    ? msg.content.slice(0, 500) + '...'
                    : msg.content}
                </pre>
              )}
              {msg.result && msg.result.exit_code !== 0 && (
                <div className="mt-2 text-xs text-red-400">
                  Exit code: {msg.result.exit_code}
                  {msg.result.stderr && (
                    <pre className="mt-1 text-red-400/80 whitespace-pre-wrap">{msg.result.stderr}</pre>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {claudeRelay.isPending && (
          <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
            <div className="flex items-center gap-3 text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">Claude Code is working...</span>
              <span className="text-xs text-gray-600 font-mono">{elapsed}s</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-700 pt-4 space-y-3">
        {/* Controls row */}
        <div className="flex gap-3 items-center">
          <select
            value={selectedNode}
            onChange={e => setSelectedNode(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500"
          >
            {nodes.map(node => (
              <option key={node.id} value={node.id}>
                {node.name} {node.status === 'online' ? '' : '(offline)'}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={projectPath}
            onChange={e => setProjectPath(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500 w-48 font-mono"
            placeholder="~/factorylm"
          />
          <select
            value={timeout}
            onChange={e => setTimeout(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-500"
          >
            <option value={60}>1m timeout</option>
            <option value={180}>3m timeout</option>
            <option value={300}>5m timeout</option>
            <option value={600}>10m timeout</option>
          </select>
        </div>

        {/* Textarea + Send */}
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Paste your Perplexity output or write a prompt... (Ctrl+Enter to send)"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm resize-none focus:outline-none focus:border-primary-500 min-h-[100px] max-h-[300px]"
            rows={4}
            disabled={claudeRelay.isPending}
          />
          <button
            onClick={sendPrompt}
            disabled={claudeRelay.isPending || !prompt.trim()}
            className={clsx(
              'px-6 rounded-lg font-medium text-sm transition-colors flex items-center gap-2 self-end h-12',
              claudeRelay.isPending || !prompt.trim()
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-primary-600 hover:bg-primary-500 text-white'
            )}
          >
            {claudeRelay.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Send className="w-4 h-4" />
                Send
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
