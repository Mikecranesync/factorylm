#!/usr/bin/env python3
"""
FactoryLM Edge Server - Modbus TCP Server with GPIO
Runs on Raspberry Pi to bridge Modbus to physical I/O

Usage:
    sudo python edge_server.py
    sudo python edge_server.py --host 0.0.0.0 --port 502 --config config.json
"""

import asyncio
import logging
from typing import Dict, List
import json
import signal

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.device import ModbusDeviceIdentification

try:
    import RPi.GPIO as GPIO
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    print("Warning: RPi.GPIO not available, running in simulation mode")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GPIOManager:
    """Manages GPIO pins for Modbus coil mapping"""

    def __init__(self, config: Dict):
        self.config = config
        self.inputs: Dict[int, int] = {}   # coil -> GPIO BCM pin
        self.outputs: Dict[int, int] = {}  # coil -> GPIO BCM pin
        self.input_names: Dict[int, str] = {}
        self.output_names: Dict[int, str] = {}

        if PI_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

        self._setup_pins()

    def _setup_pins(self):
        """Configure GPIO pins from config"""
        for mapping in self.config.get('inputs', []):
            coil = mapping['coil']
            pin = mapping['gpio']
            name = mapping.get('name', f'Input_{coil}')
            self.inputs[coil] = pin
            self.input_names[coil] = name
            if PI_AVAILABLE:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                logger.info(f"Input: Coil {coil} -> GPIO {pin} ({name})")
            else:
                logger.info(f"Input (sim): Coil {coil} -> GPIO {pin} ({name})")

        for mapping in self.config.get('outputs', []):
            coil = mapping['coil']
            pin = mapping['gpio']
            name = mapping.get('name', f'Output_{coil}')
            self.outputs[coil] = pin
            self.output_names[coil] = name
            if PI_AVAILABLE:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
                logger.info(f"Output: Coil {coil} -> GPIO {pin} ({name})")
            else:
                logger.info(f"Output (sim): Coil {coil} -> GPIO {pin} ({name})")

    def read_input(self, coil: int) -> bool:
        """Read physical input state"""
        if coil in self.inputs:
            if PI_AVAILABLE:
                return GPIO.input(self.inputs[coil]) == GPIO.HIGH
            else:
                # Simulation mode - always return False
                return False
        return False

    def write_output(self, coil: int, value: bool):
        """Write physical output state"""
        if coil in self.outputs:
            name = self.output_names.get(coil, f'Output_{coil}')
            if PI_AVAILABLE:
                GPIO.output(self.outputs[coil], GPIO.HIGH if value else GPIO.LOW)
            logger.debug(f"Output {name} (coil {coil}) = {value}")

    def read_all_inputs(self) -> Dict[int, bool]:
        """Read all input states"""
        return {coil: self.read_input(coil) for coil in self.inputs}

    def cleanup(self):
        """Release GPIO resources"""
        if PI_AVAILABLE:
            GPIO.cleanup()
            logger.info("GPIO cleanup complete")


class EdgeDataBlock(ModbusSequentialDataBlock):
    """Custom data block that syncs with GPIO"""

    def __init__(self, gpio_manager: GPIOManager, address: int, values: List[bool]):
        super().__init__(address, values)
        self.gpio = gpio_manager

    def setValues(self, address: int, values):
        """Called when Modbus client writes coils"""
        # Convert to list if needed
        if not isinstance(values, list):
            values = [values]

        super().setValues(address, values)

        # Sync outputs to GPIO
        for i, val in enumerate(values):
            coil = address + i
            if coil in self.gpio.outputs:
                self.gpio.write_output(coil, bool(val))
                logger.info(f"Write: Coil {coil} = {val}")

    def getValues(self, address: int, count: int = 1):
        """Called when Modbus client reads coils"""
        # First, update input coils from GPIO
        for coil in self.gpio.inputs:
            if address <= coil < address + count:
                val = self.gpio.read_input(coil)
                super().setValues(coil, [val])

        return super().getValues(address, count)


def load_config(config_file: str) -> Dict:
    """Load configuration from file or return defaults"""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded configuration from {config_file}")
            return config
    except FileNotFoundError:
        logger.warning(f"Config file {config_file} not found, using defaults")
        return {
            "name": "Factory I/O Default",
            "description": "Basic simulation with buttons and LEDs",
            "inputs": [
                {"coil": 0, "gpio": 17, "name": "Start_Button"},
                {"coil": 1, "gpio": 27, "name": "Stop_Button"},
                {"coil": 2, "gpio": 22, "name": "E_Stop"}
            ],
            "outputs": [
                {"coil": 10, "gpio": 5, "name": "LED_Green"},
                {"coil": 11, "gpio": 6, "name": "LED_Red"},
                {"coil": 12, "gpio": 13, "name": "Relay1"},
                {"coil": 13, "gpio": 19, "name": "Relay2"}
            ]
        }


async def run_server(host: str = "0.0.0.0", port: int = 502, config_file: str = "config.json"):
    """Start the Modbus TCP server"""

    config = load_config(config_file)

    # Initialize GPIO
    gpio = GPIOManager(config)

    # Create Modbus data store with 100 coils and 100 holding registers
    coils = EdgeDataBlock(gpio, 0, [False] * 100)
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [False] * 100),  # Discrete Inputs
        co=coils,                                         # Coils (with GPIO sync)
        hr=ModbusSequentialDataBlock(0, [0] * 100),      # Holding Registers
        ir=ModbusSequentialDataBlock(0, [0] * 100),      # Input Registers
    )
    context = ModbusServerContext(slaves=store, single=True)

    # Device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = "FactoryLM"
    identity.ProductCode = "EDGE-01"
    identity.ProductName = "FactoryLM Edge Device"
    identity.ModelName = "Raspberry Pi Edge Server"
    identity.MajorMinorRevision = "1.0.0"

    logger.info("=" * 60)
    logger.info("FactoryLM Edge Server")
    logger.info("=" * 60)
    logger.info(f"Configuration: {config.get('name', 'Default')}")
    logger.info(f"Server address: {host}:{port}")
    logger.info(f"GPIO mode: {'Hardware' if PI_AVAILABLE else 'Simulation'}")
    logger.info(f"Inputs: {list(gpio.inputs.keys())} -> GPIO {list(gpio.inputs.values())}")
    logger.info(f"Outputs: {list(gpio.outputs.keys())} -> GPIO {list(gpio.outputs.values())}")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop")

    try:
        await StartAsyncTcpServer(
            context=context,
            identity=identity,
            address=(host, port),
        )
    except PermissionError:
        logger.error(f"Permission denied for port {port}. Try running with sudo.")
        raise
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error(f"Port {port} is already in use. Check for other Modbus servers.")
        raise
    finally:
        gpio.cleanup()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="FactoryLM Edge Modbus Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    sudo python edge_server.py
    sudo python edge_server.py --port 5020
    sudo python edge_server.py --config my_config.json

Note: Port 502 requires root privileges. Use --port 5020 for testing without sudo.
        """
    )
    parser.add_argument("--host", default="0.0.0.0", help="Server bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--config", default="config.json", help="Configuration file (default: config.json)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(run_server(args.host, args.port, args.config))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except PermissionError:
        print(f"\nError: Cannot bind to port {args.port}. Try:")
        print(f"  sudo python edge_server.py --port {args.port}")
        print("  or use a port > 1024 without sudo:")
        print("  python edge_server.py --port 5020")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
