"""
Test client for VFD Simulator
==============================
Demonstrates reading/writing to the simulated VFD.

Run the simulator first:
    python vfd_simulator.py --port 5020
    
Then run this client:
    python test_vfd_client.py
"""

import time
from pymodbus.client import ModbusTcpClient

# Register addresses (from vfd_simulator.py)
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


def read_vfd_status(client):
    """Read all VFD status registers."""
    result = client.read_holding_registers(2100, 10)
    if result.isError():
        print(f"Error reading status: {result}")
        return None
    
    regs = result.registers
    return {
        'status_word': regs[0],
        'frequency_hz': regs[1] / 10,
        'current_a': regs[2] / 10,
        'dc_bus_v': regs[3],
        'output_v': regs[4],
        'power_kw': regs[5] / 10,
        'rpm': regs[6],
        'torque_pct': regs[7] / 10,
        'temp_c': regs[8],
        'fault_code': regs[9],
    }


def start_vfd(client, frequency_hz: float):
    """Start the VFD at specified frequency."""
    # Set frequency setpoint
    client.write_register(REGISTERS['frequency_setpoint'], int(frequency_hz * 10))
    # Set run command
    client.write_register(REGISTERS['control_word'], 1)
    print(f"VFD START command sent, setpoint: {frequency_hz} Hz")


def stop_vfd(client):
    """Stop the VFD."""
    client.write_register(REGISTERS['control_word'], 0)
    print("VFD STOP command sent")


def main():
    print("=" * 50)
    print("VFD Simulator Test Client")
    print("=" * 50)
    print()
    
    # Connect to simulator
    client = ModbusTcpClient("localhost", port=5020)
    if not client.connect():
        print("ERROR: Could not connect to VFD simulator at localhost:5020")
        print("Make sure vfd_simulator.py is running!")
        return
    
    print("✅ Connected to VFD simulator")
    print()
    
    try:
        # Read initial status
        print("--- Initial Status ---")
        status = read_vfd_status(client)
        if status:
            for k, v in status.items():
                print(f"  {k}: {v}")
        print()
        
        # Start the VFD at 30 Hz
        print("--- Starting VFD at 30 Hz ---")
        start_vfd(client, 30.0)
        print()
        
        # Monitor for 10 seconds
        print("--- Monitoring (10 seconds) ---")
        for i in range(10):
            time.sleep(1)
            status = read_vfd_status(client)
            if status:
                print(f"  [{i+1}s] {status['frequency_hz']:.1f}Hz, "
                      f"{status['current_a']:.2f}A, "
                      f"{status['rpm']:.0f}RPM, "
                      f"{status['temp_c']}°C")
        print()
        
        # Increase to 60 Hz
        print("--- Ramping to 60 Hz ---")
        client.write_register(REGISTERS['frequency_setpoint'], 600)  # 60 Hz * 10
        
        for i in range(10):
            time.sleep(1)
            status = read_vfd_status(client)
            if status:
                print(f"  [{i+1}s] {status['frequency_hz']:.1f}Hz, "
                      f"{status['current_a']:.2f}A, "
                      f"{status['rpm']:.0f}RPM")
        print()
        
        # Stop
        print("--- Stopping VFD ---")
        stop_vfd(client)
        
        for i in range(5):
            time.sleep(1)
            status = read_vfd_status(client)
            if status:
                print(f"  [{i+1}s] {status['frequency_hz']:.1f}Hz, "
                      f"{status['rpm']:.0f}RPM")
        print()
        
        print("✅ Test complete!")
        
    finally:
        client.close()


if __name__ == "__main__":
    main()
