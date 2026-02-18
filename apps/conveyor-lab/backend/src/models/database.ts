/**
 * In-memory data store for Conveyor Lab
 *
 * Simple in-memory storage for demo purposes.
 * Can be replaced with SQLite/Postgres later.
 */

import type {
  User,
  Run,
  TelemetryPoint,
  ModelAnalysis,
  Feedback,
  Media,
} from '../types';

// In-memory data store
export const store = {
  users: new Map<string, User>(),
  runs: new Map<string, Run>(),
  telemetryPoints: new Map<string, TelemetryPoint[]>(), // keyed by runId
  modelAnalyses: new Map<string, ModelAnalysis>(),
  feedback: new Map<string, Feedback[]>(), // keyed by runId
  media: new Map<string, Media[]>(), // keyed by runId
};

export function initializeDatabase(): void {
  console.log('[DB] In-memory store initialized');
}

export default store;
