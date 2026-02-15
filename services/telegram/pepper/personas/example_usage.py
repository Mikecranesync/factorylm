"""
Example usage of PEPPER Persona system

Demonstrates how to:
1. Load personas based on user mode
2. Generate system prompts
3. Format responses
4. Switch between God and Demo modes
"""

from models import UserMode
from loader import PersonaLoader
from formatter import ResponseFormatter


def main():
    """Demonstrate persona system usage"""

    # Initialize loader
    loader = PersonaLoader()

    print("=" * 60)
    print("PEPPER PERSONA SYSTEM - USAGE EXAMPLES")
    print("=" * 60)
    print()

    # List available personas
    print("Available Personas:")
    personas = loader.list_available_personas()
    for persona_name in personas:
        print(f"  - {persona_name}")
    print()

    # Example 1: God Mode (Mike)
    print("-" * 60)
    print("EXAMPLE 1: God Mode (Pepper Prime)")
    print("-" * 60)

    god_persona = loader.load_persona(UserMode.GOD)

    print(f"Name: {god_persona.name}")
    print(f"Greeting: {loader.get_greeting(UserMode.GOD)}")
    print(f"Sass Level: {god_persona.sass_level}/10")
    print(f"Formality: {god_persona.formality}/10")
    print(f"Can Curse: {god_persona.can_curse}")
    print(f"Can Challenge: {god_persona.can_challenge}")
    print()

    print("Available Tools:")
    for tool in god_persona.tools[:5]:  # Show first 5
        print(f"  ✅ {tool}")
    print(f"  ... and {len(god_persona.tools) - 5} more")
    print()

    print("Guardrails:")
    for guardrail in god_persona.guardrails:
        print(f"  ⚠️ {guardrail}")
    print()

    # Generate system prompt for God mode
    print("System Prompt Preview (first 500 chars):")
    god_prompt = loader.build_system_prompt(god_persona)
    print(god_prompt[:500] + "...")
    print()

    # Format response in God mode
    god_formatter = ResponseFormatter(god_persona)

    print("Response Formatting:")
    raw_response = """
Boss, I checked the PLC. Here's the data:
```json
{"motor_m3": {"status": "running", "current": 12.5, "temp": 65}}
```
"""
    formatted = god_formatter.format_response(raw_response)
    print(f"Raw: {raw_response}")
    print(f"Formatted: {formatted}")
    print()

    # Technical output example
    print("Technical Output (when requested):")
    technical_request = "Show me the JSON for that motor"
    allow_tech = god_formatter.should_allow_technical(technical_request)
    print(f"Request: '{technical_request}'")
    print(f"Allow Technical: {allow_tech}")
    if allow_tech:
        formatted_tech = god_formatter.format_response(raw_response, allow_technical=True)
        print(f"Output: {formatted_tech}")
    print()

    # Example 2: Demo Mode (Customer/Technician)
    print("-" * 60)
    print("EXAMPLE 2: Demo Mode (Pepper)")
    print("-" * 60)

    demo_persona = loader.load_persona(UserMode.DEMO)

    print(f"Name: {demo_persona.name}")
    print(f"Greeting: {loader.get_greeting(UserMode.DEMO)}")
    print(f"Sass Level: {demo_persona.sass_level}/10")
    print(f"Formality: {demo_persona.formality}/10")
    print(f"Can Curse: {demo_persona.can_curse}")
    print(f"Can Challenge: {demo_persona.can_challenge}")
    print()

    print("Available Tools:")
    for tool in demo_persona.tools:
        print(f"  ✅ {tool}")
    print()

    print("Guardrails:")
    for guardrail in demo_persona.guardrails:
        print(f"  🚫 {guardrail}")
    print()

    # Format response in Demo mode
    demo_formatter = ResponseFormatter(demo_persona)

    print("Response Formatting:")
    raw_technical = """
I checked the REST API endpoint. The HTTP response returned a 404 status code.
The JSON payload shows the motor has a fault code.
```json
{"motor": "M3", "fault": "E-47"}
```
"""
    formatted_demo = demo_formatter.format_response(raw_technical)
    print(f"Raw Technical: {raw_technical}")
    print(f"Formatted (Jargon Simplified): {formatted_demo}")
    print()

    # Example 3: Equipment Status Formatting
    print("-" * 60)
    print("EXAMPLE 3: Equipment Status Formatting")
    print("-" * 60)

    equipment_status = {
        "running": True,
        "current": 12.5,
        "temperature": 65,
        "fault_code": None,
        "last_maintenance": "2026-02-10",
    }

    formatted_status = demo_formatter.format_equipment_status(
        "Conveyor Motor M-3",
        equipment_status
    )
    print(formatted_status)
    print()

    # Example 4: Fault Code Formatting
    print("-" * 60)
    print("EXAMPLE 4: Fault Code Explanation")
    print("-" * 60)

    fault_info = demo_formatter.format_fault_code(
        code="E-47",
        description="Photo eye obstruction detected at Station 4",
        causes=[
            "Dirty or obstructed sensor lens",
            "Sensor misalignment",
            "Product buildup blocking beam",
            "Sensor hardware failure"
        ],
        actions=[
            "Clean sensor lens with lint-free cloth",
            "Check sensor alignment (LED should be solid green)",
            "Clear any product buildup in sensor area",
            "Test sensor with hand blockage",
            "Replace sensor if issue persists"
        ]
    )
    print(fault_info)
    print()

    # Example 5: Procedure Formatting
    print("-" * 60)
    print("EXAMPLE 5: Maintenance Procedure")
    print("-" * 60)

    procedure = demo_formatter.format_procedure_steps(
        procedure_name="Photo Eye Sensor Maintenance - PE-404",
        steps=[
            "Lock out conveyor C-4 (LOTO station 4-B)",
            "Clean sensor lens with lint-free cloth",
            "Check alignment (LED should be solid green)",
            "If blinking: adjust mounting bracket until solid",
            "Test with hand blockage to verify operation",
            "Remove LOTO and resume operation"
        ],
        safety_notes=[
            "Verify LOTO before touching sensor area",
            "Wear safety glasses during maintenance"
        ]
    )
    print(procedure)
    print()

    # Example 6: Mode Comparison
    print("-" * 60)
    print("EXAMPLE 6: Mode Comparison")
    print("-" * 60)

    print("Tool Access Comparison:")
    print(f"{'Tool':<30} {'God Mode':<15} {'Demo Mode':<15}")
    print("-" * 60)

    all_tools = set(god_persona.tools + demo_persona.tools)
    for tool in sorted(all_tools):
        god_access = "✅" if tool in god_persona.tools else "❌"
        demo_access = "✅" if tool in demo_persona.tools else "❌"
        print(f"{tool:<30} {god_access:<15} {demo_access:<15}")
    print()

    # Example 7: System Prompt with Tool Filtering
    print("-" * 60)
    print("EXAMPLE 7: Tool Filtering")
    print("-" * 60)

    available_tools = ["plc_read", "vector_search", "manual_search"]
    filtered_prompt = loader.build_system_prompt(god_persona, available_tools)

    print("God Mode persona with limited tools available:")
    print(f"Persona tools: {god_persona.tools[:3]}... (full list)")
    print(f"Available tools: {available_tools}")
    print("\nFiltered tools in prompt:")
    for tool in available_tools:
        if tool in filtered_prompt:
            print(f"  ✅ {tool}")
    print()

    print("=" * 60)
    print("END OF EXAMPLES")
    print("=" * 60)


if __name__ == "__main__":
    main()
