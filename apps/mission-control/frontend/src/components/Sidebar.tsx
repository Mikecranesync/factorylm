import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Bot,
  Wrench,
  Play,
  Activity,
  Terminal,
  Cpu
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat Relay' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/terminal', icon: Terminal, label: 'Terminal' },
  { to: '/workers', icon: Users, label: 'Worker Swarm' },
  { to: '/ralph', icon: Play, label: 'Ralph Loop' },
  { to: '/agents', icon: Bot, label: 'Agents' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
  { to: '/hub', icon: Cpu, label: 'Ladder Logic' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col">
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Activity className="w-8 h-8 text-primary-500" />
          <div>
            <h1 className="text-lg font-bold">Mission Control</h1>
            <p className="text-xs text-gray-500">FactoryLM Orchestration</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <div className="text-xs text-gray-600">
          <p>40+ Autonomous Capabilities</p>
          <p className="mt-1">8 Workflows | 25+ Workers</p>
        </div>
      </div>
    </aside>
  )
}
