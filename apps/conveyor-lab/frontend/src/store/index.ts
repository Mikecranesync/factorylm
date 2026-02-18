/**
 * Global state store using Zustand
 */

import { create } from 'zustand';
import type { VFDStatus, Run, TelemetryPoint } from '../types';

interface ConveyorStore {
  // VFD Status
  status: VFDStatus | null;
  setStatus: (status: VFDStatus) => void;

  // Active Run
  activeRun: Run | null;
  setActiveRun: (run: Run | null) => void;

  // Telemetry buffer (last N points for chart)
  telemetryBuffer: TelemetryPoint[];
  addTelemetryPoint: (point: TelemetryPoint) => void;
  clearTelemetryBuffer: () => void;

  // WebSocket connection status
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  // UI state
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;
}

const MAX_TELEMETRY_POINTS = 100;

export const useConveyorStore = create<ConveyorStore>((set) => ({
  // VFD Status
  status: null,
  setStatus: (status) => set({ status }),

  // Active Run
  activeRun: null,
  setActiveRun: (run) => set({ activeRun: run }),

  // Telemetry buffer
  telemetryBuffer: [],
  addTelemetryPoint: (point) =>
    set((state) => ({
      telemetryBuffer: [...state.telemetryBuffer, point].slice(-MAX_TELEMETRY_POINTS),
    })),
  clearTelemetryBuffer: () => set({ telemetryBuffer: [] }),

  // WebSocket status
  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  // UI state
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),
  error: null,
  setError: (error) => set({ error }),
}));
