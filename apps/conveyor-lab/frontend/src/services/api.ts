/**
 * API client for Conveyor Lab backend
 */

import { getTelegramInitData } from '../utils/telegram';
import type { VFDStatus, Run, RunConfig, TelemetryPoint, ModelAnalysis, Feedback, Media } from '../types';

const API_BASE = '/api';

/**
 * Make an authenticated API request
 */
async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Add Telegram init data for authentication
  const initData = getTelegramInitData();
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Status API
// ============================================================================

export async function getStatus(): Promise<VFDStatus> {
  return apiFetch<VFDStatus>('/status');
}

export async function sendCommand(
  action: 'start' | 'stop' | 'set_speed' | 'set_direction' | 'clear_fault',
  value?: number | 'forward' | 'reverse',
  runId?: string
): Promise<{ success: boolean; status: VFDStatus }> {
  return apiFetch('/command', {
    method: 'POST',
    body: JSON.stringify({ action, value, runId }),
  });
}

// ============================================================================
// Runs API
// ============================================================================

export async function createRun(config: RunConfig): Promise<{ run: Run; status: VFDStatus }> {
  return apiFetch('/runs', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export async function listRuns(params?: {
  limit?: number;
  offset?: number;
  tags?: string[];
  dateFrom?: number;
  dateTo?: number;
}): Promise<{ runs: Run[]; pagination: { limit: number; offset: number; hasMore: boolean } }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', params.limit.toString());
  if (params?.offset) query.set('offset', params.offset.toString());
  if (params?.tags?.length) query.set('tags', params.tags.join(','));
  if (params?.dateFrom) query.set('dateFrom', params.dateFrom.toString());
  if (params?.dateTo) query.set('dateTo', params.dateTo.toString());

  const queryString = query.toString();
  return apiFetch(`/runs${queryString ? `?${queryString}` : ''}`);
}

export async function getRun(id: string): Promise<{
  run: Run;
  telemetry: TelemetryPoint[];
  modelAnalysis: ModelAnalysis | null;
  feedback: Feedback[];
  media: Media[];
}> {
  return apiFetch(`/runs/${id}`);
}

export async function stopRun(id: string): Promise<{ run: Run; status: VFDStatus }> {
  return apiFetch(`/runs/${id}/stop`, { method: 'POST' });
}

export async function addFeedback(
  runId: string,
  data: {
    modelAnalysisId?: string;
    actionTaken: 'followed' | 'partial' | 'ignored';
    rating: number;
    tags: string[];
    notes?: string;
  }
): Promise<{ feedback: Feedback }> {
  return apiFetch(`/runs/${runId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function addModelAnalysis(
  runId: string,
  data: {
    cosmosModel?: string;
    summary: string;
    suggestedActions: string[];
    confidence: number;
    reasoning?: string;
  }
): Promise<{ analysis: ModelAnalysis }> {
  return apiFetch(`/runs/${runId}/model-analysis`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
