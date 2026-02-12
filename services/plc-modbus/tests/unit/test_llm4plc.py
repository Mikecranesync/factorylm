"""
Unit tests for LLM4PLC — Structured Text code generation module.

Tests STDataType, STVariable, STProgram (generation, validation),
template generators (conveyor, motor safety, sorting station),
STCodeGenerator utilities, and create_program_from_template.

NEW for V3 — llm4plc.py has no V1/V2 counterpart.
"""

import pytest
from datetime import datetime

from factorylm_plc.llm4plc import (
    STDataType,
    STVariable,
    STProgram,
    STCodeGenerator,
    create_program_from_template,
    generate_conveyor_control,
    generate_motor_safety_program,
    generate_sorting_station_program,
)


# ---------------------------------------------------------------------------
# STDataType
# ---------------------------------------------------------------------------


class TestSTDataType:
    """Test IEC 61131-3 data type enum."""

    def test_bool_value(self):
        assert STDataType.BOOL.value == "BOOL"

    def test_int_value(self):
        assert STDataType.INT.value == "INT"

    def test_real_value(self):
        assert STDataType.REAL.value == "REAL"

    def test_all_types_defined(self):
        """All expected data types are present."""
        names = {t.name for t in STDataType}
        assert {"BOOL", "INT", "DINT", "REAL", "TIME", "STRING"} <= names


# ---------------------------------------------------------------------------
# STVariable
# ---------------------------------------------------------------------------


class TestSTVariable:
    """Test Structured Text variable declaration."""

    def test_to_st_basic(self):
        """Basic variable without initial value or comment."""
        var = STVariable(name="counter", data_type=STDataType.INT)
        st = var.to_st()
        assert "counter" in st
        assert "INT" in st
        assert st.strip().endswith(";")

    def test_to_st_with_initial_value(self):
        """Variable with initial value."""
        var = STVariable(name="limit", data_type=STDataType.INT, initial_value="100")
        st = var.to_st()
        assert ":= 100" in st

    def test_to_st_with_comment(self):
        """Variable with comment produces ST comment syntax."""
        var = STVariable(
            name="flag",
            data_type=STDataType.BOOL,
            initial_value="FALSE",
            comment="Safety interlock",
        )
        st = var.to_st()
        assert "(* Safety interlock *)" in st


# ---------------------------------------------------------------------------
# STProgram
# ---------------------------------------------------------------------------


class TestSTProgram:
    """Test ST program generation and validation."""

    def test_empty_program_structure(self):
        """Empty program contains PROGRAM / END_PROGRAM keywords."""
        prog = STProgram(name="TestProg")
        code = prog.to_st()
        assert "PROGRAM TestProg" in code
        assert "END_PROGRAM" in code

    def test_add_variable(self):
        """add_variable adds a variable that appears in generated code."""
        prog = STProgram(name="TestProg")
        prog.add_variable("speed", STDataType.INT, "0", "Motor speed")
        code = prog.to_st()
        assert "VAR" in code
        assert "END_VAR" in code
        assert "speed" in code
        assert "INT" in code

    def test_set_body(self):
        """set_body inserts logic between PROGRAM and END_PROGRAM."""
        prog = STProgram(name="TestProg")
        prog.set_body("motor_running := TRUE;")
        code = prog.to_st()
        assert "motor_running := TRUE;" in code

    def test_header_comment(self):
        """Generated code includes program name and author."""
        prog = STProgram(name="MyProg", author="UnitTest")
        code = prog.to_st()
        assert "MyProg" in code
        assert "UnitTest" in code

    def test_validate_syntax_valid_program(self):
        """A well-formed program produces no errors."""
        prog = STProgram(name="ValidProg")
        prog.set_body("""
IF motor_running THEN
    motor_speed := 50;
END_IF;
""")
        errors = prog.validate_syntax()
        assert errors == []

    def test_validate_syntax_unbalanced_if(self):
        """Unbalanced IF/END_IF detected."""
        prog = STProgram(name="BadProg")
        prog.set_body("""
IF motor_running THEN
    motor_speed := 50;
""")
        errors = prog.validate_syntax()
        assert any("IF" in e and "END_IF" in e for e in errors)

    def test_validate_syntax_unbalanced_case(self):
        """Unbalanced CASE/END_CASE detected."""
        prog = STProgram(name="BadProg")
        prog.set_body("""
CASE state OF
    0: motor_speed := 0;
""")
        errors = prog.validate_syntax()
        assert any("CASE" in e for e in errors)

    def test_validate_syntax_invalid_assignment(self):
        """Invalid ':= =' pattern detected."""
        prog = STProgram(name="BadProg")
        prog.set_body("motor_speed := = 50;")
        errors = prog.validate_syntax()
        assert any("assignment" in e.lower() for e in errors)

    def test_global_variables_defined(self):
        """GLOBAL_VARIABLES contains expected PLC variable names."""
        gv = STProgram.GLOBAL_VARIABLES
        assert "motor_speed" in gv
        assert "motor_running" in gv
        assert "conveyor_running" in gv
        assert "e_stop_active" in gv
        assert gv["motor_speed"] == STDataType.INT
        assert gv["motor_running"] == STDataType.BOOL


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------


