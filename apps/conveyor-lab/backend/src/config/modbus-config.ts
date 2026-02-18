/**
 * Modbus TCP Configuration for Factory I/O
 *
 * Factory I/O runs as Modbus TCP Server on port 502.
 * These mappings correspond to a basic conveyor scene.
 */

export const MODBUS_CONFIG = {
  // Connection settings
  // Factory I/O binds to Tailscale IP on this machine
  host: process.env.MODBUS_HOST || '100.83.251.23',
  port: parseInt(process.env.MODBUS_PORT || '502', 10),
  unitId: parseInt(process.env.MODBUS_UNIT_ID || '1', 10),

  // Timeouts
  connectTimeout: 5000, // ms
  responseTimeout: 3000, // ms

  // Polling interval
  pollIntervalMs: 100,
};

/**
 * Modbus Register Map for Factory I/O Conveyor Scene
 *
 * Coils (0xxxxx) - Digital Outputs - Write commands
 * Discrete Inputs (1xxxxx) - Digital Inputs - Read status
 * Holding Registers (4xxxxx) - Analog Outputs - Write setpoints
 * Input Registers (3xxxxx) - Analog Inputs - Read values
 */
export const MODBUS_MAP = {
  // Coils - Write to Factory I/O
  coils: {
    CONVEYOR: 0, // Conveyor belt on/off
    FORWARD: 1, // Direction forward (if applicable)
    REVERSE: 2, // Direction reverse (if applicable)
  },

  // Discrete Inputs - Read from Factory I/O
  discreteInputs: {
    RUNNING: 0, // Conveyor is running
    SENSOR_ENTRY: 1, // Entry sensor
    SENSOR_EXIT: 2, // Exit sensor
    AT_ENTRY: 3, // Part at entry
    AT_EXIT: 4, // Part at exit
  },

  // Holding Registers - Write setpoints to Factory I/O
  holdingRegisters: {
    // No speed control in basic scene
  },

  // Input Registers - Read analog values from Factory I/O
  inputRegisters: {
    // Analog inputs would go here
  },

  // Scaling factors
  scaling: {
    speedHzMax: 60, // HMI displays 0-60 Hz
    speedPctMax: 100, // Factory I/O uses 0-100%
  },
};

/**
 * Map Factory I/O discrete inputs to VFD status
 */
export function mapToRunState(running: boolean): 'running' | 'stopped' | 'fault' {
  if (running) return 'running';
  return 'stopped';
}
