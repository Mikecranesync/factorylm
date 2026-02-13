"""Matrix API — tag ingestion, incidents, and cosmos insights."""

import datetime
import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("MATRIX_DB_PATH", "matrix.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tag_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node_id TEXT NOT NULL,
            motor_running INTEGER,
            motor_speed INTEGER,
            motor_current REAL,
            temperature REAL,
            pressure INTEGER,
            conveyor_running INTEGER,
            conveyor_speed INTEGER,
            sensor_1 INTEGER,
            sensor_2 INTEGER,
            fault_alarm INTEGER,
            e_stop INTEGER,
            error_code INTEGER,
            error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node_id TEXT NOT NULL,
            error_code INTEGER,
            error_message TEXT,
            status TEXT DEFAULT 'open',
            trigger_tag_id INTEGER,
            tags_json TEXT
        );
        CREATE TABLE IF NOT EXISTS cosmos_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            summary TEXT,
            root_cause TEXT,
            confidence REAL,
            reasoning TEXT,
            suggested_checks_json TEXT,
            video_url TEXT,
            cosmos_model TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
    """)
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Matrix API started — db=%s", DB_PATH)
    yield


app = FastAPI(title="FactoryLM Matrix API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---

class TagPayload(BaseModel):
    timestamp: str
    node_id: str = "unknown"
    motor_running: bool = False
    motor_speed: int = 0
    motor_current: float = 0.0
    temperature: float = 0.0
    pressure: int = 0
    conveyor_running: bool = False
    conveyor_speed: int = 0
    sensor_1: bool = False
    sensor_2: bool = False
    fault_alarm: bool = False
    e_stop: bool = False
    error_code: int = 0
    error_message: str = ""


class InsightPayload(BaseModel):
    incident_id: int
    summary: str = ""
    root_cause: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    suggested_checks: list[str] = []
    video_url: str = ""
    cosmos_model: str = "nvidia/cosmos-reason2"


# --- Health ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "db": DB_PATH}


# --- Tags ---

@app.post("/api/tags")
async def ingest_tag(tag: TagPayload):
    """Ingest a single tag snapshot. Auto-creates incidents on fault."""
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO tag_snapshots
               (timestamp, node_id, motor_running, motor_speed, motor_current,
                temperature, pressure, conveyor_running, conveyor_speed,
                sensor_1, sensor_2, fault_alarm, e_stop, error_code, error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tag.timestamp, tag.node_id,
             int(tag.motor_running), tag.motor_speed, tag.motor_current,
             tag.temperature, tag.pressure,
             int(tag.conveyor_running), tag.conveyor_speed,
             int(tag.sensor_1), int(tag.sensor_2),
             int(tag.fault_alarm), int(tag.e_stop),
             tag.error_code, tag.error_message),
        )
        tag_id = cur.lastrowid

        # Auto-create incident on new fault
        incident_id = None
        if tag.fault_alarm and tag.error_code > 0:
            # Check if there's already an open incident for this node+error
            existing = conn.execute(
                "SELECT id FROM incidents WHERE node_id=? AND error_code=? AND status='open'",
                (tag.node_id, tag.error_code),
            ).fetchone()
            if not existing:
                cur2 = conn.execute(
                    """INSERT INTO incidents (timestamp, node_id, error_code, error_message, status, trigger_tag_id, tags_json)
                       VALUES (?,?,?,?,?,?,?)""",
                    (tag.timestamp, tag.node_id, tag.error_code, tag.error_message,
                     "open", tag_id, json.dumps(tag.model_dump())),
                )
                incident_id = cur2.lastrowid
                logger.info("Incident #%d created: %s on %s", incident_id, tag.error_message, tag.node_id)

        conn.commit()
        return {"tag_id": tag_id, "incident_id": incident_id}
    finally:
        conn.close()


@app.get("/api/tags")
async def list_tags(limit: int = 50, node_id: str | None = None):
    """List recent tag snapshots."""
    conn = get_db()
    try:
        if node_id:
            rows = conn.execute(
                "SELECT * FROM tag_snapshots WHERE node_id=? ORDER BY id DESC LIMIT ?",
                (node_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tag_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Incidents ---

@app.get("/api/incidents")
async def list_incidents(status: str | None = None, limit: int = 50):
    """List incidents, optionally filtered by status."""
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            # Check if cosmos insight exists
            insight = conn.execute(
                "SELECT id FROM cosmos_insights WHERE incident_id=?", (d["id"],)
            ).fetchone()
            d["has_insight"] = insight is not None
            results.append(d)
        return results
    finally:
        conn.close()


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: int):
    """Get a single incident with its cosmos insight (if any)."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Incident not found")
        d = dict(row)

        insight = conn.execute(
            "SELECT * FROM cosmos_insights WHERE incident_id=? ORDER BY id DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        d["cosmos_insight"] = dict(insight) if insight else None
        return d
    finally:
        conn.close()


# --- Cosmos Insights ---

@app.post("/api/insights")
async def create_insight(payload: InsightPayload):
    """Store a cosmos insight for an incident."""
    conn = get_db()
    try:
        # Verify incident exists
        inc = conn.execute("SELECT id FROM incidents WHERE id=?", (payload.incident_id,)).fetchone()
        if not inc:
            raise HTTPException(404, "Incident not found")

        cur = conn.execute(
            """INSERT INTO cosmos_insights
               (incident_id, timestamp, summary, root_cause, confidence,
                reasoning, suggested_checks_json, video_url, cosmos_model)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (payload.incident_id,
             datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
             payload.summary, payload.root_cause, payload.confidence,
             payload.reasoning, json.dumps(payload.suggested_checks),
             payload.video_url, payload.cosmos_model),
        )
        insight_id = cur.lastrowid

        # Mark incident as analyzed
        conn.execute(
            "UPDATE incidents SET status='analyzed' WHERE id=?",
            (payload.incident_id,),
        )
        conn.commit()
        return {"insight_id": insight_id}
    finally:
        conn.close()


@app.get("/api/insights")
async def list_insights(limit: int = 20):
    """List recent cosmos insights."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM cosmos_insights ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Web HMI (inline HTML) ---

@app.get("/", response_class=HTMLResponse)
async def hmi_dashboard():
    """Simple web HMI dashboard — single HTML page with live data."""
    return HTML_DASHBOARD


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FactoryLM Matrix — Cosmos Cookoff</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 16px; }
  h1 { color: #76b900; margin-bottom: 8px; font-size: 1.4rem; }
  h2 { color: #aaa; font-size: 1rem; margin: 16px 0 8px; border-bottom: 1px solid #333; padding-bottom: 4px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
  .card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 12px; }
  .card.fault { border-color: #ff4444; }
  .card.ok { border-color: #76b900; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #222; }
  th { color: #888; }
  .tag-val { font-family: monospace; color: #76b900; }
  .fault-val { color: #ff4444; font-weight: bold; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
  .badge-open { background: #ff4444; color: #fff; }
  .badge-analyzed { background: #76b900; color: #000; }
  .insight-box { background: #1e2a0a; border: 1px solid #76b900; border-radius: 6px; padding: 10px; margin-top: 8px; }
  .insight-box h3 { color: #76b900; font-size: 0.9rem; margin-bottom: 6px; }
  .insight-box p { font-size: 0.85rem; margin: 4px 0; }
  .insight-box .label { color: #888; }
  .checks { list-style: none; padding: 0; }
  .checks li::before { content: "→ "; color: #76b900; }
  #status { font-size: 0.8rem; color: #666; margin-top: 8px; }
  @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>🏭 FactoryLM Matrix</h1>
<p style="color:#888; font-size:0.85rem;">NVIDIA Cosmos Cookoff 2026 — Live Dashboard</p>

<div class="grid">
  <div class="card" id="live-tags-card">
    <h2>📊 Live Tags</h2>
    <table id="tags-table">
      <tr><th>Tag</th><th>Value</th></tr>
      <tr><td>Motor</td><td class="tag-val" id="t-motor">—</td></tr>
      <tr><td>Motor Speed</td><td class="tag-val" id="t-speed">—</td></tr>
      <tr><td>Motor Current</td><td class="tag-val" id="t-current">—</td></tr>
      <tr><td>Temperature</td><td class="tag-val" id="t-temp">—</td></tr>
      <tr><td>Pressure</td><td class="tag-val" id="t-pressure">—</td></tr>
      <tr><td>Conveyor</td><td class="tag-val" id="t-conveyor">—</td></tr>
      <tr><td>Sensor 1</td><td class="tag-val" id="t-s1">—</td></tr>
      <tr><td>Sensor 2</td><td class="tag-val" id="t-s2">—</td></tr>
      <tr><td>Fault</td><td id="t-fault">—</td></tr>
      <tr><td>E-Stop</td><td id="t-estop">—</td></tr>
      <tr><td>Error</td><td id="t-error">—</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>🚨 Incidents</h2>
    <div id="incidents-list"><em style="color:#666">Loading...</em></div>
  </div>
</div>

<div id="insight-detail" style="margin-top:16px;"></div>
<div id="status">Connecting...</div>

<script>
const API = '';

async function fetchTags() {
  try {
    const res = await fetch(API + '/api/tags?limit=1');
    const data = await res.json();
    if (!data.length) return;
    const t = data[0];
    document.getElementById('t-motor').textContent = t.motor_running ? 'RUNNING' : 'STOPPED';
    document.getElementById('t-speed').textContent = t.motor_speed + '%';
    document.getElementById('t-current').textContent = t.motor_current.toFixed(2) + ' A';
    document.getElementById('t-temp').textContent = t.temperature.toFixed(1) + '°C';
    document.getElementById('t-pressure').textContent = t.pressure + ' PSI';
    document.getElementById('t-conveyor').textContent = t.conveyor_running ? t.conveyor_speed + '%' : 'STOPPED';
    document.getElementById('t-s1').textContent = t.sensor_1 ? 'PART' : 'clear';
    document.getElementById('t-s2').textContent = t.sensor_2 ? 'PART' : 'clear';

    const faultEl = document.getElementById('t-fault');
    faultEl.textContent = t.fault_alarm ? 'ACTIVE' : 'None';
    faultEl.className = t.fault_alarm ? 'fault-val' : 'tag-val';

    const estopEl = document.getElementById('t-estop');
    estopEl.textContent = t.e_stop ? 'ENGAGED' : 'Clear';
    estopEl.className = t.e_stop ? 'fault-val' : 'tag-val';

    document.getElementById('t-error').textContent = t.error_code ? t.error_message + ' (' + t.error_code + ')' : 'None';
    document.getElementById('t-error').className = t.error_code ? 'fault-val' : 'tag-val';

    const card = document.getElementById('live-tags-card');
    card.className = t.fault_alarm ? 'card fault' : 'card ok';
  } catch(e) {}
}

async function fetchIncidents() {
  try {
    const res = await fetch(API + '/api/incidents?limit=10');
    const data = await res.json();
    if (!data.length) {
      document.getElementById('incidents-list').innerHTML = '<em style="color:#666">No incidents yet</em>';
      return;
    }
    let html = '<table><tr><th>#</th><th>Error</th><th>Node</th><th>Status</th><th>Insight</th></tr>';
    for (const inc of data) {
      const badge = inc.status === 'analyzed'
        ? '<span class="badge badge-analyzed">✓ analyzed</span>'
        : '<span class="badge badge-open">open</span>';
      const insight = inc.has_insight ? '✓' : '–';
      html += '<tr style="cursor:pointer" onclick="showInsight(' + inc.id + ')">';
      html += '<td>' + inc.id + '</td>';
      html += '<td>' + (inc.error_message || 'Unknown') + '</td>';
      html += '<td>' + inc.node_id + '</td>';
      html += '<td>' + badge + '</td>';
      html += '<td>' + insight + '</td>';
      html += '</tr>';
    }
    html += '</table>';
    document.getElementById('incidents-list').innerHTML = html;
  } catch(e) {}
}

async function showInsight(incidentId) {
  try {
    const res = await fetch(API + '/api/incidents/' + incidentId);
    const inc = await res.json();
    const ci = inc.cosmos_insight;
    let html = '<div class="card">';
    html += '<h2>Incident #' + inc.id + ': ' + (inc.error_message || '') + '</h2>';
    html += '<p style="color:#888;font-size:0.8rem;">Node: ' + inc.node_id + ' | Time: ' + inc.timestamp + '</p>';

    if (ci) {
      let checks = [];
      try { checks = JSON.parse(ci.suggested_checks_json || '[]'); } catch(e) {}
      html += '<div class="insight-box">';
      html += '<h3>🧠 Cosmos Reason 2 Insight</h3>';
      html += '<p><span class="label">Summary:</span> ' + ci.summary + '</p>';
      html += '<p><span class="label">Root Cause:</span> ' + ci.root_cause + '</p>';
      html += '<p><span class="label">Confidence:</span> ' + (ci.confidence * 100).toFixed(0) + '%</p>';
      html += '<p><span class="label">Reasoning:</span> ' + ci.reasoning + '</p>';
      if (checks.length) {
        html += '<p class="label">Suggested Checks:</p><ul class="checks">';
        checks.forEach(c => html += '<li>' + c + '</li>');
        html += '</ul>';
      }
      html += '<p style="color:#555;font-size:0.75rem;margin-top:6px;">Model: ' + ci.cosmos_model + '</p>';
      html += '</div>';
    } else {
      html += '<p style="color:#888;margin-top:8px;">No Cosmos insight yet — waiting for analysis...</p>';
    }

    html += '</div>';
    document.getElementById('insight-detail').innerHTML = html;
  } catch(e) {}
}

// Poll every 2 seconds
setInterval(() => { fetchTags(); fetchIncidents(); }, 2000);
fetchTags(); fetchIncidents();
document.getElementById('status').textContent = 'Connected to Matrix API at ' + window.location.origin;
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MATRIX_PORT", "8000"))
    uvicorn.run("services.matrix.app:app", host="0.0.0.0", port=port, reload=True)
