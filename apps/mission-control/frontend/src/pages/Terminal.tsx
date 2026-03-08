import ShellTerminal from '../components/ShellTerminal'
import QuickActions from '../components/QuickActions'
import { Terminal as TerminalIcon } from 'lucide-react'

export default function Terminal() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <TerminalIcon className="w-7 h-7 text-primary-500" />
          Remote Terminal
        </h1>
        <p className="text-gray-500 mt-1">Execute commands on any Jarvis node</p>
      </div>
      <QuickActions />
      <ShellTerminal />
    </div>
  )
}
