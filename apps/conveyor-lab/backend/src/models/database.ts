/**
 * SQLite database setup for Conveyor Lab
 *
 * Designed to be easily migrated to Postgres later.
 * All timestamps are Unix milliseconds.
 */

import Database from 'better-sqlite3';
import path from 'path';

const DB_PATH = process.env.DB_PATH || path.join(process.cwd(), 'conveyor-lab.db');

export const db = new Database(DB_PATH);

// Enable WAL mode for better concurrent access
db.pragma('journal_mode = WAL');

// Initialize schema
export function initializeDatabase(): void {
  db.exec(`
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      telegram_id INTEGER UNIQUE NOT NULL,
      username TEXT,
      first_name TEXT,
      last_name TEXT,
      created_at INTEGER NOT NULL,
      last_seen_at INTEGER NOT NULL
    );

    -- Runs table
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      config_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      started_at INTEGER,
      ended_at INTEGER,
      summary_json TEXT,
      created_at INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Telemetry points (time-series)
    CREATE TABLE IF NOT EXISTS telemetry_points (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      timestamp INTEGER NOT NULL,
      command_hz REAL NOT NULL,
      actual_hz REAL NOT NULL,
      motor_current REAL NOT NULL,
      run_state TEXT NOT NULL,
      direction TEXT NOT NULL,
      fault_code INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (run_id) REFERENCES runs(id)
    );

    -- Model analysis results (Cosmos)
    CREATE TABLE IF NOT EXISTS model_analyses (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      cosmos_model TEXT NOT NULL,
      summary TEXT NOT NULL,
      suggested_actions_json TEXT NOT NULL,
      confidence REAL NOT NULL,
      reasoning TEXT,
      created_at INTEGER NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(id)
    );

    -- User feedback
    CREATE TABLE IF NOT EXISTS feedback (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      model_analysis_id TEXT,
      action_taken TEXT NOT NULL,
      rating INTEGER NOT NULL,
      tags_json TEXT NOT NULL,
      notes TEXT,
      created_at INTEGER NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(id),
      FOREIGN KEY (user_id) REFERENCES users(id),
      FOREIGN KEY (model_analysis_id) REFERENCES model_analyses(id)
    );

    -- Media attachments
    CREATE TABLE IF NOT EXISTS media (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      type TEXT NOT NULL,
      url TEXT NOT NULL,
      thumbnail_url TEXT,
      caption TEXT,
      created_at INTEGER NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(id)
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_runs_user_id ON runs(user_id);
    CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
    CREATE INDEX IF NOT EXISTS idx_telemetry_run_id ON telemetry_points(run_id);
    CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry_points(timestamp);
  `);

  console.log('[DB] Database initialized at', DB_PATH);
}

export default db;