class TestGenerateConveyorControl:
    """Test generate_conveyor_control template."""

    def test_generates_valid_program(self):
        """Generated program validates with no errors."""
        prog = generate_conveyor_control()
        assert isinstance(prog, STProgram)
        assert prog.name == "ConveyorControl"
        errors = prog.validate_syntax()
        assert errors == []

    def test_contains_estop_logic(self):
        """Conveyor control includes e-stop safety check."""
        prog = generate_conveyor_control()
        code = prog.to_st()
        assert "e_stop_active" in code

    def test_contains_sensor_logic(self):
        """Conveyor control references sensors."""
        prog = generate_conveyor_control()
        code = prog.to_st()
        assert "sensor_1_active" in code
        assert "sensor_2_active" in code


class TestGenerateMotorSafetyProgram:
    """Test generate_motor_safety_program template."""

    def test_generates_valid_program(self):
        """Generated program validates with no errors."""
        prog = generate_motor_safety_program()
        assert prog.name == "MotorSafety"
        errors = prog.validate_syntax()
        assert errors == []

    def test_contains_temperature_check(self):
        """Motor safety includes temperature monitoring."""
        prog = generate_motor_safety_program()
        code = prog.to_st()
        assert "temperature" in code.lower() or "TEMP_LIMIT" in code

    def test_contains_current_check(self):
        """Motor safety includes current monitoring."""
        prog = generate_motor_safety_program()
        code = prog.to_st()
        assert "motor_current" in code or "CURRENT_LIMIT" in code


class TestGenerateSortingStationProgram:
    """Test generate_sorting_station_program template."""

    def test_generates_valid_program(self):
        """Generated program validates with no errors."""
        prog = generate_sorting_station_program()
        assert prog.name == "SortingStation"
        errors = prog.validate_syntax()
        assert errors == []

    def test_contains_state_machine(self):
        """Sorting station uses a CASE state machine."""
        prog = generate_sorting_station_program()
        code = prog.to_st()
        assert "CASE" in code
        assert "END_CASE" in code


# ---------------------------------------------------------------------------
# STCodeGenerator
# ---------------------------------------------------------------------------


class TestSTCodeGenerator:
    """Test STCodeGenerator utility methods."""

    def test_create_empty_program(self):
        """create_empty_program returns a named STProgram."""
        prog = STCodeGenerator.create_empty_program("EmptyTest")
        assert isinstance(prog, STProgram)
        assert prog.name == "EmptyTest"

    def test_create_timer_block(self):
        """create_timer_block returns ST code with IF/END_IF."""
        code = STCodeGenerator.create_timer_block(
            timer_name="delay_timer",
            condition="start_signal",
            duration_ms=5000,
            on_complete="output := TRUE;",
        )
        assert "delay_timer" in code
        assert "start_signal" in code
        assert "5000" in code
        assert "output := TRUE;" in code
        assert "IF" in code
        assert "END_IF" in code

    def test_create_interlock(self):
        """create_interlock returns ST code for enable/disable logic."""
        code = STCodeGenerator.create_interlock(
            output="motor_running",
            enable_conditions=["NOT e_stop_active", "pressure > 50"],
            disable_conditions=["e_stop_active", "fault_alarm"],
        )
        assert "motor_running" in code
        assert "e_stop_active" in code
        assert "fault_alarm" in code

    def test_create_interlock_empty_conditions(self):
        """Interlock with empty conditions uses TRUE/FALSE defaults."""
        code = STCodeGenerator.create_interlock(
            output="lamp",
            enable_conditions=[],
            disable_conditions=[],
        )
        assert "TRUE" in code
        assert "FALSE" in code

    def test_validate_for_micro820_clean(self):
        """Clean program produces no compatibility warnings."""
        prog = STProgram(name="CleanProg")
        prog.set_body("motor_speed := 50;")
        warnings = STCodeGenerator.validate_for_micro820(prog)
        # May warn about global variable usage, but should not warn about
        # unsupported features
        unsupported = [w for w in warnings if "not supported" in w.lower()]
        assert unsupported == []

    def test_validate_for_micro820_pointer_warning(self):
        """POINTER usage triggers a compatibility warning."""
        prog = STProgram(name="BadProg")
        prog.set_body("my_ptr : POINTER TO INT;")
        warnings = STCodeGenerator.validate_for_micro820(prog)
        assert any("POINTER" in w for w in warnings)


# ---------------------------------------------------------------------------
# create_program_from_template
# ---------------------------------------------------------------------------


class TestCreateProgramFromTemplate:
    """Test template lookup function."""

    def test_conveyor_template(self):
        """'conveyor' template returns a program."""
        prog = create_program_from_template("conveyor")
        assert prog is not None
        assert prog.name == "ConveyorControl"

    def test_motor_safety_template(self):
        """'motor_safety' template returns a program."""
        prog = create_program_from_template("motor_safety")
        assert prog is not None
        assert prog.name == "MotorSafety"

    def test_sorting_station_template(self):
        """'sorting_station' template returns a program."""
        prog = create_program_from_template("sorting_station")
        assert prog is not None
        assert prog.name == "SortingStation"

    def test_unknown_template_returns_none(self):
        """Unknown template name returns None."""
        assert create_program_from_template("nonexistent") is None

    def test_case_insensitive(self):
        """Template lookup is case-insensitive."""
        prog = create_program_from_template("Conveyor")
        assert prog is not None
