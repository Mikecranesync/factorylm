"""
Test suite for PEPPER Persona system

Run with: pytest test_personas.py -v
"""

import pytest
from pathlib import Path

from .models import Persona, UserMode
from .loader import PersonaLoader
from .formatter import ResponseFormatter


@pytest.fixture
def personas_dir():
    """Get personas directory path"""
    return Path(__file__).parent


@pytest.fixture
def loader(personas_dir):
    """Create PersonaLoader instance"""
    return PersonaLoader(personas_dir)


@pytest.fixture
def god_persona(loader):
    """Load God mode persona"""
    return loader.load_persona(UserMode.GOD)


@pytest.fixture
def demo_persona(loader):
    """Load Demo mode persona"""
    return loader.load_persona(UserMode.DEMO)


class TestPersonaLoader:
    """Test PersonaLoader functionality"""

    def test_load_god_persona(self, god_persona):
        """Test loading God mode persona"""
        assert god_persona.mode == UserMode.GOD
        assert god_persona.name == "Pepper Prime"
        assert god_persona.sass_level == 7
        assert god_persona.formality == 3
        assert god_persona.can_curse is True
        assert god_persona.can_challenge is True

    def test_load_demo_persona(self, demo_persona):
        """Test loading Demo mode persona"""
        assert demo_persona.mode == UserMode.DEMO
        assert demo_persona.name == "Pepper"
        assert demo_persona.sass_level == 2
        assert demo_persona.formality == 6
        assert demo_persona.can_curse is False
        assert demo_persona.can_challenge is False

    def test_god_tools(self, god_persona):
        """Test God mode has correct tools"""
        assert "filesystem_write" in god_persona.tools
        assert "shell_execute" in god_persona.tools
        assert "ai_layer_3" in god_persona.tools

    def test_demo_tools(self, demo_persona):
        """Test Demo mode has restricted tools"""
        assert "filesystem_write" not in demo_persona.tools
        assert "shell_execute" not in demo_persona.tools
        assert "plc_read" in demo_persona.tools
        assert "vector_search" in demo_persona.tools

    def test_god_guardrails(self, god_persona):
        """Test God mode guardrails"""
        assert "no_plc_writes" in god_persona.guardrails
        assert "confirm_production_deploys" in god_persona.guardrails

    def test_demo_guardrails(self, demo_persona):
        """Test Demo mode has strict guardrails"""
        assert "no_plc_writes" in demo_persona.guardrails
        assert "no_filesystem_access" in demo_persona.guardrails
        assert "no_shell_execute" in demo_persona.guardrails
        assert "no_external_comms" in demo_persona.guardrails

    def test_persona_caching(self, loader):
        """Test personas are cached after first load"""
        persona1 = loader.load_persona(UserMode.GOD)
        persona2 = loader.load_persona(UserMode.GOD)
        assert persona1 is persona2  # Same object

    def test_reload_personas(self, loader):
        """Test persona reload clears cache"""
        persona1 = loader.load_persona(UserMode.GOD)
        loader.reload_personas()
        persona2 = loader.load_persona(UserMode.GOD)
        assert persona1 is not persona2  # Different objects

    def test_list_available_personas(self, loader):
        """Test listing available personas"""
        personas = loader.list_available_personas()
        assert "GOD" in personas
        assert "DEMO" in personas

    def test_get_greeting_god(self, loader):
        """Test God mode greeting"""
        greeting = loader.get_greeting(UserMode.GOD)
        assert "boss" in greeting.lower()

    def test_get_greeting_demo(self, loader):
        """Test Demo mode greeting"""
        greeting = loader.get_greeting(UserMode.DEMO)
        assert "pepper" in greeting.lower()
        assert "maintenance" in greeting.lower()

    def test_build_system_prompt_god(self, loader, god_persona):
        """Test system prompt generation for God mode"""
        prompt = loader.build_system_prompt(god_persona)
        assert "Pepper Prime" in prompt
        assert "GOD" in prompt
        assert "filesystem_write" in prompt
        assert "OUTPUT FORMAT LAW" in prompt

    def test_build_system_prompt_demo(self, loader, demo_persona):
        """Test system prompt generation for Demo mode"""
        prompt = loader.build_system_prompt(demo_persona)
        assert "Pepper" in prompt
        assert "DEMO" in prompt
        assert "vector_search" in prompt
        assert "no_filesystem_access" in prompt

    def test_build_system_prompt_with_filtered_tools(self, loader, god_persona):
        """Test system prompt with limited available tools"""
        available_tools = ["plc_read", "vector_search"]
        prompt = loader.build_system_prompt(god_persona, available_tools)
        # Should only show tools that are both in persona.tools AND available_tools
        assert "plc_read" in prompt
        # filesystem_write not in available_tools, should not appear
        # (even though it's in god_persona.tools)


