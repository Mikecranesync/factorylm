import { useState } from 'react'
import { useJHCResurrect, useJHCScan } from '../hooks/useAPI'
import { Cross, Search, Zap, AlertTriangle, Check } from 'lucide-react'

export default function JHCPanel() {
  const [repoUrl, setRepoUrl] = useState('')
  const [orgToScan, setOrgToScan] = useState('')
  const [aggression, setAggression] = useState('moderate')
  const [allowDepUpgrades, setAllowDepUpgrades] = useState(false)
  const [allowCIEdits, setAllowCIEdits] = useState(false)

  const scanMutation = useJHCScan()
  const resurrectMutation = useJHCResurrect()

  const handleScan = () => {
    if (!orgToScan) return
    scanMutation.mutate({ org: orgToScan, minScore: 50 })
  }

  const handleResurrect = () => {
    if (!repoUrl) return
    resurrectMutation.mutate({
      repo_url: repoUrl,
      aggression,
      allow_dep_upgrades: allowDepUpgrades,
      allow_ci_edits: allowCIEdits,
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card bg-gradient-to-r from-purple-900/50 to-indigo-900/50 border-purple-500">
        <div className="flex items-center gap-3">
          <span className="text-3xl">&#128591;</span>
          <div>
            <h2 className="text-xl font-bold">Jesus H Christ</h2>
            <p className="text-sm text-gray-400">Repo Resurrection Service ($99-$999)</p>
          </div>
        </div>
      </div>

      {/* Scan Section */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Search className="w-5 h-5 text-primary-500" />
          Scan for Candidates
        </h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={orgToScan}
            onChange={(e) => setOrgToScan(e.target.value)}
            placeholder="GitHub org (e.g., facebook)"
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2"
          />
          <button
            onClick={handleScan}
            disabled={!orgToScan || scanMutation.isPending}
            className="btn btn-primary flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            {scanMutation.isPending ? 'Scanning...' : 'Scan'}
          </button>
        </div>

        {scanMutation.data && (
          <div className="mt-4 bg-gray-900 rounded-lg p-4 max-h-64 overflow-auto">
            <pre className="text-sm text-gray-300 whitespace-pre-wrap">
              {scanMutation.data.output}
            </pre>
          </div>
        )}
      </div>

      {/* Resurrection Section */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-500" />
          Begin Resurrection
        </h3>

        <div className="space-y-4">
          {/* Repo URL */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Repository URL</label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/org/repo"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2"
            />
          </div>

          {/* Aggression Level */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Aggression Level</label>
            <select
              value={aggression}
              onChange={(e) => setAggression(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2"
            >
              <option value="gentle">Gentle - Documentation only</option>
              <option value="moderate">Moderate - Deps + CI fixes</option>
              <option value="aggressive">Aggressive - Full refactor</option>
            </select>
          </div>

          {/* Options */}
          <div className="grid grid-cols-2 gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={allowDepUpgrades}
                onChange={(e) => setAllowDepUpgrades(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600"
              />
              <span className="text-sm">Allow dependency upgrades</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={allowCIEdits}
                onChange={(e) => setAllowCIEdits(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600"
              />
              <span className="text-sm">Allow CI config edits</span>
            </label>
          </div>

          {/* Warning */}
          <div className="flex items-start gap-2 p-3 bg-yellow-900/20 border border-yellow-700 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-yellow-200">
              This action will be queued for human approval. Destructive operations require
              explicit confirmation in the HIL queue.
            </p>
          </div>

          {/* Submit */}
          <button
            onClick={handleResurrect}
            disabled={!repoUrl || resurrectMutation.isPending}
            className="btn btn-primary w-full flex items-center justify-center gap-2"
          >
            <span className="text-lg">&#128591;</span>
            {resurrectMutation.isPending ? 'Queueing...' : 'Begin Resurrection'}
          </button>

          {resurrectMutation.data && (
            <div className="p-3 bg-green-900/20 border border-green-700 rounded-lg flex items-center gap-2">
              <Check className="w-5 h-5 text-green-500" />
              <span className="text-sm text-green-200">
                Queued for approval. Action ID: {(resurrectMutation.data as any).action_id}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Pricing Info */}
      <div className="card bg-gray-900/50">
        <h4 className="font-semibold mb-3">Resurrection Pricing</h4>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 rounded-lg bg-green-900/20 border border-green-700">
            <p className="text-xl font-bold text-green-400">$99</p>
            <p className="text-xs text-gray-400">Gentle (Docs)</p>
          </div>
          <div className="p-3 rounded-lg bg-yellow-900/20 border border-yellow-700">
            <p className="text-xl font-bold text-yellow-400">$299</p>
            <p className="text-xs text-gray-400">Moderate (Deps+CI)</p>
          </div>
          <div className="p-3 rounded-lg bg-red-900/20 border border-red-700">
            <p className="text-xl font-bold text-red-400">$999</p>
            <p className="text-xs text-gray-400">Aggressive (Refactor)</p>
          </div>
        </div>
      </div>
    </div>
  )
}
