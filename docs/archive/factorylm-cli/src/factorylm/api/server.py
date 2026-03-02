"""FastAPI web dashboard — extracted from Matrix API.

Provides REST endpoints and an embedded HMI dashboard.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from factorylm.db.store import TagStore

logger = logging.getLogger(__name__)

# Lazy-import to keep `factorylm[api]` optional
_app = None
_store: TagStore | None = None


def create_app(store: TagStore | None = None) -> "FastAPI":
    """Build and return the FastAPI application."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse

    global _store
    _store = store

    @asynccontextmanager
    async def lifespan(app):
        global _store
        if _store is None:
            _store = TagStore()
        logger.info("FactoryLM API started — db=%s", _store.db_path)
        yield

    app = FastAPI(title="FactoryLM API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "db": _store.db_path if _store else "none"}

    @app.get("/api/tags")
    async def list_tags(limit: int = 50, node_id: str | None = None):
        snapshots = _store.get_snapshots_as_flat(limit)
        if node_id:
            snapshots = [s for s in snapshots if s.get("node_id") == node_id]
        return snapshots

    @app.get("/api/incidents")
    async def list_incidents(status: str | None = None, limit: int = 50):
        return _store.get_incidents(status=status, limit=limit)

    @app.get("/api/incidents/{incident_id}")
    async def get_incident(incident_id: int):
        incidents = _store.get_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                return inc
        raise HTTPException(404, "Incident not found")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _HTML_DASHBOARD

    return app


def run_server(store: TagStore, host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the API server (blocking)."""
    import uvicorn

    app = create_app(store)
    uvicorn.run(app, host=host, port=port, log_level="info")


async def run_server_async(store: TagStore, host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the API server as an async task."""
    import uvicorn

    app = create_app(store)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


_HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FactoryLM Dashboard</title>
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
  #status { font-size: 0.8rem; color: #666; margin-top: 8px; }
  @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>FactoryLM</h1>
<p style="color:#888; font-size:0.85rem;">Industrial Monitoring Dashboard</p>

<div class="grid">
  <div class="card" id="live-tags-card">
    <h2>Live Tags</h2>
    <table id="tags-table"><tr><td style="color:#666">Loading...</td></tr></table>
  </div>
  <div class="card">
    <h2>Incidents</h2>
    <div id="incidents-list"><em style="color:#666">Loading...</em></div>
  </div>
</div>
<div id="status">Connecting...</div>

<script>
async function fetchTags() {
  try {
    const res = await fetch('/api/tags?limit=1');
    const data = await res.json();
    if (!data.length) return;
    const t = data[0];
    let html = '<tr><th>Tag</th><th>Value</th></tr>';
    for (const [k,v] of Object.entries(t)) {
      if (['id','timestamp','node_id'].includes(k)) continue;
      const cls = (k.includes('fault') || k.includes('e_stop')) && v ? 'fault-val' : 'tag-val';
      html += '<tr><td>'+k+'</td><td class="'+cls+'">'+v+'</td></tr>';
    }
    document.getElementById('tags-table').innerHTML = html;
    const card = document.getElementById('live-tags-card');
    card.className = (t.fault_alarm || t.e_stop) ? 'card fault' : 'card ok';
  } catch(e) {}
}
async function fetchIncidents() {
  try {
    const res = await fetch('/api/incidents?limit=10');
    const data = await res.json();
    if (!data.length) { document.getElementById('incidents-list').innerHTML = '<em style="color:#666">No incidents</em>'; return; }
    let html = '<table><tr><th>#</th><th>Error</th><th>Status</th></tr>';
    for (const inc of data) {
      const badge = inc.status === 'analyzed' ? '<span class="badge badge-analyzed">analyzed</span>' : '<span class="badge badge-open">open</span>';
      html += '<tr><td>'+inc.id+'</td><td>'+(inc.error_message||'Unknown')+'</td><td>'+badge+'</td></tr>';
    }
    html += '</table>';
    document.getElementById('incidents-list').innerHTML = html;
  } catch(e) {}
}
setInterval(() => { fetchTags(); fetchIncidents(); }, 2000);
fetchTags(); fetchIncidents();
document.getElementById('status').textContent = 'Connected — ' + window.location.origin;
</script>
</body>
</html>"""
