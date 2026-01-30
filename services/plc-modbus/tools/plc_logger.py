#!/usr/bin/env python3
"""
Async PLC State Logger

Monitors all digital inputs and outputs on the Micro 820 PLC
and logs state changes to a file with timestamps.

Usage:
    python tools/plc_logger.py [--duration 300] [--output plc_log.csv]
"""

import argparse
import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

from pymodbus.client import ModbusTcpClient


class PLCLogger:
    """Async logger for PLC state changes."""

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 502,
        num_inputs: int = 8,
        num_outputs: int = 3,
        poll_interval: float = 0.05,
    ):
        self.host = host
        self.port = port
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs
        self.poll_interval = poll_interval
        self.client = None
        self.log_entries = []
        self.start_time = None

        # State tracking
        self.last_inputs = None
        self.last_outputs = None

    def connect(self) -> bool:
        """Connect to PLC."""
        self.client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=3,
        )
        return self.client.connect()

    def disconnect(self):
        """Disconnect from PLC."""
        if self.client:
            self.client.close()

    def read_state(self) -> tuple[list[int], list[int]]:
        """Read all inputs and outputs."""
        # Inputs at coils 8+
        inp_result = self.client.read_coils(address=8, count=self.num_inputs)
        if inp_result.isError():
            return self.last_inputs or [0] * self.num_inputs, self.last_outputs or [0] * self.num_outputs
        inp_bits = list(inp_result.bits)
        inputs = [int(inp_bits[i]) if i < len(inp_bits) else 0 for i in range(self.num_inputs)]

        # Outputs at coils 16+
        out_result = self.client.read_coils(address=16, count=self.num_outputs)
        if out_result.isError():
            return inputs, self.last_outputs or [0] * self.num_outputs
        out_bits = list(out_result.bits)
        outputs = [int(out_bits[i]) if i < len(out_bits) else 0 for i in range(self.num_outputs)]

        return inputs, outputs

    def log_change(self, channel_type: str, channel: int, old_val: int, new_val: int):
        """Log a state change."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        timestamp = datetime.now().isoformat(timespec='milliseconds')

        entry = {
            'timestamp': timestamp,
            'elapsed_sec': round(elapsed, 3),
            'type': channel_type,
            'channel': channel,
            'old_value': old_val,
            'new_value': new_val,
        }
        self.log_entries.append(entry)

        # Print to console
        direction = "ON " if new_val else "OFF"
        prefix = "DI" if channel_type == "INPUT" else "DO"
        print(f"[{elapsed:7.3f}s] {prefix}_{channel:02d} -> {direction}")

    async def monitor(self, duration: float):
        """Monitor PLC for specified duration."""
        self.start_time = datetime.now()
        end_time = self.start_time.timestamp() + duration

        # Get initial state
        self.last_inputs, self.last_outputs = self.read_state()

        # Log initial state
        print("\n=== INITIAL STATE ===")
        print(f"Inputs ON:  {[i for i, v in enumerate(self.last_inputs) if v]}")
        print(f"Outputs ON: {[i for i, v in enumerate(self.last_outputs) if v]}")
        print(f"\n=== MONITORING FOR {duration}s ===\n")

        changes = 0
        polls = 0

        while datetime.now().timestamp() < end_time:
            inputs, outputs = self.read_state()
            polls += 1

            # Check input changes
            for i in range(self.num_inputs):
                if inputs[i] != self.last_inputs[i]:
                    self.log_change("INPUT", i, self.last_inputs[i], inputs[i])
                    changes += 1

            # Check output changes
            for i in range(self.num_outputs):
                if outputs[i] != self.last_outputs[i]:
                    self.log_change("OUTPUT", i, self.last_outputs[i], outputs[i])
                    changes += 1

            self.last_inputs = inputs
            self.last_outputs = outputs

            await asyncio.sleep(self.poll_interval)

        print(f"\n=== DONE ===")
        print(f"Duration: {duration}s | Polls: {polls} | Changes: {changes}")

    def save_log(self, filepath: str):
        """Save log to CSV file."""
        if not self.log_entries:
            print("No changes recorded.")
            return

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'elapsed_sec', 'type', 'channel', 'old_value', 'new_value'
            ])
            writer.writeheader()
            writer.writerows(self.log_entries)

        print(f"Saved {len(self.log_entries)} entries to {filepath}")


async def main():
    parser = argparse.ArgumentParser(description="Log PLC state changes")
    parser.add_argument("--host", default="192.168.1.100", help="PLC IP address")
    parser.add_argument("--duration", type=float, default=120, help="Monitoring duration (seconds)")
    parser.add_argument("--output", default="plc_log.csv", help="Output CSV file")
    parser.add_argument("--inputs", type=int, default=12, help="Number of digital inputs")
    parser.add_argument("--outputs", type=int, default=6, help="Number of digital outputs")
    args = parser.parse_args()

    logger = PLCLogger(
        host=args.host,
        num_inputs=args.inputs,
        num_outputs=args.outputs,
    )

    print(f"Connecting to PLC at {args.host}...")
    if not logger.connect():
        print("Failed to connect!")
        sys.exit(1)
    print("Connected!")

    try:
        await logger.monitor(args.duration)
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        logger.disconnect()
        logger.save_log(args.output)


if __name__ == "__main__":
    asyncio.run(main())
