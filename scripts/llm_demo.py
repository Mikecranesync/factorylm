"""
FactoryLM Demo: Ask questions about your factory via LLM

This script connects to a Micro 820 PLC via Modbus TCP and allows
you to ask natural language questions about the factory state.
An LLM analyzes the live machine data and provides intelligent responses.

Usage:
    python llm_demo.py
    python llm_demo.py --host 192.168.1.100
    python llm_demo.py --demo  # Run without PLC connection

Requirements:
    pip install pymodbus python-dotenv groq
"""

from pymodbus.client import ModbusTcpClient
from dotenv import load_dotenv
import argparse
import os
import sys

# Load environment variables
load_dotenv()

# Try to import FactoryLM core (if installed)
try:
    from factorylm import create_llm_client
    HAS_FACTORYLM = True
except ImportError:
    HAS_FACTORYLM = False
    try:
        import groq
        HAS_GROQ = True
    except ImportError:
        HAS_GROQ = False

# Configuration from environment
PLC_IP = os.getenv("PLC_HOST", "192.168.1.100")
PLC_PORT = int(os.getenv("PLC_PORT", "502"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")


class FactoryState:
    """Current factory state from PLC"""

    def __init__(self, registers: list, coils: list):
        self.motor_speed = registers[0] if len(registers) > 0 else 0
        self.motor_current = registers[1] / 10.0 if len(registers) > 1 else 0
        self.temperature = registers[2] / 10.0 if len(registers) > 2 else 0
        self.pressure = registers[3] if len(registers) > 3 else 0
        self.conveyor_speed = registers[4] if len(registers) > 4 else 0
        self.error_code = registers[5] if len(registers) > 5 else 0

        self.motor_running = coils[0] if len(coils) > 0 else False
        self.motor_stopped = coils[1] if len(coils) > 1 else True
        self.fault_alarm = coils[2] if len(coils) > 2 else False
        self.conveyor_running = coils[3] if len(coils) > 3 else False
        self.sensor_1 = coils[4] if len(coils) > 4 else False
        self.sensor_2 = coils[5] if len(coils) > 5 else False

    @classmethod
    def create_demo(cls) -> "FactoryState":
        """Create a demo state without PLC connection"""
        registers = [75, 25, 452, 100, 50, 0]  # speed, current*10, temp*10, pressure, conv, err
        coils = [True, False, False, True, False, True]
        return cls(registers, coils)

    def to_context(self) -> str:
        """Format for LLM context injection"""
        status = "RUNNING" if self.motor_running else "STOPPED"
        fault = "!! FAULT ACTIVE !!" if self.fault_alarm else "OK"
        conv_status = f"RUNNING at {self.conveyor_speed}%" if self.conveyor_running else "STOPPED"

        return f"""
CURRENT FACTORY STATE (live data from Micro 820 PLC):
======================================================
Motor Status:     {status}
Motor Speed:      {self.motor_speed}%
Motor Current:    {self.motor_current:.1f} A
Temperature:      {self.temperature:.1f} C
Pressure:         {self.pressure} PSI
Conveyor:         {conv_status}
Sensor 1:         {'PART DETECTED' if self.sensor_1 else 'Clear'}
Sensor 2:         {'PART DETECTED' if self.sensor_2 else 'Clear'}
System Status:    {fault}
Error Code:       {self.error_code if self.error_code else 'None'}
======================================================
"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/LLM"""
        return {
            "motor_speed": self.motor_speed,
            "motor_current": self.motor_current,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "conveyor_speed": self.conveyor_speed,
            "error_code": self.error_code,
            "motor_running": self.motor_running,
            "motor_stopped": self.motor_stopped,
            "fault_alarm": self.fault_alarm,
            "conveyor_running": self.conveyor_running,
            "sensor_1": self.sensor_1,
            "sensor_2": self.sensor_2,
        }


def read_plc_state(host: str, port: int) -> FactoryState:
    """Read current state from PLC"""
    client = ModbusTcpClient(host, port=port, timeout=5)

    if not client.connect():
        raise ConnectionError(f"Cannot connect to PLC at {host}:{port}")

    try:
        # Read holding registers 100-105
        reg_result = client.read_holding_registers(address=100, count=6, slave=1)
        if reg_result.isError():
            raise IOError(f"Register read error: {reg_result}")

        # Read coils 0-5
        coil_result = client.read_coils(address=0, count=6, slave=1)
        if coil_result.isError():
            raise IOError(f"Coil read error: {coil_result}")

        return FactoryState(reg_result.registers, coil_result.bits[:6])
    finally:
        client.close()


def get_system_prompt() -> str:
    """Return the system prompt for the LLM"""
    return """You are FactoryLM, an AI assistant for factory operators.
You have access to real-time machine data from an Allen-Bradley Micro 820 PLC
connected to a Factory I/O simulation.

Your job is to:
1. Analyze the machine state provided
2. Answer operator questions clearly and concisely
3. Provide actionable recommendations
4. Alert to any concerning values

Normal operating ranges:
- Temperature: 20-60 C (warn above 50 C, critical above 70 C)
- Motor current: 0-5 A (warn above 4 A)
- Pressure: 80-120 PSI
- Motor speed: 0-100%

Error codes:
- 0: No error
- 1: Motor overload
- 2: Temperature high
- 3: Conveyor jam
- 4: Sensor failure
- 5: Communication loss

Be direct and helpful. Use plain language suitable for factory floor operators.
Keep responses concise but informative.
"""


def ask_llm(question: str, state: FactoryState) -> str:
    """Ask the LLM about the factory state"""

    full_prompt = f"""
{state.to_context()}

OPERATOR QUESTION: {question}

Please analyze the current factory state and answer the operator's question.
"""

    if HAS_FACTORYLM:
        # Use FactoryLM abstraction
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        llm = create_llm_client(LLM_PROVIDER, api_key)
        response = llm.analyze_machine_state(question, state.to_dict())
        return response.text

    elif HAS_GROQ:
        # Direct GROQ call
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return "Error: GROQ_API_KEY not set in environment"

        client = groq.Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.3,  # Lower for more factual responses
            max_tokens=500
        )
        return response.choices[0].message.content

    else:
        return ("Error: No LLM client available. "
                "Install factorylm-core or groq package and set API key.")


def main():
    """Interactive LLM demo"""
    parser = argparse.ArgumentParser(
        description="FactoryLM - Ask questions about your factory"
    )
    parser.add_argument(
        "--host", "-H",
        default=PLC_IP,
        help=f"PLC IP address (default: {PLC_IP})"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=PLC_PORT,
        help=f"Modbus TCP port (default: {PLC_PORT})"
    )
    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run in demo mode without PLC connection"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  FactoryLM - LLM-Powered Factory Assistant")
    print("  Connected to Micro 820 via Modbus TCP")
    print("=" * 60)

    # Check for LLM availability
    if not HAS_FACTORYLM and not HAS_GROQ:
        print("\nWarning: No LLM client available!")
        print("Install with: pip install groq")
        print("Then set GROQ_API_KEY in .env file")

    # Initial state read
    demo_mode = args.demo
    state = None

    print("\nReading initial PLC state...")
    try:
        if demo_mode:
            state = FactoryState.create_demo()
            print("Running in DEMO MODE with simulated data")
        else:
            state = read_plc_state(args.host, args.port)
        print(state.to_context())
    except Exception as e:
        print(f"Error connecting to PLC: {e}")
        print("\nSwitching to DEMO MODE with simulated data...")
        state = FactoryState.create_demo()
        demo_mode = True
        print(state.to_context())

    print("\nAsk questions about your factory (type 'quit' to exit)")
    print("Examples:")
    print("  - Why is the temperature rising?")
    print("  - Is the motor current normal?")
    print("  - What should I check before starting the conveyor?")
    print("  - Is there anything concerning in the current state?")
    print("-" * 60)

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if question.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break

        if not question:
            continue

        # Special commands
        if question.lower() == 'state':
            print(state.to_context())
            continue

        if question.lower() == 'refresh':
            try:
                if not demo_mode:
                    state = read_plc_state(args.host, args.port)
                print("State refreshed")
                print(state.to_context())
            except Exception as e:
                print(f"Error refreshing: {e}")
            continue

        # Refresh PLC state before each question (unless demo mode)
        if not demo_mode:
            try:
                state = read_plc_state(args.host, args.port)
            except Exception:
                pass  # Use last known state

        print("\nFactoryLM: ", end="", flush=True)

        try:
            response = ask_llm(question, state)
            print(response)
        except Exception as e:
            print(f"Error getting response: {e}")


if __name__ == "__main__":
    main()
