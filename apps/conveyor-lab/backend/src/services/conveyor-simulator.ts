/**
 * Conveyor/VFD Simulator
 *
 * Simulates realistic VFD behavior for development and demos.
 * This will be replaced by real PLC/VFD gateway calls in production.
 *
 * TODO: Replace with real PLC/VFD gateway integration:
 *   - Connect to Modbus TCP or EtherNet/IP
 *   - Read actual VFD registers for speed, current, faults
 *   - Write to VFD for start/stop/speed commands
 */

import { EventEmitter } from 'events';
import type { VFDStatus, Direction, RunState, RunSummary, Run, TelemetryPoint } from '../types/index.js';
import { FAULT_CODES } from '../types/index.js';
import { telemetryRepo, runRepo } from '../models/repositories.js';

interface SimulatorState {
  runState: RunState;
  direction: Direction;
  commandHz: number;
  actualHz: number;
  motorCurrent: number;
  faultCode: number;
  activeRunId: string | null;
}

class ConveyorSimulator extends EventEmitter {
  private state: SimulatorState = {
    runState: 'stopped',
    direction: 'forward',
    commandHz: 0,
    actualHz: 0,
    motorCurrent: 0,
    faultCode: 0,
    activeRunId: null,
  };

  private tickInterval: NodeJS.Timeout | null = null;
  private runStartTime: number = 0;
  private runMaxDuration: number = 0;

  // Physics constants (simplified)
  private readonly ACCEL_RATE = 2.0;      // Hz per second
  private readonly DECEL_RATE = 3.0;      // Hz per second
  private readonly CURRENT_PER_HZ = 0.15; // Amps per Hz
  private readonly BASE_CURRENT = 0.5;    // Idle current
  private readonly NOISE_FACTOR = 0.02;   // Random noise

  constructor() {
    super();
    this.startSimulationLoop();
  }

  /**
   * Get current VFD status
   */
  getStatus(): VFDStatus {
    return {
      runState: this.state.runState,
      direction: this.state.direction,
      commandHz: Math.round(this.state.commandHz * 10) / 10,
      actualHz: Math.round(this.state.actualHz * 10) / 10,
      motorCurrent: Math.round(this.state.motorCurrent * 100) / 100,
      faultCode: this.state.faultCode,
      faultText: FAULT_CODES[this.state.faultCode] || 'Unknown Fault',
      timestamp: Date.now(),
    };
  }

  /**
   * Start the conveyor
   */
  start(runId?: string): VFDStatus {
    if (this.state.runState === 'fault') {
      throw new Error('Cannot start while in fault state. Clear fault first.');
    }

    this.state.runState = 'running';
    this.state.activeRunId = runId || null;

    if (runId) {
      runRepo.start(runId);
      const run = runRepo.findById(runId);
      if (run) {
        this.state.direction = run.config.direction;
        this.state.commandHz = run.config.targetSpeedHz;
        this.runMaxDuration = run.config.maxDurationSeconds;
        this.runStartTime = Date.now();
      }
    }

    console.log(`[Simulator] Started conveyor${runId ? ` for run ${runId}` : ''}`);
    return this.getStatus();
  }

  /**
   * Stop the conveyor
   */
  stop(): VFDStatus {
    this.state.commandHz = 0;

    if (this.state.activeRunId) {
      this.completeRun('stopped');
    }

    console.log('[Simulator] Stopping conveyor');
    return this.getStatus();
  }

  /**
   * Set speed (Hz)
   */
  setSpeed(hz: number): VFDStatus {
    if (hz < 0 || hz > 60) {
      throw new Error('Speed must be between 0 and 60 Hz');
    }

    this.state.commandHz = hz;
    console.log(`[Simulator] Set command Hz to ${hz}`);
    return this.getStatus();
  }

  /**
   * Set direction
   */
  setDirection(direction: Direction): VFDStatus {
    if (this.state.actualHz > 1) {
      throw new Error('Cannot change direction while running. Stop first.');
    }

    this.state.direction = direction;
    console.log(`[Simulator] Set direction to ${direction}`);
    return this.getStatus();
  }

  /**
   * Clear fault
   */
  clearFault(): VFDStatus {
    this.state.faultCode = 0;
    this.state.runState = 'stopped';
    console.log('[Simulator] Fault cleared');
    return this.getStatus();
  }

  /**
   * Inject a fault (for testing)
   */
  injectFault(code: number): VFDStatus {
    this.state.faultCode = code;
    this.state.runState = 'fault';
    this.state.commandHz = 0;

    if (this.state.activeRunId) {
      this.completeRun('faulted');
    }

    console.log(`[Simulator] Injected fault: ${FAULT_CODES[code] || 'Unknown'}`);
    return this.getStatus();
  }

  /**
   * Main simulation loop - runs every 100ms
   */
  private startSimulationLoop(): void {
    this.tickInterval = setInterval(() => {
      this.tick();
    }, 100);
  }

