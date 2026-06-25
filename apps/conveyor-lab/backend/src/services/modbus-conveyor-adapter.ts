/**
 * Modbus Conveyor Adapter
 *
 * Connects to Factory I/O via Modbus TCP and exposes the same interface
 * as ConveyorSimulator for drop-in replacement.
 *
 * This allows the HMI to control and monitor a real 3D factory simulation.
 */

import { EventEmitter } from 'events';
import type { VFDStatus, Direction, RunState, RunSummary, Run, TelemetryPoint } from '../types/index.js';
import { FAULT_CODES } from '../types/index.js';
import { ModbusClient } from './modbus-client.js';
import { MODBUS_MAP, MODBUS_CONFIG } from '../config/modbus-config.js';
import { telemetryRepo, runRepo } from '../models/repositories.js';

interface AdapterState {
  runState: RunState;
  direction: Direction;
  commandHz: number;
  actualHz: number;
  motorCurrent: number;
  faultCode: number;
  activeRunId: string | null;
}

export class ModbusConveyorAdapter extends EventEmitter {
  private state: AdapterState = {
    runState: 'stopped',
    direction: 'forward',
    commandHz: 0,
    actualHz: 0,
    motorCurrent: 0,
    faultCode: 0,
    activeRunId: null,
  };

  private pollInterval: NodeJS.Timeout | null = null;
  private runStartTime: number = 0;
  private runMaxDuration: number = 0;
  private lastTelemetryLog: number = 0;

  constructor(private modbusClient: ModbusClient) {
    super();
    this.startPolling();
  }

  /**
   * Get current VFD status (read from Factory I/O)
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
   * Start the conveyor via Factory I/O
   */
  async start(runId?: string): Promise<VFDStatus> {
    if (this.state.runState === 'fault') {
      throw new Error('Cannot start while in fault state. Clear fault first.');
    }

    try {
      // Write to CONVEYOR coil (turn on)
      await this.modbusClient.writeCoil(MODBUS_MAP.coils.CONVEYOR, true);

      this.state.activeRunId = runId || null;
      this.state.commandHz = 30; // Default speed

      if (runId) {
        runRepo.start(runId);
        const run = runRepo.findById(runId);
        if (run) {
          this.state.direction = run.config.direction;
          this.state.commandHz = run.config.targetSpeedHz;
          this.runMaxDuration = run.config.maxDurationSeconds;
          this.runStartTime = Date.now();

          // Set direction in Factory I/O
          await this.setDirection(run.config.direction);
        }
      }

      console.log(`[ModbusAdapter] Started conveyor${runId ? ` for run ${runId}` : ''}`);
      return this.getStatus();
    } catch (err) {
      console.error('[ModbusAdapter] Start failed:', err);
      throw err;
    }
  }

  /**
   * Stop the conveyor via Factory I/O
   */
  async stop(): Promise<VFDStatus> {
    try {
      // Write to CONVEYOR coil (turn off)
      await this.modbusClient.writeCoil(MODBUS_MAP.coils.CONVEYOR, false);

      this.state.commandHz = 0;

      if (this.state.activeRunId) {
        this.completeRun('stopped');
      }

      console.log('[ModbusAdapter] Stopped conveyor');
      return this.getStatus();
    } catch (err) {
      console.error('[ModbusAdapter] Stop failed:', err);
      throw err;
    }
  }

  /**
   * Set speed (Hz) - Note: Basic Factory I/O scenes may not have speed control
   */
  async setSpeed(hz: number): Promise<VFDStatus> {
    if (hz < 0 || hz > 60) {
      throw new Error('Speed must be between 0 and 60 Hz');
    }

    this.state.commandHz = hz;

    // If scene has speed control via holding register:
    // const pct = Math.round((hz / 60) * 100);
    // await this.modbusClient.writeRegister(MODBUS_MAP.holdingRegisters.SPEED_CMD, pct);

    console.log(`[ModbusAdapter] Set command Hz to ${hz}`);
    return this.getStatus();
  }

  /**
   * Set direction via Factory I/O coils
   */
  async setDirection(direction: Direction): Promise<VFDStatus> {
    if (this.state.actualHz > 1) {
      throw new Error('Cannot change direction while running. Stop first.');
    }

    try {
      // Set direction coils
      if (direction === 'forward') {
        await this.modbusClient.writeCoil(MODBUS_MAP.coils.FORWARD, true);
        await this.modbusClient.writeCoil(MODBUS_MAP.coils.REVERSE, false);
      } else {
        await this.modbusClient.writeCoil(MODBUS_MAP.coils.FORWARD, false);
        await this.modbusClient.writeCoil(MODBUS_MAP.coils.REVERSE, true);
      }

      this.state.direction = direction;
      console.log(`[ModbusAdapter] Set direction to ${direction}`);
      return this.getStatus();
    } catch (err) {
      console.error('[ModbusAdapter] Set direction failed:', err);
      throw err;
    }
  }

