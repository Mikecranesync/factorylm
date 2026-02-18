/**
 * New Run Page - Configure and start a new run
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { ArrowLeft, Play } from 'lucide-react';
import { createRun } from '../services/api';
import { useConveyorStore } from '../store';
import { configureBackButton, hapticFeedback } from '../utils/telegram';
import type { RunConfig, Direction } from '../types';

const TAG_OPTIONS = ['training', 'calibration', 'production', 'maintenance', 'test'];

export function NewRunPage() {
  const navigate = useNavigate();
  const { setActiveRun, setStatus } = useConveyorStore();

  const [config, setConfig] = useState<RunConfig>({
    name: '',
    description: '',
    direction: 'forward',
    targetSpeedHz: 30,
    maxDurationSeconds: 300,
    tags: [],
  });

  const createRunMutation = useMutation({
    mutationFn: createRun,
    onSuccess: (data) => {
      setActiveRun(data.run);
      setStatus(data.status);
      hapticFeedback('success');
      navigate('/');
    },
    onError: () => {
      hapticFeedback('error');
    },
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!config.name.trim()) {
      hapticFeedback('error');
      return;
    }
    createRunMutation.mutate(config);
  };

  const toggleTag = (tag: string) => {
    setConfig((prev) => ({
      ...prev,
      tags: prev.tags.includes(tag)
        ? prev.tags.filter((t) => t !== tag)
        : [...prev.tags, tag],
    }));
    hapticFeedback('light');
  };

  return (
    <div className="min-h-screen p-4 pb-20">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/')} className="text-tg-link">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-xl font-bold">New Run</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium mb-2">Run Name *</label>
          <input
            type="text"
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
            placeholder="e.g., Morning calibration"
            className="w-full px-4 py-3 bg-tg-secondary rounded-xl focus:outline-none focus:ring-2 focus:ring-tg-link"
            required
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium mb-2">Description</label>
          <textarea
            value={config.description}
            onChange={(e) => setConfig({ ...config, description: e.target.value })}
            placeholder="Optional notes about this run..."
            rows={3}
            className="w-full px-4 py-3 bg-tg-secondary rounded-xl focus:outline-none focus:ring-2 focus:ring-tg-link resize-none"
          />
        </div>

        {/* Direction */}
        <div>
          <label className="block text-sm font-medium mb-2">Direction</label>
          <div className="flex gap-2">
            {(['forward', 'reverse'] as Direction[]).map((dir) => (
              <button
                key={dir}
                type="button"
                onClick={() => setConfig({ ...config, direction: dir })}
                className={`flex-1 py-3 rounded-xl font-medium transition-colors ${
                  config.direction === dir
                    ? 'bg-tg-button text-tg-button'
                    : 'bg-tg-secondary text-tg-hint'
                }`}
              >
                {dir.charAt(0).toUpperCase() + dir.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Target Speed */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <label className="font-medium">Target Speed</label>
            <span className="font-mono">{config.targetSpeedHz} Hz</span>
          </div>
          <input
            type="range"
            min="5"
            max="60"
            value={config.targetSpeedHz}
            onChange={(e) => setConfig({ ...config, targetSpeedHz: parseInt(e.target.value) })}
            className="w-full h-2 bg-tg-secondary rounded-lg appearance-none cursor-pointer accent-tg-link"
          />
          <div className="flex justify-between text-xs text-tg-hint mt-1">
            <span>5 Hz</span>
            <span>60 Hz</span>
          </div>
        </div>

        {/* Max Duration */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <label className="font-medium">Max Duration</label>
            <span className="font-mono">{Math.floor(config.maxDurationSeconds / 60)} min</span>
          </div>
          <input
            type="range"
            min="60"
            max="1800"
            step="60"
            value={config.maxDurationSeconds}
            onChange={(e) => setConfig({ ...config, maxDurationSeconds: parseInt(e.target.value) })}
            className="w-full h-2 bg-tg-secondary rounded-lg appearance-none cursor-pointer accent-tg-link"
          />
          <div className="flex justify-between text-xs text-tg-hint mt-1">
            <span>1 min</span>
            <span>30 min</span>
          </div>
        </div>

        {/* Tags */}
        <div>
          <label className="block text-sm font-medium mb-2">Tags</label>
          <div className="flex flex-wrap gap-2">
            {TAG_OPTIONS.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                  config.tags.includes(tag)
                    ? 'bg-tg-button text-tg-button'
                    : 'bg-tg-secondary text-tg-hint'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        {/* Error message */}
        {createRunMutation.error && (
          <div className="bg-red-100 text-red-700 rounded-xl p-3 text-sm">
            {(createRunMutation.error as Error).message || 'Failed to create run'}
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={createRunMutation.isPending || !config.name.trim()}
          className="w-full flex items-center justify-center gap-2 py-4 bg-green-500 text-white rounded-xl font-semibold disabled:opacity-50"
        >
          {createRunMutation.isPending ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Play className="w-5 h-5" />
          )}
          Start Run
        </button>
      </form>
    </div>
  );
}
