"""Week 1 acceptance tests — DB schema verification.

Acceptance Criteria (from PRD-MES-CORE.md Section 10):
  AC#1  alembic upgrade head runs without error (verified by schema existing)
  AC#2  All 7 tables present in mes_core schema
  AC#3  downtime_reasons has >= 14 seed records
  AC#4  lines table has >= 2 seed records (Conveyor-1, Sorting-1)
  AC#5  All enum types exist
  AC#6  All expected indexes exist
"""

import pytest
from sqlalchemy import inspect, text


EXPECTED_TABLES = {
    "lines",
    "products",
    "work_orders",
    "schedules",
    "downtime_reasons",
    "machine_states",
    "oee_snapshots",
}

EXPECTED_ENUMS = {
    "work_order_status",
    "machine_state_enum",
    "downtime_category",
    "entered_by_enum",
    "shift_enum",
}

EXPECTED_INDEXES = [
    ("work_orders",    "idx_work_orders_line_id"),
    ("work_orders",    "idx_work_orders_status"),
    ("machine_states", "idx_machine_states_line_id"),
    ("machine_states", "idx_machine_states_started_at"),
    ("oee_snapshots",  "idx_oee_snapshots_line_id"),
    ("oee_snapshots",  "idx_oee_snapshots_ts"),
]

SEED_DOWNTIME_CODES = {
    "MAINT_PM", "MAINT_BREAKDOWN", "CHANGEOVER_PRODUCT", "CHANGEOVER_TOOLING",
    "STARVED_MATERIAL", "BLOCKED_DOWNSTREAM", "QUALITY_HOLD", "E_STOP",
    "OVERLOAD", "OVERHEAT", "SENSOR_FAIL", "COMMS_FAIL", "JAM", "UNKNOWN",
}

SEED_LINES = {"Conveyor-1", "Sorting-1"}


class TestTables:
    def test_all_seven_tables_exist(self, db_engine):
        """AC#2 — all 7 MES tables present."""
        inspector = inspect(db_engine)
        actual = set(inspector.get_table_names())
        missing = EXPECTED_TABLES - actual
        assert not missing, f"Missing tables: {missing}"

    def test_lines_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("lines")}
        assert {"id", "name", "isa95_path", "plc_host", "plc_port", "created_at"} <= cols

    def test_work_orders_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("work_orders")}
        assert {
            "id", "order_number", "product_id", "line_id",
            "target_qty", "good_qty", "status", "created_at",
        } <= cols

    def test_oee_snapshots_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("oee_snapshots")}
        assert {
            "id", "line_id", "work_order_id", "ts",
            "availability", "performance", "quality", "oee", "teep",
        } <= cols

    def test_machine_states_columns(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("machine_states")}
        assert {"id", "line_id", "state", "started_at", "reason_code", "entered_by"} <= cols


class TestSeedData:
    def test_downtime_reasons_count(self, db_session):
        """AC#3 — at least 14 seed records in downtime_reasons."""
        result = db_session.execute(text("SELECT COUNT(*) FROM downtime_reasons")).scalar()
        assert result >= 14, f"Expected >= 14 downtime_reasons, got {result}"

    def test_downtime_reasons_codes(self, db_session):
        """All 14 standard codes present."""
        rows = db_session.execute(text("SELECT code FROM downtime_reasons")).fetchall()
        actual_codes = {r[0] for r in rows}
        missing = SEED_DOWNTIME_CODES - actual_codes
        assert not missing, f"Missing downtime_reason codes: {missing}"

    def test_lines_seeded(self, db_session):
        """AC#4 — Conveyor-1 and Sorting-1 present."""
        rows = db_session.execute(text("SELECT name FROM lines")).fetchall()
        actual_names = {r[0] for r in rows}
        missing = SEED_LINES - actual_names
        assert not missing, f"Missing seeded lines: {missing}"

    def test_lines_isa95_paths(self, db_session):
        rows = db_session.execute(
            text("SELECT name, isa95_path, plc_host FROM lines")
        ).fetchall()
        by_name = {r[0]: r for r in rows}
        assert "Conveyor-1" in by_name
        assert by_name["Conveyor-1"][1] == "lakewales/floor/conveyor-1"
        assert by_name["Conveyor-1"][2] == "192.168.1.100"


class TestEnums:
    def test_enum_types_exist(self, db_session):
        """AC#5 — all 5 PostgreSQL enum types created."""
        result = db_session.execute(
            text("SELECT typname FROM pg_type WHERE typcategory = 'E'")
        ).fetchall()
        actual_enums = {r[0] for r in result}
        missing = EXPECTED_ENUMS - actual_enums
        assert not missing, f"Missing enum types: {missing}"


class TestIndexes:
    def test_indexes_exist(self, db_engine):
        """AC#6 — all 6 performance indexes present."""
        inspector = inspect(db_engine)
        for table_name, index_name in EXPECTED_INDEXES:
            indexes = {i["name"] for i in inspector.get_indexes(table_name)}
            assert index_name in indexes, (
                f"Missing index {index_name} on {table_name}"
            )
