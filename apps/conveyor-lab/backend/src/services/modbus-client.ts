/**
 * Modbus TCP Client Wrapper
 *
 * Provides a clean interface for communicating with Factory I/O
 * via Modbus TCP protocol.
 */

import ModbusRTU from 'modbus-serial';
import { MODBUS_CONFIG } from '../config/modbus-config.js';

export class ModbusClient {
  private client: ModbusRTU;
  private _connected: boolean = false;
  private reconnecting: boolean = false;

  constructor(
    private host: string = MODBUS_CONFIG.host,
    private port: number = MODBUS_CONFIG.port
  ) {
    this.client = new ModbusRTU();
    this.client.setTimeout(MODBUS_CONFIG.responseTimeout);
  }

  get connected(): boolean {
    return this._connected && this.client.isOpen;
  }

  /**
   * Connect to Modbus TCP server (Factory I/O)
   */
  async connect(): Promise<boolean> {
    if (this._connected && this.client.isOpen) {
      return true;
    }

    try {
      console.log(`[Modbus] Connecting to ${this.host}:${this.port}...`);
      await this.client.connectTCP(this.host, { port: this.port });
      this.client.setID(MODBUS_CONFIG.unitId);
      this._connected = true;
      console.log(`[Modbus] Connected to Factory I/O`);
      return true;
    } catch (err) {
      this._connected = false;
      console.log(`[Modbus] Connection failed: ${(err as Error).message}`);
      return false;
    }
  }

  /**
   * Disconnect from Modbus server
   */
  async disconnect(): Promise<void> {
    try {
      if (this.client.isOpen) {
        this.client.close(() => {});
      }
      this._connected = false;
      console.log('[Modbus] Disconnected');
    } catch (err) {
      console.error('[Modbus] Disconnect error:', err);
    }
  }

  /**
   * Read coils (digital outputs) - Function Code 01
   */
  async readCoils(address: number, count: number = 1): Promise<boolean[]> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      const result = await this.client.readCoils(address, count);
      return result.data;
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Write single coil (digital output) - Function Code 05
   */
  async writeCoil(address: number, value: boolean): Promise<void> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      await this.client.writeCoil(address, value);
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Read discrete inputs (digital inputs) - Function Code 02
   */
  async readDiscreteInputs(address: number, count: number = 1): Promise<boolean[]> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      const result = await this.client.readDiscreteInputs(address, count);
      return result.data;
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Read holding registers (analog outputs) - Function Code 03
   */
  async readHoldingRegisters(address: number, count: number = 1): Promise<number[]> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      const result = await this.client.readHoldingRegisters(address, count);
      return result.data;
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Write single holding register - Function Code 06
   */
  async writeRegister(address: number, value: number): Promise<void> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      await this.client.writeRegister(address, value);
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Read input registers (analog inputs) - Function Code 04
   */
  async readInputRegisters(address: number, count: number = 1): Promise<number[]> {
    if (!this.connected) {
      throw new Error('Not connected');
    }
    try {
      const result = await this.client.readInputRegisters(address, count);
      return result.data;
    } catch (err) {
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Handle connection errors and attempt reconnect
   */
  private handleError(err: unknown): void {
    const error = err as Error;
    if (error.message?.includes('Port Not Open') || error.message?.includes('ECONNRESET')) {
      this._connected = false;
      console.log('[Modbus] Connection lost, will retry...');
    }
  }

  /**
   * Attempt to reconnect if connection was lost
   */
  async ensureConnected(): Promise<boolean> {
    if (this.connected) {
      return true;
    }

    if (this.reconnecting) {
      return false;
    }

    this.reconnecting = true;
    try {
      const result = await this.connect();
      return result;
    } finally {
      this.reconnecting = false;
    }
  }
}

// Singleton instance
let _modbusClient: ModbusClient | null = null;

export function getModbusClient(): ModbusClient {
  if (!_modbusClient) {
    _modbusClient = new ModbusClient();
  }
  return _modbusClient;
}
