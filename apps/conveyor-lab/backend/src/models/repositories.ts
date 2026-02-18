/**
 * Data access layer for Conveyor Lab entities (in-memory)
 */

import { v4 as uuidv4 } from 'uuid';
import { store } from './database.js';
import type {
  User,
  Run,
  RunConfig,
  RunSummary,
  TelemetryPoint,
  ModelAnalysis,
  Feedback,
  Media,
} from '../types/index.js';

// ============================================================================
// Users
// ============================================================================

export const userRepo = {
  findByTelegramId(telegramId: number): User | null {
    for (const user of store.users.values()) {
      if (user.telegramId === telegramId) return user;
    }
    return null;
  },

  upsert(telegramId: number, data: Partial<User>): User {
    const now = Date.now();
    const existing = this.findByTelegramId(telegramId);

    if (existing) {
      const updated = { ...existing, ...data, lastSeenAt: now };
      store.users.set(existing.id, updated);
      return updated;
    }

    const id = uuidv4();
    const user: User = {
      id,
      telegramId,
      username: data.username,
      firstName: data.firstName,
      lastName: data.lastName,
      createdAt: now,
      lastSeenAt: now,
    };
    store.users.set(id, user);
    return user;
  },
};

// ============================================================================
// Runs
// ============================================================================

export const runRepo = {
  create(userId: string, config: RunConfig): Run {
    const id = uuidv4();
    const now = Date.now();

    const run: Run = {
      id,
      userId,
      config,
      status: 'pending',
      createdAt: now,
    };
    store.runs.set(id, run);
    store.telemetryPoints.set(id, []);
    store.feedback.set(id, []);
    store.media.set(id, []);
    return run;
  },

  findById(id: string): Run | null {
    return store.runs.get(id) || null;
  },

  findByUserId(userId: string, limit = 50, offset = 0): Run[] {
    const runs = Array.from(store.runs.values())
      .filter((run) => run.userId === userId)
      .sort((a, b) => b.createdAt - a.createdAt);
    return runs.slice(offset, offset + limit);
  },

  findAll(limit = 50, offset = 0, filters?: { tags?: string[]; dateFrom?: number; dateTo?: number }): Run[] {
    let runs = Array.from(store.runs.values())
      .sort((a, b) => b.createdAt - a.createdAt);

    if (filters?.dateFrom) {
      runs = runs.filter((run) => run.createdAt >= filters.dateFrom!);
    }
    if (filters?.dateTo) {
      runs = runs.filter((run) => run.createdAt <= filters.dateTo!);
    }
    if (filters?.tags && filters.tags.length > 0) {
      runs = runs.filter((run) =>
        filters.tags!.some((tag) => run.config.tags.includes(tag))
      );
    }

    return runs.slice(offset, offset + limit);
  },

  updateStatus(id: string, status: Run['status'], summary?: RunSummary): void {
    const run = store.runs.get(id);
    if (!run) return;

    const endedAt = ['completed', 'stopped', 'faulted'].includes(status) ? Date.now() : undefined;
    store.runs.set(id, { ...run, status, endedAt, summary: summary || run.summary });
  },

  start(id: string): void {
    const run = store.runs.get(id);
    if (!run) return;
    store.runs.set(id, { ...run, status: 'running', startedAt: Date.now() });
  },
};

// ============================================================================
// Telemetry
// ============================================================================

export const telemetryRepo = {
  insert(point: Omit<TelemetryPoint, 'id'>): TelemetryPoint {
    const id = uuidv4();
    const telemetryPoint: TelemetryPoint = { id, ...point };

    const points = store.telemetryPoints.get(point.runId) || [];
    points.push(telemetryPoint);
    store.telemetryPoints.set(point.runId, points);

    return telemetryPoint;
  },

  findByRunId(runId: string, limit = 1000): TelemetryPoint[] {
    const points = store.telemetryPoints.get(runId) || [];
    return points.slice(0, limit);
  },

  getRecent(runId: string, seconds = 60): TelemetryPoint[] {
    const since = Date.now() - seconds * 1000;
    const points = store.telemetryPoints.get(runId) || [];
    return points.filter((p) => p.timestamp >= since);
  },
};

// ============================================================================
// Model Analysis
// ============================================================================

export const modelAnalysisRepo = {
  create(data: Omit<ModelAnalysis, 'id' | 'createdAt'>): ModelAnalysis {
    const id = uuidv4();
    const createdAt = Date.now();
    const analysis: ModelAnalysis = { id, ...data, createdAt };
    store.modelAnalyses.set(id, analysis);
    return analysis;
  },

  findByRunId(runId: string): ModelAnalysis | null {
    for (const analysis of store.modelAnalyses.values()) {
      if (analysis.runId === runId) return analysis;
    }
    return null;
  },
};

// ============================================================================
// Feedback
// ============================================================================

export const feedbackRepo = {
  create(data: Omit<Feedback, 'id' | 'createdAt'>): Feedback {
    const id = uuidv4();
    const createdAt = Date.now();
    const fb: Feedback = { id, ...data, createdAt };

    const feedbackList = store.feedback.get(data.runId) || [];
    feedbackList.push(fb);
    store.feedback.set(data.runId, feedbackList);

    return fb;
  },

  findByRunId(runId: string): Feedback[] {
    return store.feedback.get(runId) || [];
  },
};

// ============================================================================
// Media
// ============================================================================

export const mediaRepo = {
  create(data: Omit<Media, 'id' | 'createdAt'>): Media {
    const id = uuidv4();
    const createdAt = Date.now();
    const m: Media = { id, ...data, createdAt };

    const mediaList = store.media.get(data.runId) || [];
    mediaList.push(m);
    store.media.set(data.runId, mediaList);

    return m;
  },

  findByRunId(runId: string): Media[] {
    return store.media.get(runId) || [];
  },
};
