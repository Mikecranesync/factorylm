/**
 * Run Detail Page - View run details, telemetry, and add feedback
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Clock,
  Gauge,
  Zap,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Brain,
  Star,
  Square,
} from 'lucide-react';
import { getRun, stopRun, addFeedback } from '../services/api';
import { TrendChart } from '../components/TrendChart';
import { configureBackButton, hapticFeedback } from '../utils/telegram';
import { useConveyorStore } from '../store';

const ACTION_OPTIONS = [
  { value: 'followed', label: 'Followed advice', icon: ThumbsUp },
  { value: 'partial', label: 'Partially followed', icon: MessageSquare },
  { value: 'ignored', label: 'Ignored', icon: ThumbsDown },
] as const;

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setActiveRun, setStatus } = useConveyorStore();

  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedbackData, setFeedbackData] = useState({
    actionTaken: 'followed' as 'followed' | 'partial' | 'ignored',
    rating: 3,
    tags: [] as string[],
    notes: '',
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['run', id],
    queryFn: () => getRun(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll if run is still active
      const run = query.state.data?.run;
      return run?.status === 'running' || run?.status === 'pending' ? 2000 : false;
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => stopRun(id!),
    onSuccess: (result) => {
      setActiveRun(null);
      setStatus(result.status);
      queryClient.invalidateQueries({ queryKey: ['run', id] });
      hapticFeedback('success');
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: () =>
      addFeedback(id!, {
        modelAnalysisId: data?.modelAnalysis?.id,
        ...feedbackData,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['run', id] });
      setShowFeedbackForm(false);
      hapticFeedback('success');
    },
  });

  // Configure back button
  useEffect(() => {
    configureBackButton({
      visible: true,
      onClick: () => navigate('/runs'),
    });

    return () => {
      configureBackButton({ visible: false });
    };
  }, [navigate]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-tg-link border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen p-4">
        <div className="bg-red-100 text-red-700 rounded-xl p-4">
          {(error as Error)?.message || 'Run not found'}
        </div>
      </div>
    );
  }

  const { run, telemetry, modelAnalysis, feedback } = data;
  const isActive = run.status === 'running' || run.status === 'pending';

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen p-4 pb-20 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/runs')} className="text-tg-link">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">{run.config.name}</h1>
          <p className="text-sm text-tg-hint">{run.config.description}</p>
        </div>
      </div>

      {/* Status badge */}
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
        run.status === 'running' ? 'bg-green-100 text-green-700' :
        run.status === 'completed' ? 'bg-blue-100 text-blue-700' :
        run.status === 'faulted' ? 'bg-red-100 text-red-700' :
        'bg-gray-100 text-gray-700'
      }`}>
        <div className={`w-2 h-2 rounded-full ${
          run.status === 'running' ? 'bg-green-500 animate-pulse' :
          run.status === 'completed' ? 'bg-blue-500' :
          run.status === 'faulted' ? 'bg-red-500' :
          'bg-gray-500'
        }`} />
        {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
      </div>

      {/* Summary metrics */}
      {run.summary && (
        <div className="bg-tg-secondary rounded-xl p-4">
          <h3 className="text-sm font-medium mb-3">Summary</h3>
          <div className="grid grid-cols-2 gap-3">
            <MetricItem icon={<Clock className="w-4 h-4" />} label="Duration" value={formatDuration(run.summary.durationSeconds)} />
            <MetricItem icon={<Gauge className="w-4 h-4" />} label="Avg Speed" value={`${run.summary.avgSpeedHz.toFixed(1)} Hz`} />
            <MetricItem icon={<Zap className="w-4 h-4" />} label="Avg Current" value={`${run.summary.avgCurrentAmps.toFixed(2)} A`} />
            <MetricItem
              icon={<AlertTriangle className="w-4 h-4" />}
              label="Faults"
              value={run.summary.faultCount.toString()}
              highlight={run.summary.faultCount > 0}
            />
          </div>
        </div>
      )}

      {/* Telemetry chart */}
      {telemetry.length > 0 && <TrendChart data={telemetry} height={180} />}

      {/* Model Analysis */}
      {modelAnalysis && (
        <div className="bg-tg-secondary rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-5 h-5 text-purple-500" />
            <h3 className="text-sm font-medium">AI Analysis</h3>
            <span className="text-xs text-tg-hint ml-auto">{(modelAnalysis.confidence * 100).toFixed(0)}% confidence</span>
          </div>
          <p className="text-sm mb-3">{modelAnalysis.summary}</p>
          {modelAnalysis.suggestedActions.length > 0 && (
            <div className="space-y-1">
              <span className="text-xs text-tg-hint">Suggested actions:</span>
              <ul className="text-sm space-y-1">
                {modelAnalysis.suggestedActions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-tg-link">•</span>
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Existing feedback */}
      {feedback.length > 0 && (
        <div className="bg-tg-secondary rounded-xl p-4">
          <h3 className="text-sm font-medium mb-3">Feedback</h3>
          <div className="space-y-2">
            {feedback.map((fb) => (
              <div key={fb.id} className="bg-tg-bg rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <Star
                        key={star}
                        className={`w-3.5 h-3.5 ${star <= fb.rating ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300'}`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-tg-hint capitalize">{fb.actionTaken}</span>
                </div>
                {fb.notes && <p className="text-sm text-tg-hint">{fb.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback form */}
      {!isActive && modelAnalysis && !showFeedbackForm && feedback.length === 0 && (
        <button
          onClick={() => setShowFeedbackForm(true)}
          className="w-full py-3 bg-tg-secondary rounded-xl text-tg-link font-medium"
        >
          Add Feedback
        </button>
      )}

      {showFeedbackForm && (
        <div className="bg-tg-secondary rounded-xl p-4 space-y-4">
          <h3 className="font-medium">Rate AI Recommendations</h3>

          {/* Action taken */}
          <div className="flex gap-2">
            {ACTION_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setFeedbackData({ ...feedbackData, actionTaken: opt.value })}
                className={`flex-1 py-2 px-2 rounded-lg text-xs flex flex-col items-center gap-1 ${
                  feedbackData.actionTaken === opt.value
                    ? 'bg-tg-button text-tg-button'
                    : 'bg-tg-bg text-tg-hint'
                }`}
              >
                <opt.icon className="w-4 h-4" />
                {opt.label}
              </button>
            ))}
          </div>

          {/* Rating */}
          <div>
            <label className="text-sm text-tg-hint mb-2 block">Rating</label>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setFeedbackData({ ...feedbackData, rating: star })}
                  className="p-1"
                >
                  <Star
                    className={`w-8 h-8 ${star <= feedbackData.rating ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300'}`}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-sm text-tg-hint mb-2 block">Notes (optional)</label>
            <textarea
              value={feedbackData.notes}
              onChange={(e) => setFeedbackData({ ...feedbackData, notes: e.target.value })}
              placeholder="Any additional feedback..."
              rows={2}
              className="w-full px-3 py-2 bg-tg-bg rounded-lg text-sm focus:outline-none"
            />
          </div>

          <button
            onClick={() => feedbackMutation.mutate()}
            disabled={feedbackMutation.isPending}
            className="w-full py-3 bg-tg-button text-tg-button rounded-xl font-medium disabled:opacity-50"
          >
            {feedbackMutation.isPending ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      )}

      {/* Stop button for active runs */}
      {isActive && (
        <button
          onClick={() => stopMutation.mutate()}
          disabled={stopMutation.isPending}
          className="w-full flex items-center justify-center gap-2 py-4 bg-red-500 text-white rounded-xl font-semibold disabled:opacity-50"
        >
          <Square className="w-5 h-5" />
          {stopMutation.isPending ? 'Stopping...' : 'Stop Run'}
        </button>
      )}
    </div>
  );
}

function MetricItem({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={`bg-tg-bg rounded-lg p-2 ${highlight ? 'ring-1 ring-red-300' : ''}`}>
      <div className="flex items-center gap-1 text-tg-hint text-xs mb-1">
        {icon}
        {label}
      </div>
      <div className={`font-mono font-semibold ${highlight ? 'text-red-600' : ''}`}>{value}</div>
    </div>
  );
}
