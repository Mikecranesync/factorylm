#!/usr/bin/env python3
"""
VFD + Motor Simulator for FactoryLM Demo
=========================================
Simulates a DURApulse GS10-style VFD with realistic motor physics.

Usage:
    python vfd_simulator.py --port 5020
    
Then connect FactoryLM to localhost:5020 via Modbus TCP.
"""

import asyncio
import argparse
import logging
import math
import time
import random
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("VFD_Simulator")


# =============================================================================
# DURApulse GS10 Modbus Register Map
# =============================================================================

REGISTERS = {
    'status_word': 2100,
    'output_frequency': 2101,
    'output_current': 2102,
    'dc_bus_voltage': 2103,
    'output_voltage': 2104,
    'output_power': 2105,
    'motor_rpm': 2106,
    'output_torque': 2107,
    'drive_temp': 2108,
    'fault_code': 2109,
    'control_word': 8400,
    'frequency_setpoint': 8401,
    'accel_time': 8402,
    'decel_time': 8403,
}

STATUS_READY = 0x0001
STATUS_RUNNING = 0x0002
STATUS_FAULT = 0x0004
STATUS_AT_SPEED = 0x0008
CONTROL_RUN = 0x0001
CONTROL_FAULT_RESET = 0x0004


@dataclass
class MotorState:
    """Simulated motor state with physics."""
    rated_power_kw: float = 0.19
    rated_voltage: float = 230.0
    rated_frequency: float = 60.0
    rated_current: float = 1.2
    rated_rpm: float = 1725.0
    poles: int = 4
    
    frequency_setpoint: float = 0.0
    actual_frequency: float = 0.0
    actual_current: float = 0.0
    actual_rpm: float = 0.0
    actual_torque: float = 0.0
    dc_bus_voltage: float = 310.0
    output_voltage: float = 0.0
    output_power: float = 0.0
    temperature: float = 25.0
    
    running: bool = False
    fault: bool = False
    fault_code: int = 0
    at_speed: bool = False
    
    accel_time: float = 5.0
    decel_time: float = 5.0
    last_update: float = field(default_factory=time.time)
    load_torque_pct: float = 20.0
    
    def update(self, dt: float):
        if self.fault:
            self.actual_frequency = 0.0
            self.actual_current = 0.0
            self.actual_rpm = 0.0
            return
        
        if self.running:
            freq_diff = self.frequency_setpoint - self.actual_frequency
            if abs(freq_diff) < 0.1:
                self.actual_frequency = self.frequency_setpoint
                self.at_speed = True
            else:
                self.at_speed = False
                ramp_rate = self.rated_frequency / (self.accel_time if freq_diff > 0 else self.decel_time)
                if freq_diff > 0:
                    self.actual_frequency = min(self.actual_frequency + ramp_rate * dt, self.frequency_setpoint)
                else:
                    self.actual_frequency = max(self.actual_frequency - ramp_rate * dt, self.frequency_setpoint)
        else:
            if self.actual_frequency > 0:
                ramp_rate = self.rated_frequency / self.decel_time
                self.actual_frequency = max(0, self.actual_frequency - ramp_rate * dt)
            self.at_speed = False
        
        sync_rpm = (120 * self.actual_frequency) / self.poles
        self.actual_rpm = sync_rpm * 0.97  # 3% slip
        
        if self.actual_frequency > 0:
            freq_ratio = self.actual_frequency / self.rated_frequency
            self.actual_current = (0.3 + (self.load_torque_pct / 100) * freq_ratio) * self.rated_current
            self.actual_current *= (1 + random.uniform(-0.02, 0.02))
        else:
            self.actual_current = 0.0
        
        self.output_voltage = min((self.actual_frequency / self.rated_frequency) * self.rated_voltage, self.rated_voltage)
        self.output_power = (1.732 * self.output_voltage * self.actual_current * 0.85) / 1000
        self.actual_torque = (self.output_power / self.rated_power_kw) * 100 if self.actual_frequency > 0 else 0
        
        if self.running:
            self.temperature = min(self.temperature + 0.05 * self.output_power * dt, 80)
        else:
            self.temperature = max(25, self.temperature - 0.01 * dt)
    
    def get_status_word(self) -> int:
        status = STATUS_READY
        if self.running: status |= STATUS_RUNNING
        if self.fault: status |= STATUS_FAULT
        if self.at_speed: status |= STATUS_AT_SPEED
        return status


# Global register storage
registers = {addr: 0 for addr in range(10000)}
registers[REGISTERS['accel_time']] = 50
registers[REGISTERS['decel_time']] = 50