  /**
   * Clear fault
   */
  async clearFault(): Promise<VFDStatus> {
    this.state.faultCode = 0;
    this.state.runState = 'stopped';
    console.log('[ModbusAdapter] Fault cleared');
    return this.getStatus();
  }

  /**
   * Inject a fault (for testing - doesn't affect Factory I/O)
   */
  injectFault(code: number): VFDStatus {
    this.state.faultCode = code;
    this.state.runState = 'fault';
    this.state.commandHz = 0;

    if (this.state.activeRunId) {
      this.completeRun('faulted');
    }

    console.log(`[ModbusAdapter] Injected fault: ${FAULT_CODES[code] || 'Unknown'}`);
    return this.getStatus();
  }

  /**
   * Start polling Factory I/O for status updates
   */
  private startPolling(): void {
    this.pollInterval = setInterval(() => {
      this.poll();
    }, MODBUS_CONFIG.pollIntervalMs);
    console.log(`[ModbusAdapter] Polling started (${MODBUS_CONFIG.pollIntervalMs}ms interval)`);
  }

  /**
   * Poll Factory I/O for current status
   */
  private async poll(): Promise<void> {
    if (!this.modbusClient.connected) {
      const reconnected = await this.modbusClient.ensureConnected();
      if (!reconnected) {
        return;
      }
    }

    try {
      // Read discrete inputs (status from Factory I/O)
      const inputs = await this.modbusClient.readDiscreteInputs(0, 5);

      const running = inputs[MODBUS_MAP.discreteInputs.RUNNING] || false;

      // Update state from Factory I/O
      if (running && this.state.runState !== 'fault') {
        this.state.runState = 'running';
        this.state.actualHz = this.state.commandHz; // Simulated speed feedback
        // Motor current simulation based on speed
        this.state.motorCurrent = 0.5 + this.state.actualHz * 0.15 + (Math.random() - 0.5) * 0.1;
      } else if (!running && this.state.runState !== 'fault') {
        this.state.runState = 'stopped';
        this.state.actualHz = 0;
        this.state.motorCurrent = 0;
      }

      // Check run duration limit
      if (this.state.activeRunId && this.runMaxDuration > 0) {
        const elapsed = (Date.now() - this.runStartTime) / 1000;
        if (elapsed >= this.runMaxDuration) {
          console.log(`[ModbusAdapter] Run ${this.state.activeRunId} reached max duration`);
          await this.stop();
        }
      }

      // Log telemetry if a run is active
      if (this.state.activeRunId) {
        this.logTelemetry();
      }

      // Emit status update
      this.emit('status', this.getStatus());
    } catch (err) {
      // Connection errors handled by modbus-client
      console.error('[ModbusAdapter] Poll error:', (err as Error).message);
    }
  }

  private logTelemetry(): void {
    if (!this.state.activeRunId) return;

    const now = Date.now();
    if (now - this.lastTelemetryLog < 500) return;

    const point: Omit<TelemetryPoint, 'id'> = {
      runId: this.state.activeRunId,
      timestamp: now,
      commandHz: this.state.commandHz,
      actualHz: this.state.actualHz,
      motorCurrent: this.state.motorCurrent,
      runState: this.state.runState,
      direction: this.state.direction,
      faultCode: this.state.faultCode,
    };

    telemetryRepo.insert(point);
    this.lastTelemetryLog = now;

    // Emit telemetry for WebSocket subscribers
    this.emit('telemetry', point);
  }

  private completeRun(outcome: 'completed' | 'stopped' | 'faulted'): void {
    if (!this.state.activeRunId) return;

    const runId = this.state.activeRunId;
    const telemetry = telemetryRepo.findByRunId(runId);

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

    console.log(`[ModbusAdapter] Run ${runId} completed with outcome: ${outcome}`);
    this.state.activeRunId = null;
    this.runStartTime = 0;
    this.runMaxDuration = 0;

    this.emit('runComplete', { runId, summary });
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
    this.modbusClient.disconnect();
    console.log('[ModbusAdapter] Destroyed');
  }
}
