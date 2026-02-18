/**
 * Data access layer for Conveyor Lab entities
 */

import { v4 as uuidv4 } from 'uuid';
import db from './database.js';
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
    const row = db.prepare(`
      SELECT * FROM users WHERE telegram_id = ?
    `).get(telegramId) as any;

    if (!row) return null;

    return {
      id: row.id,
      telegramId: row.telegram_id,
      username: row.username,
      firstName: row.first_name,
      lastName: row.last_name,
      createdAt: row.created_at,
      lastSeenAt: row.last_seen_at,
    };
  },

  upsert(telegramId: number, data: Partial<User>): User {
    const now = Date.now();
    const existing = this.findByTelegramId(telegramId);

    if (existing) {
      db.prepare(`
        UPDATE users SET
          username = COALESCE(?, username),
          first_name = COALESCE(?, first_name),
          last_name = COALESCE(?, last_name),
          last_seen_at = ?
        WHERE telegram_id = ?
      `).run(data.username, data.firstName, data.lastName, now, telegramId);

      return { ...existing, ...data, lastSeenAt: now };
    }

    const id = uuidv4();
    db.prepare(`
      INSERT INTO users (id, telegram_id, username, first_name, last_name, created_at, last_seen_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, telegramId, data.username, data.firstName, data.lastName, now, now);

    return {
      id,
      telegramId,
      username: data.username,
      firstName: data.firstName,
      lastName: data.lastName,
      createdAt: now,
      lastSeenAt: now,
    };
  },
};

// ============================================================================
// Runs
// ============================================================================

export const runRepo = {
  create(userId: string, config: RunConfig): Run {
    const id = uuidv4();
    const now = Date.now();

    db.prepare(`
      INSERT INTO runs (id, user_id, config_json, status, created_at)
      VALUES (?, ?, ?, 'pending', ?)
    `).run(id, userId, JSON.stringify(config), now);

    return {
      id,
      userId,
      config,
      status: 'pending',
      createdAt: now,
    };
  },

  findById(id: string): Run | null {
    const row = db.prepare(`SELECT * FROM runs WHERE id = ?`).get(id) as any;
    if (!row) return null;
    return this._rowToRun(row);
  },

  findByUserId(userId: string, limit = 50, offset = 0): Run[] {
    const rows = db.prepare(`
      SELECT * FROM runs
      WHERE user_id = ?
      ORDER BY created_at DESC
      LIMIT ? OFFSET ?
    `).all(userId, limit, offset) as any[];

    return rows.map((row) => this._rowToRun(row));
  },

  findAll(limit = 50, offset = 0, filters?: { tags?: string[]; dateFrom?: number; dateTo?: number }): Run[] {
    let sql = `SELECT * FROM runs WHERE 1=1`;
    const params: any[] = [];

    if (filters?.dateFrom) {
      sql += ` AND created_at >= ?`;
      params.push(filters.dateFrom);
    }
    if (filters?.dateTo) {
      sql += ` AND created_at <= ?`;
      params.push(filters.dateTo);
    }

    sql += ` ORDER BY created_at DESC LIMIT ? OFFSET ?`;
    params.push(limit, offset);

    const rows = db.prepare(sql).all(...params) as any[];
    let runs = rows.map((row) => this._rowToRun(row));

    // Filter by tags in memory (SQLite JSON support is limited)
    if (filters?.tags && filters.tags.length > 0) {
      runs = runs.filter((run) =>
        filters.tags!.some((tag) => run.config.tags.includes(tag))
      );
    }

    return runs;
  },

  updateStatus(id: string, status: Run['status'], summary?: RunSummary): void {
    const now = Date.now();
    const endedAt = ['completed', 'stopped', 'faulted'].includes(status) ? now : null;

    db.prepare(`
      UPDATE runs SET
        status = ?,
        ended_at = COALESCE(?, ended_at),
        summary_json = COALESCE(?, summary_json)
      WHERE id = ?
    `).run(status, endedAt, summary ? JSON.stringify(summary) : null, id);
  },

  start(id: string): void {
    db.prepare(`
      UPDATE runs SET status = 'running', started_at = ? WHERE id = ?
    `).run(Date.now(), id);
  },

  _rowToRun(row: any): Run {
    return {
      id: row.id,
      userId: row.user_id,
      config: JSON.parse(row.config_json),
      status: row.status,
      startedAt: row.started_at,
      endedAt: row.ended_at,
      summary: row.summary_json ? JSON.parse(row.summary_json) : undefined,
      createdAt: row.created_at,
    };
  },
};

// ============================================================================
// Telemetry
// ============================================================================

export const telemetryRepo = {
  insert(point: Omit<TelemetryPoint, 'id'>): TelemetryPoint {
    const id = uuidv4();

    db.prepare(`
      INSERT INTO telemetry_points
        (id, run_id, timestamp, command_hz, actual_hz, motor_current, run_state, direction, fault_code)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      point.runId,
      point.timestamp,
      point.commandHz,
      point.actualHz,
      point.motorCurrent,
      point.runState,
      point.direction,
      point.faultCode
    );

    return { id, ...point };
  },

  findByRunId(runId: string, limit = 1000): TelemetryPoint[] {
    const rows = db.prepare(`
      SELECT * FROM telemetry_points
      WHERE run_id = ?
      ORDER BY timestamp ASC
      LIMIT ?
    `).all(runId, limit) as any[];

    return rows.map((row) => ({
      id: row.id,
      runId: row.run_id,
      timestamp: row.timestamp,
      commandHz: row.command_hz,
      actualHz: row.actual_hz,
      motorCurrent: row.motor_current,
      runState: row.run_state,
      direction: row.direction,
      faultCode: row.fault_code,
    }));
  },

  getRecent(runId: string, seconds = 60): TelemetryPoint[] {
    const since = Date.now() - seconds * 1000;
    const rows = db.prepare(`
      SELECT * FROM telemetry_points
      WHERE run_id = ? AND timestamp >= ?
      ORDER BY timestamp ASC
    `).all(runId, since) as any[];

    return rows.map((row) => ({
      id: row.id,
      runId: row.run_id,
      timestamp: row.timestamp,
      commandHz: row.command_hz,
      actualHz: row.actual_hz,
      motorCurrent: row.motor_current,
      runState: row.run_state,
      direction: row.direction,
      faultCode: row.fault_code,
    }));
  },
};