class VFDSimulator:
    def __init__(self, port: int = 5020):
        self.port = port
        self.motor = MotorState()
        self.running = False
    
    def _sync_registers(self):
        """Sync motor state to/from registers."""
        # Read control
        control = registers[REGISTERS['control_word']]
        if control & CONTROL_RUN and not self.motor.fault:
            if not self.motor.running:
                self.motor.running = True
                logger.info("Motor START")
        else:
            if self.motor.running:
                self.motor.running = False
                logger.info("Motor STOP")
        
        if control & CONTROL_FAULT_RESET:
            self.motor.fault = False
            self.motor.fault_code = 0
            registers[REGISTERS['control_word']] &= ~CONTROL_FAULT_RESET
        
        self.motor.frequency_setpoint = registers[REGISTERS['frequency_setpoint']] / 10.0
        self.motor.accel_time = max(0.1, registers[REGISTERS['accel_time']] / 10.0)
        self.motor.decel_time = max(0.1, registers[REGISTERS['decel_time']] / 10.0)
        
        # Write status
        registers[REGISTERS['status_word']] = self.motor.get_status_word()
        registers[REGISTERS['output_frequency']] = int(self.motor.actual_frequency * 10)
        registers[REGISTERS['output_current']] = int(self.motor.actual_current * 10)
        registers[REGISTERS['dc_bus_voltage']] = int(self.motor.dc_bus_voltage)
        registers[REGISTERS['output_voltage']] = int(self.motor.output_voltage)
        registers[REGISTERS['output_power']] = int(self.motor.output_power * 10)
        registers[REGISTERS['motor_rpm']] = int(self.motor.actual_rpm)
        registers[REGISTERS['output_torque']] = int(self.motor.actual_torque * 10)
        registers[REGISTERS['drive_temp']] = int(self.motor.temperature)
        registers[REGISTERS['fault_code']] = self.motor.fault_code
    
    async def simulation_loop(self):
        logger.info("Simulation loop started")
        last_log = 0
        while self.running:
            now = time.time()
            dt = now - self.motor.last_update
            self.motor.last_update = now
            
            self._sync_registers()
            self.motor.update(dt)
            self._sync_registers()
            
            if self.motor.running and now - last_log > 2:
                logger.info(f"Motor: {self.motor.actual_frequency:.1f}Hz, {self.motor.actual_current:.2f}A, {self.motor.actual_rpm:.0f}RPM")
                last_log = now
            
            await asyncio.sleep(0.1)
    
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.info(f"Client connected: {addr}")
        
        try:
            while True:
                data = await reader.read(256)
                if not data:
                    break
                
                # Parse Modbus TCP frame
                if len(data) < 12:
                    continue
                
                tid = (data[0] << 8) | data[1]
                unit = data[6]
                func = data[7]
                
                if func == 3:  # Read Holding Registers
                    start = (data[8] << 8) | data[9]
                    count = (data[10] << 8) | data[11]
                    
                    values = [registers.get(start + i, 0) for i in range(count)]
                    
                    resp = bytearray([
                        data[0], data[1],  # Transaction ID
                        0, 0,  # Protocol
                        0, 3 + count * 2,  # Length
                        unit,
                        func,
                        count * 2,  # Byte count
                    ])
                    for v in values:
                        resp.extend([(v >> 8) & 0xFF, v & 0xFF])
                    
                    writer.write(resp)
                    await writer.drain()
                
                elif func == 6:  # Write Single Register
                    addr_reg = (data[8] << 8) | data[9]
                    value = (data[10] << 8) | data[11]
                    registers[addr_reg] = value
                    logger.debug(f"Write reg {addr_reg} = {value}")
                    writer.write(data[:12])  # Echo back
                    await writer.drain()
                
                elif func == 16:  # Write Multiple Registers
                    start = (data[8] << 8) | data[9]
                    count = (data[10] << 8) | data[11]
                    for i in range(count):
                        registers[start + i] = (data[13 + i*2] << 8) | data[14 + i*2]
                    
                    resp = data[:12]
                    writer.write(resp)
                    await writer.drain()
        
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {addr}")
    
    async def start(self):
        self.running = True
        
        logger.info("=" * 50)
        logger.info("VFD Simulator - DURApulse GS10 Emulation")
        logger.info("=" * 50)
        logger.info(f"Modbus TCP Server on port {self.port}")
        logger.info("")
        logger.info("Register Map:")
        for name, addr in REGISTERS.items():
            logger.info(f"  {addr}: {name}")
        logger.info("")
        logger.info("Control:")
        logger.info("  Write 1 to reg 8400 to START")
        logger.info("  Write 0 to reg 8400 to STOP")
        logger.info("  Write Hz*10 to reg 8401 for speed (600=60Hz)")
        logger.info("=" * 50)
        
        # Start simulation
        asyncio.create_task(self.simulation_loop())
        
        # Start TCP server
        server = await asyncio.start_server(self.handle_client, '0.0.0.0', self.port)
        
        async with server:
            await server.serve_forever()


async def main():
    parser = argparse.ArgumentParser(description="VFD + Motor Simulator")
    parser.add_argument("--port", type=int, default=5020, help="Modbus TCP port")
    args = parser.parse_args()
    
    sim = VFDSimulator(port=args.port)
    await sim.start()


if __name__ == "__main__":
    asyncio.run(main())
