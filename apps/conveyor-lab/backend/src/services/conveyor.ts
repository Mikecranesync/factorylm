/**
 * Conveyor Service - Abstraction Layer
 *
 * This module exports a single conveyor controller that can be either:
 * - ModbusConveyorAdapter (when Factory I/O is detected)
 * - ConveyorSimulator (fallback when no PLC/simulator connected)
 *
 * Auto-detection happens at startup.
 */

import { EventEmitter } from 'events';
import type { VFDStatus, Direction, TelemetryPoint } from '../types/index.js';
import { ConveyorSimulator } from './conveyor-simulator.js';
import { ModbusConveyorAdapter } from './modbus-conveyor-adapter.js';
import { ModbusClient } from './modbus-client.js';
import { MODBUS_CONFIG } from '../config/modbus-config.js';

/**
 * Common interface for conveyor controllers
 */
export interface IConveyorController extends EventEmitter {
  getStatus(): VFDStatus;
  start(runId?: string): VFDStatus | Promise<VFDStatus>;
  stop(): VFDStatus | Promise<VFDStatus>;
  setSpeed(hz: number): VFDStatus | Promise<VFDStatus>;
  setDirection(direction: Direction): VFDStatus | Promise<VFDStatus>;
  clearFault(): VFDStatus | Promise<VFDStatus>;
  injectFault(code: number): VFDStatus;
  destroy(): void;
}

// Global conveyor controller instance
let _conveyor: IConveyorController | null = null;
let _connectionMode: 'factoryio' | 'simulator' = 'simulator';

/**
 * Initialize the conveyor controller
 * Attempts to connect to Factory I/O via Modbus TCP, falls back to simulator
 */
export async function initializeConveyor(): Promise<IConveyorController> {
  if (_conveyor) {
    return _conveyor;
  }

  const autoConnect = process.env.FACTORYIO_AUTO_CONNECT !== 'false';

  if (autoConnect) {
    console.log(`[Conveyor] Attempting to connect to Factory I/O at ${MODBUS_CONFIG.host}:${MODBUS_CONFIG.port}...`);

    const modbusClient = new ModbusClient();
    const connected = await modbusClient.connect();

    if (connected) {
      console.log('[Conveyor] Connected to Factory I/O via Modbus TCP');
      _conveyor = new ModbusConveyorAdapter(modbusClient);
      _connectionMode = 'factoryio';
      return _conveyor;
    } else {
      console.log('[Conveyor] Factory I/O not available, using simulator');
    }
  } else {
    console.log('[Conveyor] Auto-connect disabled, using simulator');
  }

  // Fall back to simulator
  _conveyor = new ConveyorSimulator();
  _connectionMode = 'simulator';
  return _conveyor;
}

/**
 * Get the conveyor controller instance
 * Must call initializeConveyor() first
 */
export function getConveyor(): IConveyorController {
  if (!_conveyor) {
    // Return simulator as fallback if not initialized
    console.warn('[Conveyor] Not initialized, creating simulator');
    _conveyor = new ConveyorSimulator();
    _connectionMode = 'simulator';
  }
  return _conveyor;
}

/**
 * Get the current connection mode
 */
export function getConnectionMode(): 'factoryio' | 'simulator' {
  return _connectionMode;
}

/**
 * Reconnect to Factory I/O (useful after simulator was used as fallback)
 */
export async function reconnectFactoryIO(): Promise<boolean> {
  if (_connectionMode === 'factoryio') {
    return true; // Already connected
  }

  const modbusClient = new ModbusClient();
  const connected = await modbusClient.connect();

  if (connected) {
    // Destroy old simulator
    if (_conveyor) {
      _conveyor.destroy();
    }

    _conveyor = new ModbusConveyorAdapter(modbusClient);
    _connectionMode = 'factoryio';
    console.log('[Conveyor] Reconnected to Factory I/O');
    return true;
  }

  return false;
}