// ============================================================================
// Model Analysis
// ============================================================================

export const modelAnalysisRepo = {
  create(data: Omit<ModelAnalysis, 'id' | 'createdAt'>): ModelAnalysis {
    const id = uuidv4();
    const createdAt = Date.now();

    db.prepare(`
      INSERT INTO model_analyses
        (id, run_id, cosmos_model, summary, suggested_actions_json, confidence, reasoning, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      data.runId,
      data.cosmosModel,
      data.summary,
      JSON.stringify(data.suggestedActions),
      data.confidence,
      data.reasoning,
      createdAt
    );

    return { id, ...data, createdAt };
  },

  findByRunId(runId: string): ModelAnalysis | null {
    const row = db.prepare(`
      SELECT * FROM model_analyses WHERE run_id = ? ORDER BY created_at DESC LIMIT 1
    `).get(runId) as any;

    if (!row) return null;

    return {
      id: row.id,
      runId: row.run_id,
      cosmosModel: row.cosmos_model,
      summary: row.summary,
      suggestedActions: JSON.parse(row.suggested_actions_json),
      confidence: row.confidence,
      reasoning: row.reasoning,
      createdAt: row.created_at,
    };
  },
};

// ============================================================================
// Feedback
// ============================================================================

export const feedbackRepo = {
  create(data: Omit<Feedback, 'id' | 'createdAt'>): Feedback {
    const id = uuidv4();
    const createdAt = Date.now();

    db.prepare(`
      INSERT INTO feedback
        (id, run_id, user_id, model_analysis_id, action_taken, rating, tags_json, notes, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      data.runId,
      data.userId,
      data.modelAnalysisId,
      data.actionTaken,
      data.rating,
      JSON.stringify(data.tags),
      data.notes,
      createdAt
    );

    return { id, ...data, createdAt };
  },

  findByRunId(runId: string): Feedback[] {
    const rows = db.prepare(`
      SELECT * FROM feedback WHERE run_id = ? ORDER BY created_at DESC
    `).all(runId) as any[];

    return rows.map((row) => ({
      id: row.id,
      runId: row.run_id,
      userId: row.user_id,
      modelAnalysisId: row.model_analysis_id,
      actionTaken: row.action_taken,
      rating: row.rating,
      tags: JSON.parse(row.tags_json),
      notes: row.notes,
      createdAt: row.created_at,
    }));
  },
};

// ============================================================================
// Media
// ============================================================================

export const mediaRepo = {
  create(data: Omit<Media, 'id' | 'createdAt'>): Media {
    const id = uuidv4();
    const createdAt = Date.now();

    db.prepare(`
      INSERT INTO media (id, run_id, type, url, thumbnail_url, caption, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, data.runId, data.type, data.url, data.thumbnailUrl, data.caption, createdAt);

    return { id, ...data, createdAt };
  },

  findByRunId(runId: string): Media[] {
    const rows = db.prepare(`
      SELECT * FROM media WHERE run_id = ? ORDER BY created_at DESC
    `).all(runId) as any[];

    return rows.map((row) => ({
      id: row.id,
      runId: row.run_id,
      type: row.type,
      url: row.url,
      thumbnailUrl: row.thumbnail_url,
      caption: row.caption,
      createdAt: row.created_at,
    }));
  },
};
