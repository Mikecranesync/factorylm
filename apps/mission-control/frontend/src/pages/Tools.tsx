import JHCPanel from '../components/JHCPanel'
import { GitBranch } from 'lucide-react'

export default function Tools() {
  return (
    <div className="space-y-6">
      {/* JHC Panel */}
      <JHCPanel />

      {/* Git Forensics */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-orange-500" />
          Git Forensics
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Analyze repository health, find code hotspots, and detect patterns.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            Generate Full Report
          </button>
          <button className="btn bg-gray-800 hover:bg-gray-700 text-sm">
            Find Hotspots
          </button>
        </div>
      </div>
    </div>
  )
}
