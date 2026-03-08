import { useState } from 'react'
import JHCPanel from '../components/JHCPanel'
import { useGitReport, useGitHotspots } from '../hooks/useAPI'
import { GitBranch, Loader2 } from 'lucide-react'

export default function Tools() {
  const [repoPath, setRepoPath] = useState('.')
  const reportMutation = useGitReport()
  const hotspotsMutation = useGitHotspots()

  const latestResult = reportMutation.data || hotspotsMutation.data
  const latestError = reportMutation.error || hotspotsMutation.error

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

        <div className="mb-4">
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="Repo path (e.g., . or ~/factorylm)"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm font-mono focus:outline-none focus:border-primary-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => reportMutation.mutate({ repoPath })}
            disabled={reportMutation.isPending || !repoPath}
            className="btn bg-gray-800 hover:bg-gray-700 text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {reportMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            {reportMutation.isPending ? 'Generating...' : 'Generate Full Report'}
          </button>
          <button
            onClick={() => hotspotsMutation.mutate({ repoPath })}
            disabled={hotspotsMutation.isPending || !repoPath}
            className="btn bg-gray-800 hover:bg-gray-700 text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {hotspotsMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            {hotspotsMutation.isPending ? 'Scanning...' : 'Find Hotspots'}
          </button>
        </div>

        {latestError && (
          <div className="mt-4 bg-red-900/20 border border-red-800/30 rounded-lg p-4">
            <pre className="text-sm text-red-400 whitespace-pre-wrap">{String(latestError)}</pre>
          </div>
        )}

        {latestResult && (
          <div className="mt-4 bg-gray-900 rounded-lg p-4 max-h-96 overflow-auto">
            <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">
              {latestResult.output || '(no output)'}
            </pre>
            {latestResult.error && (
              <pre className="text-sm text-red-400 whitespace-pre-wrap mt-2">
                {latestResult.error}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
