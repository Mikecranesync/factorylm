#!/usr/bin/env python3
"""
Real-time PLC I/O Monitor

Interactive display showing all digital inputs and outputs
like the LED panel on a PLC front.

Usage:
    python tools/plc_monitor.py

Press Ctrl+C to exit.
"""

import sys
import time
from datetime import datetime

from pymodbus.client import ModbusTcpClient


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def clear_screen():
    print("\033[2J\033[H", end="")


def indicator(on: bool) -> str:
    if on:
        return f"{Colors.BG_GREEN}{Colors.BOLD} ON  {Colors.RESET}"
    else:
        return f"{Colors.DIM} off {Colors.RESET}"


def draw_io_panel(program_vars: list, inputs: list, outputs: list, cycle_time_ms: float, cycle_count: int):
    """Draw the I/O panel display."""
    clear_screen()

    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    print(f"{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}MICRO 820 PLC - REAL-TIME I/O MONITOR{Colors.RESET}                                {Colors.CYAN}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.DIM}192.168.1.100:502{Colors.RESET}    {now}    Cycle: {cycle_count:,}  ({cycle_time_ms:.1f}ms)        {Colors.CYAN}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╠════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")

    # Program Variables
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.BLUE}PROGRAM VARIABLES (coils 0-6){Colors.RESET}                                      {Colors.CYAN}║{Colors.RESET}")
    var_names = ['motor_run', 'motor_stp', 'fault', 'conveyor', 'sensor1', 'sensor2', 'e_stop']
    row = "  "
    for i in range(7):
        row += f" {var_names[i][:8]:8s}:{indicator(program_vars[i])}"
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}{row}  {Colors.CYAN}║{Colors.RESET}")

    print(f"{Colors.BOLD}{Colors.CYAN}╠════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")

    # Physical Digital Inputs
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}PHYSICAL INPUTS _IO_EM_DI_00 to DI_07 (coils 7-14){Colors.RESET}                {Colors.CYAN}║{Colors.RESET}")
    row1 = "  "
    for i in range(4):
        row1 += f"  DI_{i:02d}:{indicator(inputs[i])}"
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}{row1}                  {Colors.CYAN}║{Colors.RESET}")

    row2 = "  "
    for i in range(4, 8):
        row2 += f"  DI_{i:02d}:{indicator(inputs[i])}"
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}{row2}                  {Colors.CYAN}║{Colors.RESET}")

    print(f"{Colors.BOLD}{Colors.CYAN}╠════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")

    # Physical Digital Outputs
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}{Colors.GREEN}PHYSICAL OUTPUTS _IO_EM_DO_00, DO_01, DO_03 (coils 15-17){Colors.RESET}         {Colors.CYAN}║{Colors.RESET}")
    out_row = f"    DO_00:{indicator(outputs[0])}  DO_01:{indicator(outputs[1])}  DO_03:{indicator(outputs[2])}"
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}{out_row}                  {Colors.CYAN}║{Colors.RESET}")

    print(f"{Colors.BOLD}{Colors.CYAN}╠════════════════════════════════════════════════════════════════════════╣{Colors.RESET}")

    # Summary
    vars_on = [var_names[i] for i, v in enumerate(program_vars) if v]
    inputs_on = [f"DI_{i:02d}" for i, v in enumerate(inputs) if v]
    outputs_on = [f"DO_{i:02d}" if i < 2 else "DO_03" for i, v in enumerate(outputs) if v]

    all_on = vars_on + inputs_on + outputs_on
    on_str = ", ".join(all_on) if all_on else "none"

    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {Colors.BOLD}ACTIVE:{Colors.RESET} {on_str:<62} {Colors.CYAN}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    print()
    print(f"  {Colors.DIM}Press Ctrl+C to exit{Colors.RESET}")

    sys.stdout.flush()


def main():
    host = "192.168.1.100"
    port = 502

    print(f"Connecting to PLC at {host}:{port}...")

    client = ModbusTcpClient(host=host, port=port, timeout=3)
    if not client.connect():
        print("Failed to connect!")
        sys.exit(1)

    print("Connected! Starting monitor...")
    time.sleep(0.5)

    cycle_count = 0

    try:
        while True:
            start = time.perf_counter()

            # Read all coils 0-17 in one request
            result = client.read_coils(address=0, count=18)
            if result.isError():
                program_vars = [0] * 7
                inputs = [0] * 8
                outputs = [0] * 3
            else:
                bits = [int(b) for b in result.bits[:18]]
                program_vars = bits[0:7]      # Coils 0-6
                inputs = bits[7:15]           # Coils 7-14 (_IO_EM_DI_00 to DI_07)
                outputs = bits[15:18]         # Coils 15-17 (_IO_EM_DO_00, DO_01, DO_03)

            cycle_time = (time.perf_counter() - start) * 1000
            cycle_count += 1

            draw_io_panel(program_vars, inputs, outputs, cycle_time, cycle_count)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