class TestResponseFormatter:
    """Test ResponseFormatter functionality"""

    def test_format_response_strips_json_god_mode(self, god_persona):
        """Test JSON stripping in God mode (when not explicitly requested)"""
        formatter = ResponseFormatter(god_persona)
        content = """
Here's the data:
```json
{"motor": "M3", "current": 12.5}
```
"""
        formatted = formatter.format_response(content, allow_technical=False)
        assert "```json" not in formatted
        assert "motor" not in formatted.lower() or "Motor" in formatted  # Converted to plain English

    def test_format_response_allows_json_when_requested(self, god_persona):
        """Test technical output allowed when explicitly requested"""
        formatter = ResponseFormatter(god_persona)
        content = """
```json
{"motor": "M3", "current": 12.5}
```
"""
        formatted = formatter.format_response(content, allow_technical=True)
        assert "```json" in formatted
        # Original content preserved

    def test_format_response_demo_simplifies_jargon(self, demo_persona):
        """Test Demo mode simplifies technical jargon"""
        formatter = ResponseFormatter(demo_persona)
        content = "The API returned HTTP 404. Check the REST endpoint."

        formatted = formatter.format_response(content)
        assert "API" not in formatted or "interface" in formatted
        assert "REST" not in formatted or "web service" in formatted

    def test_status_indicator_success(self, god_persona):
        """Test success status indicator"""
        formatter = ResponseFormatter(god_persona)
        status = formatter.format_status_indicator(True, "Operation complete")
        assert "✅" in status
        assert "Operation complete" in status

    def test_status_indicator_failure(self, god_persona):
        """Test failure status indicator"""
        formatter = ResponseFormatter(god_persona)
        status = formatter.format_status_indicator(False, "Connection lost")
        assert "❌" in status
        assert "Connection lost" in status

    def test_format_equipment_status(self, demo_persona):
        """Test equipment status formatting"""
        formatter = ResponseFormatter(demo_persona)
        status = {
            "running": True,
            "current": 12.5,
            "temperature": 65,
            "fault_code": None,
        }
        formatted = formatter.format_equipment_status("Motor M-3", status)
        assert "Motor M-3" in formatted
        assert "✅" in formatted
        assert "12.5A" in formatted
        assert "65°C" in formatted

    def test_format_fault_code(self, demo_persona):
        """Test fault code formatting"""
        formatter = ResponseFormatter(demo_persona)
        formatted = formatter.format_fault_code(
            code="E-47",
            description="Photo eye obstruction detected",
            causes=["Dirty sensor", "Misalignment", "Product buildup"],
            actions=["Clean sensor lens", "Check alignment", "Clear obstruction"]
        )
        assert "E-47" in formatted
        assert "Photo eye" in formatted
        assert "Dirty sensor" in formatted
        assert "Clean sensor lens" in formatted

    def test_format_procedure_steps(self, demo_persona):
        """Test procedure formatting"""
        formatter = ResponseFormatter(demo_persona)
        formatted = formatter.format_procedure_steps(
            procedure_name="Motor Bearing Replacement",
            steps=[
                "Lock out equipment",
                "Remove motor cover",
                "Extract old bearing",
                "Install new bearing",
                "Replace cover and test"
            ],
            safety_notes=["Verify LOTO", "Wear safety glasses"]
        )
        assert "Motor Bearing Replacement" in formatted
        assert "⚠️" in formatted
        assert "Verify LOTO" in formatted
        assert "1. Lock out equipment" in formatted
        assert "5. Replace cover and test" in formatted

    def test_truncate_if_too_long(self, god_persona):
        """Test message truncation for long content"""
        formatter = ResponseFormatter(god_persona)
        long_content = "A" * 5000
        truncated = formatter.truncate_if_too_long(long_content, max_length=4000)
        assert len(truncated) <= 4000
        assert "[Message truncated" in truncated

    def test_should_allow_technical_god_mode(self, god_persona):
        """Test technical output detection in God mode"""
        formatter = ResponseFormatter(god_persona)
        assert formatter.should_allow_technical("Show me the JSON") is True
        assert formatter.should_allow_technical("Dump the logs") is True
        assert formatter.should_allow_technical("What's the motor status?") is False

    def test_should_allow_technical_demo_mode(self, demo_persona):
        """Test Demo mode never allows technical output"""
        formatter = ResponseFormatter(demo_persona)
        assert formatter.should_allow_technical("Show me the JSON") is False
        assert formatter.should_allow_technical("Dump the logs") is False

    def test_json_to_plain_english(self, demo_persona):
        """Test JSON to plain English conversion"""
        formatter = ResponseFormatter(demo_persona)
        data = {
            "motor_status": "running",
            "current_draw": 12.5,
            "fault_codes": ["E-47", "W-12"]
        }
        plain = formatter._json_to_plain_english(data)
        assert "Motor Status" in plain
        assert "running" in plain
        assert "Current Draw" in plain
        assert "12.5" in plain
        assert "E-47" in plain


class TestPersonaValidation:
    """Test persona data validation"""

    def test_sass_level_validation(self):
        """Test sass_level must be 1-10"""
        with pytest.raises(ValueError):
            Persona(
                mode=UserMode.GOD,
                name="Test",
                soul_content="",
                greeting="Hi",
                sass_level=11,  # Invalid
                formality=5,
                can_curse=False,
                can_challenge=False
            )

    def test_formality_validation(self):
        """Test formality must be 1-10"""
        with pytest.raises(ValueError):
            Persona(
                mode=UserMode.DEMO,
                name="Test",
                soul_content="",
                greeting="Hi",
                sass_level=5,
                formality=0,  # Invalid
                can_curse=False,
                can_challenge=False
            )

    def test_valid_persona_creation(self):
        """Test valid persona creation"""
        persona = Persona(
            mode=UserMode.DEMO,
            name="Test Persona",
            soul_content="Test content",
            greeting="Hello",
            sass_level=5,
            formality=7,
            can_curse=False,
            can_challenge=False,
            tools=["plc_read"],
            guardrails=["no_writes"]
        )
        assert persona.mode == UserMode.DEMO
        assert persona.name == "Test Persona"
        assert "plc_read" in persona.tools
        assert "no_writes" in persona.guardrails


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
