/**
 * Core types for Conveyor Lab Mini App
 */

// VFD/Conveyor States
export type RunState = 'stopped' | 'running' | 'fault' | 'offline';
export type Direction = 'forward' | 'reverse';

// Fault codes matching real VFD error codes
export const FAULT_CODES: Record<number, string> = {
  0: 'No Fault',
  1: 'Overcurrent',
  2: 'Overvoltage',
  3: 'Undervoltage',
  4: 'Overtemperature',
  5: 'Ground Fault',
  6: 'Communication Loss',
  7: 'Motor Overload',
  8: 'External Fault',
};

// Live status from VFD
export interface VFDStatus {
  runState: RunState;
  direction: Direction;
  commandHz: number;      // Commanded frequency (0-60 Hz typical)
  actualHz: number;       // Actual motor frequency
  motorCurrent: number;   // Amps
  faultCode: number;
  faultText: string;
  timestamp: number;
}

// User (identified by Telegram)
export interface User {
  id: string;
  telegramId: number;
  username?: string;
  firstName?: string;
  lastName?: string;
  createdAt: number;
  lastSeenAt: number;
}

// Run configuration
export interface RunConfig {
  name: string;
  description?: string;
  direction: Direction;
  targetSpeedHz: number;
  maxDurationSeconds: number;
  tags: string[];
}

// Run entity
export interface Run {
  id: string;
  userId: string;
  config: RunConfig;
  status: 'pending' | 'running' | 'completed' | 'stopped' | 'faulted';
  startedAt?: number;
  endedAt?: number;
  summary?: RunSummary;
  createdAt: number;
}

// Run summary metrics
export interface RunSummary {
  durationSeconds: number;
  avgSpeedHz: number;
  maxSpeedHz: number;
  avgCurrentAmps: number;
  maxCurrentAmps: number;
  faultCount: number;
  outcome: 'success' | 'stopped' | 'faulted';
}

// Telemetry point (time-series data)
export interface TelemetryPoint {
  id: string;
  runId: string;
  timestamp: number;
  commandHz: number;
  actualHz: number;
  motorCurrent: number;
  runState: RunState;
  direction: Direction;
  faultCode: number;
}

// Cosmos model analysis result
export interface ModelAnalysis {
  id: string;
  runId: string;
  cosmosModel: string;
  summary: string;
  suggestedActions: string[];
  confidence: number;
  reasoning?: string;
  createdAt: number;
}

// User feedback on model analysis
export interface Feedback {
  id: string;
  runId: string;
  userId: string;
  modelAnalysisId?: string;
  actionTaken: 'followed' | 'partial' | 'ignored';
  rating: number;  // 1-5
  tags: string[];
  notes?: string;
  createdAt: number;
}

// Media attachment
export interface Media {
  id: string;
  runId: string;
  type: 'video' | 'image';
  url: string;
  thumbnailUrl?: string;
  caption?: string;
  createdAt: number;
}

// API command for VFD control
export interface VFDCommand {
  action: 'start' | 'stop' | 'set_speed' | 'set_direction';
  value?: number | Direction;
}

// Telegram Web App init data (parsed)
export interface TelegramInitData {
  queryId?: string;
  user?: {
    id: number;
    firstName: string;
    lastName?: string;
    username?: string;
    languageCode?: string;
  };
  authDate: number;
  hash: string;
}
