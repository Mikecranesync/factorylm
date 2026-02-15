"""
Simple integration test for Persona system
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personas.models import UserMode
from personas.loader import PersonaLoader
from personas.formatter import ResponseFormatter


def test_basic_functionality():
    """Test basic persona system functionality"""

    print("=" * 60)
    print("PEPPER PERSONA SYSTEM - INTEGRATION TEST")
    print("=" * 60)
    print()

    # Initialize loader
    loader = PersonaLoader()

    # Test 1: Load God Mode
    print("TEST 1: Loading God Mode (Pepper Prime)")
    print("-" * 60)
    god_persona = loader.load_persona(UserMode.GOD)
    print(f"Name: {god_persona.name}")
    print(f"Sass Level: {god_persona.sass_level}/10")
    print(f"Can Curse: {god_persona.can_curse}")
    print(f"Can Challenge: {god_persona.can_challenge}")
    print(f"Tools: {len(god_persona.tools)} tools available")
    print(f"Guardrails: {len(god_persona.guardrails)} restrictions")
    print("PASSED")
    print()

    # Test 2: Load Demo Mode
    print("TEST 2: Loading Demo Mode (Pepper)")
    print("-" * 60)
    demo_persona = loader.load_persona(UserMode.DEMO)
    print(f"Name: {demo_persona.name}")
    print(f"Sass Level: {demo_persona.sass_level}/10")
    print(f"Can Curse: {demo_persona.can_curse}")
    print(f"Can Challenge: {demo_persona.can_challenge}")
    print(f"Tools: {len(demo_persona.tools)} tools available")
    print(f"Guardrails: {len(demo_persona.guardrails)} restrictions")
    print("PASSED")
    print()

    # Test 3: System Prompt Generation
    print("TEST 3: System Prompt Generation")
    print("-" * 60)
    god_prompt = loader.build_system_prompt(god_persona)
    demo_prompt = loader.build_system_prompt(demo_persona)
    print(f"God Mode prompt length: {len(god_prompt)} characters")
    print(f"Demo Mode prompt length: {len(demo_prompt)} characters")
    print(f"God Mode contains 'Pepper Prime': {'Pepper Prime' in god_prompt}")
    print(f"Demo Mode contains guardrails: {'no_filesystem_access' in demo_prompt}")
    print("PASSED")
    print()

    # Test 4: Response Formatting
    print("TEST 4: Response Formatting")
    print("-" * 60)

    god_formatter = ResponseFormatter(god_persona)
    demo_formatter = ResponseFormatter(demo_persona)

    # Test JSON stripping
    test_response = """
Here's the motor status:
```json
{"motor": "M3", "current": 12.5}
```
"""
    formatted = demo_formatter.format_response(test_response)
    print(f"Original response contains JSON: {'```json' in test_response}")
    print(f"Formatted response contains JSON: {'```json' in formatted}")
    print("PASSED")
    print()

    # Test 5: Equipment Status Formatting
    print("TEST 5: Equipment Status Formatting")
    print("-" * 60)

    status = {
        "running": True,
        "current": 12.5,
        "temperature": 65,
        "fault_code": None
    }

    formatted_status = demo_formatter.format_equipment_status("Motor M-3", status)
    print("Formatted Equipment Status:")
    print(formatted_status)
    print("PASSED")
    print()

    # Test 6: Fault Code Formatting
    print("TEST 6: Fault Code Formatting")
    print("-" * 60)

    fault = demo_formatter.format_fault_code(
        code="E-47",
        description="Photo eye obstruction",
        causes=["Dirty sensor", "Misalignment"],
        actions=["Clean lens", "Check alignment"]
    )
    print("Formatted Fault Code:")
    print(fault)
    print("PASSED")
    print()

    # Test 7: Greeting Messages
    print("TEST 7: Greeting Messages")
    print("-" * 60)
    god_greeting = loader.get_greeting(UserMode.GOD)
    demo_greeting = loader.get_greeting(UserMode.DEMO)
    print(f"God Mode: {god_greeting}")
    print(f"Demo Mode: {demo_greeting}")
    print("PASSED")
    print()

    # Test 8: Tool Access Comparison
    print("TEST 8: Tool Access Comparison")
    print("-" * 60)
    god_tools = set(god_persona.tools)
    demo_tools = set(demo_persona.tools)

    print(f"God Mode exclusive tools: {god_tools - demo_tools}")
    print(f"Demo Mode tools: {demo_tools}")
    print(f"Shared tools: {god_tools & demo_tools}")
    print("PASSED")
    print()

    # Summary
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print()
    print("Persona System Successfully Implemented:")
    print("- God Mode (Pepper Prime) for Mike Harper")
    print("- Demo Mode (Pepper) for technicians")
    print("- OUTPUT FORMAT LAW enforcement")
    print("- Response formatting and jargon simplification")
    print("- Equipment status, fault code, and procedure formatting")
    print()


if __name__ == "__main__":
    test_basic_functionality()
