/**
 * Runs List Page - View run history
 */

import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Clock, Gauge, Zap, ChevronRight, Filter } from 'lucide-react';
import { listRuns } from '../services/api';
import { configureBackButton } from '../utils/telegram';
import type { Run } from '../types';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-500',
  running: 'bg-green-500',
  completed: 'bg-blue-500',
  stopped: 'bg-yellow-500',
  faulted: 'bg-red-500',
};

export function RunsListPage() {
  const navigate = useNavigate();
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['runs', selectedTags],
    queryFn: () => listRuns({ limit: 50, tags: selectedTags.length > 0 ? selectedTags : undefined }),
  });

  // Configure back button
  useEffect(() => {
    configureBackButton({
      visible: true,
      onClick: () => navigate('/'),
    });

    return () => {
      configureBackButton({ visible: false });
    };
  }, [navigate]);

  // Collect all unique tags
  const allTags = [...new Set(data?.runs.flatMap((r) => r.config.tags) || [])];

  return (
    <div className="min-h-screen p-4 pb-20">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate('/')} className="text-tg-link">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-xl font-bold">Run History</h1>
      </div>

      {/* Tag filters */}
      {allTags.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2 text-sm text-tg-hint">
            <Filter className="w-4 h-4" />
            <span>Filter by tag</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() => {
                  setSelectedTags((prev) =>
                    prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
                  );
                }}
                className={`px-3 py-1 rounded-full text-xs transition-colors ${
                  selectedTags.includes(tag)
                    ? 'bg-tg-button text-tg-button'
                    : 'bg-tg-secondary text-tg-hint'
                }`}
              >
                {tag}
              </button>
            ))}
            {selectedTags.length > 0 && (
              <button
                onClick={() => setSelectedTags([])}
                className="px-3 py-1 rounded-full text-xs bg-red-100 text-red-600"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-tg-link border-t-transparent rounded-full" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-100 text-red-700 rounded-xl p-4 text-sm">
          {(error as Error).message || 'Failed to load runs'}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && data?.runs.length === 0 && (
        <div className="text-center py-12 text-tg-hint">
          <p className="mb-4">No runs yet</p>
          <Link to="/new-run" className="text-tg-link font-medium">
            Start your first run
          </Link>
        </div>
      )}

      {/* Runs list */}
      {data?.runs && data.runs.length > 0 && (
        <div className="space-y-3">
          {data.runs.map((run) => (
            <RunCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}

function RunCard({ run }: { run: Run }) {
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Link
      to={`/runs/${run.id}`}
      className="block bg-tg-secondary rounded-xl p-4"
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${STATUS_COLORS[run.status]}`} />
            <span className="font-medium">{run.config.name}</span>
          </div>
          <div className="text-xs text-tg-hint">{formatDate(run.createdAt)}</div>
        </div>
        <ChevronRight className="w-5 h-5 text-tg-hint" />
      </div>

      {/* Metrics */}
      {run.summary && (
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-1 text-tg-hint">
            <Clock className="w-3.5 h-3.5" />
            <span>{formatDuration(run.summary.durationSeconds)}</span>
          </div>
          <div className="flex items-center gap-1 text-tg-hint">
            <Gauge className="w-3.5 h-3.5" />
            <span>{run.summary.avgSpeedHz.toFixed(1)} Hz avg</span>
          </div>
          <div className="flex items-center gap-1 text-tg-hint">
            <Zap className="w-3.5 h-3.5" />
            <span>{run.summary.avgCurrentAmps.toFixed(1)} A</span>
          </div>
        </div>
      )}

      {/* Tags */}
      {run.config.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {run.config.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 bg-tg-bg rounded text-xs text-tg-hint"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
