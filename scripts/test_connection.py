"""
FactoryLM - Micro 820 Modbus Connection Test

Test script to verify Modbus TCP connection to Micro 820 PLC.
Run this BEFORE attempting full HMI integration.

Usage:
    python test_connection.py
    python test_connection.py --host 192.168.1.100 --port 502
"""

from pymodbus.client import ModbusTcpClient
import argparse
import time
import sys

# Default Configuration - MUST MATCH YOUR CCW SETTINGS
DEFAULT_PLC_IP = "192.168.1.100"
DEFAULT_PLC_PORT = 502


def test_connection(host: str, port: int) -> ModbusTcpClient | bool:
    """Test basic Modbus TCP connection"""
    print(f"Connecting to Micro 820 at {host}:{port}...")

    client = ModbusTcpClient(host, port=port, timeout=5)

    if not client.connect():
        print("FAILED to connect!")
        print("\nCheck:")
        print("  1. PLC is powered on and in RUN mode")
        print("  2. Ethernet cable is connected")
        print("  3. IP addresses are on same subnet")
        print("  4. Modbus TCP Server is enabled in CCW")
        print("  5. Windows Firewall allows port 502")
        return False

    print("Connected!")
    return client


def read_registers(client: ModbusTcpClient) -> list | None:
    """Read holding registers 100-105"""
    print("\nReading Holding Registers 100-105...")

    result = client.read_holding_registers(address=100, count=6, slave=1)

    if result.isError():
        print(f"Error reading registers: {result}")
        return None

    registers = result.registers
    print(f"  Register 100 (motor_speed):    {registers[0]}")
    print(f"  Register 101 (motor_current):  {registers[1] / 10.0} A")
    print(f"  Register 102 (temperature):    {registers[2] / 10.0} C")
    print(f"  Register 103 (pressure):       {registers[3]} PSI")

    if len(registers) > 4:
        print(f"  Register 104 (conveyor_speed): {registers[4]}")
    if len(registers) > 5:
        print(f"  Register 105 (error_code):     {registers[5]}")

    return registers


def read_coils(client: ModbusTcpClient) -> list | None:
    """Read coils 0-5"""
    print("\nReading Coils 0-5...")

    result = client.read_coils(address=0, count=6, slave=1)

    if result.isError():
        print(f"Error reading coils: {result}")
        return None

    coils = result.bits[:6]  # Get first 6 bits
    print(f"  Coil 0 (motor_running):    {coils[0]}")
    print(f"  Coil 1 (motor_stopped):    {coils[1]}")
    print(f"  Coil 2 (fault_alarm):      {coils[2]}")
    print(f"  Coil 3 (conveyor_running): {coils[3]}")
    print(f"  Coil 4 (sensor_1):         {coils[4]}")
    print(f"  Coil 5 (sensor_2):         {coils[5]}")

    return coils


def write_test(client: ModbusTcpClient):
    """Test writing a coil (toggle motor)"""
    print("\nWrite Test - Toggling motor_running...")

    # Read current state
    result = client.read_coils(address=0, count=1, slave=1)
    if result.isError():
        print(f"Error reading coil: {result}")
        return

    current = result.bits[0]
    print(f"  Current motor_running: {current}")

    # Toggle
    new_value = not current
    print(f"  Writing motor_running: {new_value}")

    write_result = client.write_coil(address=0, value=new_value, slave=1)
    if write_result.isError():
        print(f"Error writing coil: {write_result}")
        return

    # Verify
    time.sleep(0.1)
    result = client.read_coils(address=0, count=1, slave=1)
    if not result.isError():
        print(f"  Verified motor_running: {result.bits[0]}")


def continuous_monitor(client: ModbusTcpClient, interval: float = 1.0):
    """Continuously read and display PLC state"""
    print(f"\nStarting continuous monitoring (interval: {interval}s)")
    print("Press Ctrl+C to stop...\n")

    try:
        while True:
            # Read registers
            result = client.read_holding_registers(address=100, count=4, slave=1)
            if not result.isError():
                regs = result.registers
                print(f"Speed: {regs[0]:3}% | Current: {regs[1]/10:5.1f}A | "
                      f"Temp: {regs[2]/10:5.1f}C | Pressure: {regs[3]:3} PSI", end="")

            # Read coils
            result = client.read_coils(address=0, count=3, slave=1)
            if not result.isError():
                coils = result.bits[:3]
                status = "RUN" if coils[0] else "STOP"
                fault = " FAULT!" if coils[2] else ""
                print(f" | Motor: {status}{fault}")
            else:
                print()

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test Modbus TCP connection to Micro 820 PLC"
    )
    parser.add_argument(
        "--host", "-H",
        default=DEFAULT_PLC_IP,
        help=f"PLC IP address (default: {DEFAULT_PLC_IP})"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PLC_PORT,
        help=f"Modbus TCP port (default: {DEFAULT_PLC_PORT})"
    )
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Enable continuous monitoring mode"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Monitoring interval in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--write-test", "-w",
        action="store_true",
        help="Run write test (toggles motor_running coil)"
    )

    args = parser.parse_args()

    print("=" * 55)
    print("  FactoryLM - Micro 820 Connection Test")
    print("=" * 55)

    client = test_connection(args.host, args.port)
    if not client:
        sys.exit(1)

    try:
        # Initial read
        read_registers(client)
        read_coils(client)

        # Optional write test
        if args.write_test:
            response = input("\nRun write test? This will toggle motor_running (y/n): ")
            if response.lower() == 'y':
                write_test(client)

        # Optional continuous monitoring
        if args.monitor:
            continuous_monitor(client, args.interval)
        else:
            print("\nTip: Use --monitor flag for continuous monitoring")

    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        client.close()
        print("Connection closed")


if __name__ == "__main__":
    main()
