import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Workers from './pages/Workers'
import Ralph from './pages/Ralph'
import Agents from './pages/Agents'
import Tools from './pages/Tools'
import Terminal from './pages/Terminal'
import Hub from './pages/Hub'

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/terminal" element={<Terminal />} />
          <Route path="/workers" element={<Workers />} />
          <Route path="/ralph" element={<Ralph />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/hub" element={<Hub />} />
        </Routes>
      </main>
    </div>
  )
}
