/**
 * Shared types for Conveyor Lab frontend
 */

export type RunState = 'stopped' | 'running' | 'fault' | 'offline';
export type Direction = 'forward' | 'reverse';

export interface VFDStatus {
  runState: RunState;
  direction: Direction;
  commandHz: number;
  actualHz: number;
  motorCurrent: number;
  faultCode: number;
  faultText: string;
  timestamp: number;
}

export interface RunConfig {
  name: string;
  description?: string;
  direction: Direction;
  targetSpeedHz: number;
  maxDurationSeconds: number;
  tags: string[];
}

export interface RunSummary {
  durationSeconds: number;
  avgSpeedHz: number;
  maxSpeedHz: number;
  avgCurrentAmps: number;
  maxCurrentAmps: number;
  faultCount: number;
  outcome: 'success' | 'stopped' | 'faulted';
}

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

export interface Feedback {
  id: string;
  runId: string;
  userId: string;
  modelAnalysisId?: string;
  actionTaken: 'followed' | 'partial' | 'ignored';
  rating: number;
  tags: string[];
  notes?: string;
  createdAt: number;
}

export interface Media {
  id: string;
  runId: string;
  type: 'video' | 'image';
  url: string;
  thumbnailUrl?: string;
  caption?: string;
  createdAt: number;
}

// WebSocket message types
export interface WSMessage {
  type: 'status' | 'telemetry' | 'runComplete' | 'error';
  data: any;
  timestamp: number;
}

// Telegram Web App types
export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    auth_date: number;
    hash: string;
  };
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    isProgressVisible: boolean;
    setText(text: string): void;
    onClick(callback: () => void): void;
    offClick(callback: () => void): void;
    show(): void;
    hide(): void;
    enable(): void;
    disable(): void;
    showProgress(leaveActive?: boolean): void;
    hideProgress(): void;
  };
  BackButton: {
    isVisible: boolean;
    onClick(callback: () => void): void;
    offClick(callback: () => void): void;
    show(): void;
    hide(): void;
  };
  HapticFeedback: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void;
    notificationOccurred(type: 'error' | 'success' | 'warning'): void;
    selectionChanged(): void;
  };
  ready(): void;
  expand(): void;
  close(): void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}