  private tick(): void {
    const dt = 0.1; // 100ms in seconds

    // Update actual Hz based on command Hz (with lag)
    if (this.state.runState === 'running') {
      const diff = this.state.commandHz - this.state.actualHz;

      if (Math.abs(diff) < 0.1) {
        this.state.actualHz = this.state.commandHz;
      } else if (diff > 0) {
        this.state.actualHz += this.ACCEL_RATE * dt;
      } else {
        this.state.actualHz -= this.DECEL_RATE * dt;
      }

      // Clamp
      this.state.actualHz = Math.max(0, Math.min(60, this.state.actualHz));
    } else {
      // Decelerate to stop
      if (this.state.actualHz > 0) {
        this.state.actualHz = Math.max(0, this.state.actualHz - this.DECEL_RATE * dt);
      }
    }

    // Update motor current based on speed + noise
    if (this.state.actualHz > 0.5) {
      const baseCurrent = this.BASE_CURRENT + this.state.actualHz * this.CURRENT_PER_HZ;
      const noise = (Math.random() - 0.5) * this.NOISE_FACTOR * baseCurrent;
      this.state.motorCurrent = baseCurrent + noise;
    } else {
      this.state.motorCurrent = 0;
    }

    // Check if motor has fully stopped
    if (this.state.runState !== 'fault' && this.state.actualHz < 0.1 && this.state.commandHz === 0) {
      this.state.runState = 'stopped';
      this.state.actualHz = 0;
      this.state.motorCurrent = 0;
    }

    // Random fault injection (0.01% chance per tick for demo)
    if (this.state.runState === 'running' && Math.random() < 0.0001) {
      const faultCodes = [1, 2, 4, 7]; // Common faults
      this.injectFault(faultCodes[Math.floor(Math.random() * faultCodes.length)]);
    }

    // Check run duration limit
    if (this.state.activeRunId && this.runMaxDuration > 0) {
      const elapsed = (Date.now() - this.runStartTime) / 1000;
      if (elapsed >= this.runMaxDuration) {
        console.log(`[Simulator] Run ${this.state.activeRunId} reached max duration`);
        this.completeRun('completed');
        this.state.commandHz = 0;
      }
    }

    // Log telemetry if a run is active
    if (this.state.activeRunId) {
      this.logTelemetry();
    }

    // Emit status update
    this.emit('status', this.getStatus());
  }

  private logTelemetry(): void {
    if (!this.state.activeRunId) return;

    const point: Omit<TelemetryPoint, 'id'> = {
      runId: this.state.activeRunId,
      timestamp: Date.now(),
      commandHz: this.state.commandHz,
      actualHz: this.state.actualHz,
      motorCurrent: this.state.motorCurrent,
      runState: this.state.runState,
      direction: this.state.direction,
      faultCode: this.state.faultCode,
    };

    // Only log every 500ms to avoid flooding DB
    const lastLog = (this as any)._lastTelemetryLog || 0;
    if (Date.now() - lastLog >= 500) {
      telemetryRepo.insert(point);
      (this as any)._lastTelemetryLog = Date.now();

      // Emit telemetry for WebSocket subscribers
      this.emit('telemetry', point);
    }
  }

  private completeRun(outcome: 'completed' | 'stopped' | 'faulted'): void {
    if (!this.state.activeRunId) return;

    const runId = this.state.activeRunId;
    const telemetry = telemetryRepo.findByRunId(runId);

    // Calculate summary
    const speeds = telemetry.map((t) => t.actualHz);
    const currents = telemetry.map((t) => t.motorCurrent);
    const faults = telemetry.filter((t) => t.faultCode > 0);

    const summaryOutcome: RunSummary['outcome'] = outcome === 'completed' ? 'success' : outcome;
    const runStatus: Run['status'] = outcome === 'completed' ? 'completed' : outcome === 'stopped' ? 'stopped' : 'faulted';

    const summary = {
      durationSeconds: Math.round((Date.now() - this.runStartTime) / 1000),
      avgSpeedHz: speeds.length > 0 ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0,
      maxSpeedHz: speeds.length > 0 ? Math.max(...speeds) : 0,
      avgCurrentAmps: currents.length > 0 ? currents.reduce((a, b) => a + b, 0) / currents.length : 0,
      maxCurrentAmps: currents.length > 0 ? Math.max(...currents) : 0,
      faultCount: faults.length,
      outcome: summaryOutcome,
    };

    runRepo.updateStatus(runId, runStatus, summary);

    console.log(`[Simulator] Run ${runId} completed with outcome: ${outcome}`);
    this.state.activeRunId = null;
    this.runStartTime = 0;
    this.runMaxDuration = 0;

    this.emit('runComplete', { runId, summary });
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.tickInterval) {
      clearInterval(this.tickInterval);
    }
  }
}

// Export the class for use with conveyor service
export { ConveyorSimulator };

// Legacy singleton instance (deprecated - use getConveyor() from conveyor.ts)
export const conveyorSimulator = new ConveyorSimulator();
