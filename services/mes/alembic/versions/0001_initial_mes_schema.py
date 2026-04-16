"""Initial MES Core schema — 7 tables + seed data.

Revision ID: 0001
Revises: (none — initial)
Create Date: 2026-04-15

Tables created:
  lines             — production lines (Conveyor-1, Sorting-1 seeded)
  products          — SKUs with ideal cycle times
  work_orders       — production job lifecycle
  schedules         — shift-based scheduling
  downtime_reasons  — reason code lookup (14 codes seeded)
  machine_states    — state transition time-series
  oee_snapshots     — 60s OEE computed snapshots

Reference: docs/PRD-MES-CORE.md (Walker Reynolds 8-Week MES Bootcamp, Session 1)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE work_order_status AS ENUM (
            'PENDING', 'ACTIVE', 'PAUSED', 'COMPLETE', 'CANCELLED'
        )
    """)
    op.execute("""
        CREATE TYPE machine_state_enum AS ENUM (
            'RUNNING', 'DOWN', 'CHANGEOVER', 'IDLE', 'OFFLINE'
        )
    """)
    op.execute("""
        CREATE TYPE downtime_category AS ENUM (
            'PLANNED', 'UNPLANNED', 'EXTERNAL'
        )
    """)
    op.execute("""
        CREATE TYPE entered_by_enum AS ENUM (
            'PLC', 'OPERATOR', 'MIRA_AI'
        )
    """)
    op.execute("""
        CREATE TYPE shift_enum AS ENUM (
            'DAY', 'NIGHT', 'WEEKEND'
        )
    """)

    # ── lines ─────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE lines (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT UNIQUE NOT NULL,
            isa95_path  TEXT NOT NULL,
            plc_host    TEXT NOT NULL,
            plc_port    INTEGER NOT NULL DEFAULT 502,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── products ──────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE products (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku             TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            ideal_cycle_sec FLOAT NOT NULL,
            description     TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── work_orders ───────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE work_orders (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            order_number     TEXT UNIQUE NOT NULL,
            product_id       UUID NOT NULL REFERENCES products(id),
            line_id          UUID NOT NULL REFERENCES lines(id),
            target_qty       INTEGER NOT NULL,
            good_qty         INTEGER NOT NULL DEFAULT 0,
            status           work_order_status NOT NULL DEFAULT 'PENDING',
            scheduled_start  TIMESTAMPTZ,
            actual_start     TIMESTAMPTZ,
            actual_end       TIMESTAMPTZ,
            notes            TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_work_orders_line_id ON work_orders(line_id)")
    op.execute("CREATE INDEX idx_work_orders_status  ON work_orders(status)")

    # ── schedules ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE schedules (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_order_id  UUID NOT NULL REFERENCES work_orders(id),
            line_id        UUID NOT NULL REFERENCES lines(id),
            shift          shift_enum NOT NULL,
            planned_start  TIMESTAMPTZ NOT NULL,
            planned_end    TIMESTAMPTZ NOT NULL,
            planned_qty    INTEGER NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── downtime_reasons ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE downtime_reasons (
            code        TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            category    downtime_category NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── machine_states ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE machine_states (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_id     UUID NOT NULL REFERENCES lines(id),
            state       machine_state_enum NOT NULL,
            started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at    TIMESTAMPTZ,
            reason_code TEXT REFERENCES downtime_reasons(code),
            entered_by  entered_by_enum NOT NULL DEFAULT 'PLC',
            notes       TEXT
        )
    """)
    op.execute("CREATE INDEX idx_machine_states_line_id    ON machine_states(line_id)")
    op.execute("CREATE INDEX idx_machine_states_started_at ON machine_states(started_at)")

    # ── oee_snapshots ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE oee_snapshots (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_id          UUID NOT NULL REFERENCES lines(id),
            work_order_id    UUID REFERENCES work_orders(id),
            ts               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            run_time_sec     INTEGER NOT NULL DEFAULT 0,
            planned_time_sec INTEGER NOT NULL DEFAULT 0,
            total_count      INTEGER NOT NULL DEFAULT 0,
            good_count       INTEGER NOT NULL DEFAULT 0,
            ideal_cycle_sec  FLOAT NOT NULL DEFAULT 1.0,
            availability     FLOAT NOT NULL DEFAULT 0.0,
            performance      FLOAT NOT NULL DEFAULT 0.0,
            quality          FLOAT NOT NULL DEFAULT 0.0,
            oee              FLOAT NOT NULL DEFAULT 0.0,
            teep             FLOAT
        )
    """)
    op.execute("CREATE INDEX idx_oee_snapshots_line_id ON oee_snapshots(line_id)")
    op.execute("CREATE INDEX idx_oee_snapshots_ts      ON oee_snapshots(ts)")

    # ── Seed: downtime_reasons ────────────────────────────────────────────────
    # 14 standard codes. Add new codes via INSERT — do not remove existing ones.
    op.execute("""
        INSERT INTO downtime_reasons (code, description, category) VALUES
          ('MAINT_PM',           'Planned preventive maintenance',          'PLANNED'),
          ('MAINT_BREAKDOWN',    'Unplanned equipment breakdown',           'UNPLANNED'),
          ('CHANGEOVER_PRODUCT', 'Product changeover',                      'PLANNED'),
          ('CHANGEOVER_TOOLING', 'Tooling change',                          'PLANNED'),
          ('STARVED_MATERIAL',   'Starved — no material upstream',          'UNPLANNED'),
          ('BLOCKED_DOWNSTREAM', 'Blocked — downstream full or stopped',    'UNPLANNED'),
          ('QUALITY_HOLD',       'Quality hold — inspection required',      'PLANNED'),
          ('E_STOP',             'Emergency stop activated',                'UNPLANNED'),
          ('OVERLOAD',           'Motor overload fault',                    'UNPLANNED'),
          ('OVERHEAT',           'Thermal fault — motor or drive overheat', 'UNPLANNED'),
          ('SENSOR_FAIL',        'Sensor failure or miscommunication',      'UNPLANNED'),
          ('COMMS_FAIL',         'PLC communications failure',              'UNPLANNED'),
          ('JAM',                'Conveyor or mechanism jam',               'UNPLANNED'),
          ('UNKNOWN',            'Reason not yet categorized',              'UNPLANNED')
    """)

    # ── Seed: lines ───────────────────────────────────────────────────────────
    # Two lines matching the FactoryLM cluster at 192.168.1.100
    op.execute("""
        INSERT INTO lines (name, isa95_path, plc_host, plc_port, description) VALUES
          ('Conveyor-1', 'lakewales/floor/conveyor-1', '192.168.1.100', 502,
           'Conveyor of Destiny — From A to B scene (Micro820 + Factory IO)'),
          ('Sorting-1',  'lakewales/floor/sorting-1',  '192.168.1.100', 502,
           'Sorting by Height scene — Factory IO')
    """)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS oee_snapshots")
    op.execute("DROP TABLE IF EXISTS machine_states")
    op.execute("DROP TABLE IF EXISTS schedules")
    op.execute("DROP TABLE IF EXISTS work_orders")
    op.execute("DROP TABLE IF EXISTS downtime_reasons")
    op.execute("DROP TABLE IF EXISTS products")
    op.execute("DROP TABLE IF EXISTS lines")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS shift_enum")
    op.execute("DROP TYPE IF EXISTS entered_by_enum")
    op.execute("DROP TYPE IF EXISTS downtime_category")
    op.execute("DROP TYPE IF EXISTS machine_state_enum")
    op.execute("DROP TYPE IF EXISTS work_order_status")
