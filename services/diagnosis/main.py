#!/usr/bin/env python3
"""
FactoryLM Diagnosis Service
Bridges Telegram/Jarvis -> PLC Laptop -> Micro 820 -> LLM -> Response

Run with: uvicorn main:app --host 0.0.0.0 --port 8200
"""
import os
import logging
import time
from datetime import datetime
from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('factorylm.diagnosis')

# Configuration
PLC_MODBUS_URL = os.getenv('PLC_MODBUS_URL', 'http://100.72.2.99:8001')
PLC_LAPTOP_URL = os.getenv('PLC_LAPTOP_URL', 'http://100.72.2.99:8765')
TRAVEL_LAPTOP_URL = os.getenv('TRAVEL_LAPTOP_URL', 'http://100.83.251.23:8765')
LLM_ROUTER_URL = os.getenv('LLM_ROUTER_URL', 'http://localhost:8100')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile')

app = FastAPI(
    title='FactoryLM Diagnosis Service',
    description='AI-powered factory diagnostics via natural language',
    version='1.0.0'
)

class DiagnosisRequest(BaseModel):
    question: str

class DiagnosisResponse(BaseModel):
    question: str
    diagnosis: str
    plc_data: Optional[dict] = None
    timestamp: str
    latency_ms: int

def check_laptop_health(url: str, name: str) -> dict:
    """Check if a laptop's Jarvis Node is responding."""
    try:
        r = requests.get(f'{url}/health', timeout=5)
        return {'status': 'online', 'name': name, 'data': r.json()}
    except Exception as e:
        return {'status': 'offline', 'name': name, 'error': str(e)}

def format_plc_io_for_llm(io_data: dict) -> str:
    """Convert structured PLC I/O JSON into human-readable LLM context."""
    lines = []

    coils = io_data.get('coils', {})
    inputs = io_data.get('inputs', {})
    outputs = io_data.get('outputs', {})
    registers = io_data.get('registers', {})

    # Program variables
    conveyor = coils.get('Conveyor', False)
    emitter = coils.get('Emitter', False)
    sensor_start = coils.get('SensorStart', False)
    sensor_end = coils.get('SensorEnd', False)
    run_cmd = coils.get('RunCommand', False)
    lines.append(f"Conveyor Motor: {'RUNNING' if conveyor else 'STOPPED'}")
    lines.append(f"Item Emitter: {'ACTIVE' if emitter else 'OFF'}")
    lines.append(f"Entry Sensor: {'TRIGGERED' if sensor_start else 'clear'}")
    lines.append(f"Exit Sensor: {'TRIGGERED' if sensor_end else 'clear'}")
    lines.append(f"Remote Run Command: {'ON' if run_cmd else 'OFF'}")

    # Physical inputs — derive human-readable states
    estop_no = inputs.get('DI_01', False)
    estop_nc = inputs.get('DI_02', True)
    estop_pressed = estop_no and not estop_nc
    lines.append(f"E-Stop: {'PRESSED — MACHINE HALTED' if estop_pressed else 'Released (normal)'}")

    sw_center = inputs.get('DI_00', False)
    sw_right = inputs.get('DI_03', False)
    if sw_right:
        sw_pos = 'RIGHT'
    elif sw_center:
        sw_pos = 'CENTER'
    else:
        sw_pos = 'LEFT'
    lines.append(f"Selector Switch: {sw_pos}")

    pushbutton = inputs.get('DI_04', False)
    if pushbutton:
        lines.append("Pushbutton: PRESSED")

    # Physical outputs
    lines.append(f"Switch Indicator LED: {'ON' if outputs.get('DO_00', False) else 'OFF'}")
    lines.append(f"E-Stop Indicator LED: {'ON' if outputs.get('DO_01', False) else 'OFF'}")

    # Registers
    item_count = registers.get('ItemCount', 0)
    lines.append(f"Items Counted: {item_count}")

    # VFD registers
    hz = registers.get('ConveyorHz', 0)
    current_a = registers.get('MotorCurrentX10', 0) / 10.0
    temp_c = registers.get('MotorTempX10', 0) / 10.0
    vfd_status = registers.get('VFDStatus', 0)
    error_code = registers.get('ErrorCode', 0)
    vfd_label = {0: 'Idle', 1: 'Running', 2: 'FAULT'}.get(vfd_status, f'Unknown({vfd_status})')
    lines.append(f"VFD Frequency: {hz} Hz")
    lines.append(f"Motor Current: {current_a:.1f} A")
    lines.append(f"Motor Temperature: {temp_c:.1f} °C")
    lines.append(f"VFD Status: {vfd_label}")
    if error_code:
        error_labels = {1: 'Overload', 2: 'Overheat', 3: 'Sensor Failure', 4: 'Jam', 7: 'E-Stop'}
        lines.append(f"ERROR CODE {error_code}: {error_labels.get(error_code, 'Unknown')}")

    lines.append(f"Timestamp: {io_data.get('timestamp', 'unknown')}")
    return '\n'.join(lines)


def get_plc_state() -> dict:
    """Read PLC state from the plc-modbus API on the PLC laptop."""
    t0 = time.monotonic()
    try:
        # Check connection status first
        status_r = requests.get(f'{PLC_MODBUS_URL}/api/plc/status', timeout=5)
        status = status_r.json()

        if not status.get('connected', False):
            logger.warning("PLC not connected (status: %s)", status)
            return {
                'error': 'PLC not connected. Run POST /api/plc/connect on the PLC laptop first.',
                'plc_status': status,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Read all I/O via the proper API
        io_r = requests.get(f'{PLC_MODBUS_URL}/api/plc/io', timeout=10)
        io_data = io_r.json()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info("PLC read OK in %dms", elapsed_ms)

        return {
            'plc_io': io_data,
            'plc_state': format_plc_io_for_llm(io_data),
            'timestamp': io_data.get('timestamp', datetime.utcnow().isoformat()),
        }
    except requests.ConnectionError:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error("PLC laptop unreachable at %s (%dms)", PLC_MODBUS_URL, elapsed_ms)
        return {
            'error': f'PLC laptop unreachable at {PLC_MODBUS_URL}',
            'timestamp': datetime.utcnow().isoformat(),
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error("PLC read failed: %s (%dms)", e, elapsed_ms)
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
        }

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are an expert industrial maintenance AI assistant for FactoryLM. "
    "You help factory technicians diagnose equipment issues quickly and accurately. "
    "When there is an alarm or fault: 1) Explain the likely cause, "
    "2) Recommend immediate action, 3) Suggest preventive measures. "
    "Keep your response under 200 words. Be direct and practical."
)


def _build_diagnosis_prompt(question: str, plc_context: str) -> str:
    return f"Current PLC/Machine State:\n{plc_context}\n\nTechnician Question: {question}"


def _ask_llm_via_router(prompt: str) -> str | None:
    """Try the llm-router service first (budget tracking + multi-provider)."""
    try:
        r = requests.post(
            f'{LLM_ROUTER_URL}/v1/chat/completions',
            json={
                'model': 'auto',
                'task_type': 'fast',
                'messages': [
                    {'role': 'system', 'content': DIAGNOSIS_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                'max_tokens': 500,
                'temperature': 0.3,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            logger.info("LLM response via router (provider=%s)", data.get('x_provider', '?'))
            return data['choices'][0]['message']['content']
        logger.warning("LLM router returned %d, falling back to direct Groq", r.status_code)
        return None
    except Exception as e:
        logger.warning("LLM router unreachable (%s), falling back to direct Groq", e)
        return None


def _ask_llm_direct_groq(prompt: str) -> str | None:
    """Direct Groq API call as fallback."""
    if not GROQ_API_KEY:
        return None
    r = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': GROQ_MODEL,
            'messages': [
                {'role': 'system', 'content': DIAGNOSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': 500,
            'temperature': 0.3,
        },
        timeout=30,
    )
    if r.status_code == 200:
        logger.info("LLM response via direct Groq")
        return r.json()['choices'][0]['message']['content']
    logger.error("Groq API error: %d - %s", r.status_code, r.text)
    return None


def ask_llm(question: str, plc_context: str) -> str:
    """Send question + PLC context to LLM for diagnosis.

    Tries llm-router first (budget + circuit breaker + multi-provider),
    then falls back to direct Groq, then returns raw PLC data.
    """
    t0 = time.monotonic()
    prompt = _build_diagnosis_prompt(question, plc_context)

    # Try router first, then direct Groq
    result = _ask_llm_via_router(prompt) or _ask_llm_direct_groq(prompt)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if result:
        logger.info("LLM diagnosis completed in %dms", elapsed_ms)
        return result

    logger.warning("All LLM providers failed (%dms), returning raw PLC data", elapsed_ms)
    return f'[LLM unavailable — showing raw PLC data]\n\n{plc_context}'

@app.get('/')
async def root():
    return {
        'service': 'FactoryLM Diagnosis Service',
        'version': '1.0.0',
        'endpoints': {
            '/health': 'Service health check',
            '/network': 'Check all network nodes',
            '/diagnose': 'POST - Ask a question about the factory'
        }
    }

@app.get('/health')
async def health():
    return {
        'status': 'healthy',
        'service': 'factorylm-diagnosis',
        'timestamp': datetime.utcnow().isoformat(),
        'llm_configured': bool(GROQ_API_KEY)
    }

@app.get('/network')
async def network_status():
    """Check status of all network nodes."""
    return {
        'plc_laptop': check_laptop_health(PLC_LAPTOP_URL, 'PLC Laptop'),
        'travel_laptop': check_laptop_health(TRAVEL_LAPTOP_URL, 'Travel Laptop'),
        'timestamp': datetime.utcnow().isoformat()
    }

@app.post('/diagnose', response_model=DiagnosisResponse)
async def diagnose(request: DiagnosisRequest):
    """
    Answer a question about factory/PLC state.

    This is the main endpoint for FactoryLM diagnostics.
    """
    t0 = time.monotonic()
    logger.info("DIAGNOSE request: %s", request.question[:120])

    # Get PLC state via plc-modbus API
    plc_data = get_plc_state()

    # Build LLM context
    if 'error' in plc_data:
        plc_context = f'ERROR: Could not read PLC — {plc_data["error"]}'
    else:
        plc_context = plc_data.get('plc_state', 'No PLC state available')

    # Get diagnosis from LLM (router -> Groq fallback -> raw data)
    diagnosis = ask_llm(request.question, plc_context)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info("DIAGNOSE complete: %dms", elapsed_ms)

    return DiagnosisResponse(
        question=request.question,
        diagnosis=diagnosis,
        plc_data=plc_data,
        timestamp=datetime.utcnow().isoformat(),
        latency_ms=elapsed_ms,
    )

# ---------------------------------------------------------------------------
# Simulation Dashboard — /sim
# ---------------------------------------------------------------------------

SIM_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FactoryLM — Simulation Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0a0e17;color:#e0e0e0;padding:16px}
h1{font-size:1.3rem;color:#00e5ff;margin-bottom:12px;display:flex;align-items:center;gap:8px}
h1 .dot{width:10px;height:10px;border-radius:50%;background:#555;display:inline-block}
h1 .dot.on{background:#00e676;box-shadow:0 0 6px #00e676}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:#141a2a;border:1px solid #1e2a3a;border-radius:8px;padding:14px}
.card h2{font-size:.85rem;color:#90a4ae;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:.82rem}
td{padding:3px 6px;border-bottom:1px solid #1a2030}
td:first-child{color:#78909c;width:45%}
.on{color:#00e676;font-weight:600} .off{color:#546e7a}
.alert{color:#ff5252;font-weight:700}
.val{color:#00e5ff;font-family:monospace}
.btn{border:none;border-radius:4px;padding:7px 14px;font-size:.8rem;cursor:pointer;font-weight:600;margin:3px}
.btn-go{background:#00e676;color:#0a0e17} .btn-stop{background:#ff5252;color:#fff}
.btn-warn{background:#ff9100;color:#0a0e17} .btn-fault{background:#7c4dff;color:#fff}
.btn-clear{background:#263238;color:#90a4ae;border:1px solid #37474f}
.btn:hover{filter:brightness(1.15)}
#diagnosis-box{background:#0d1117;border:1px solid #1e2a3a;border-radius:6px;padding:10px;
  min-height:80px;font-size:.82rem;white-space:pre-wrap;line-height:1.5;color:#b0bec5;margin-top:8px}
#q{width:100%;padding:8px;border:1px solid #1e2a3a;border-radius:4px;background:#0d1117;
  color:#e0e0e0;font-size:.85rem;margin-bottom:6px}
.flow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:.75rem;margin-top:10px}
.flow .node{background:#1a237e;padding:4px 10px;border-radius:4px;color:#7c4dff;font-weight:600}
.flow .arrow{color:#37474f}
.latency{font-size:.7rem;color:#546e7a;margin-top:4px}
.gauge{height:14px;background:#1a2030;border-radius:7px;overflow:hidden;margin:4px 0}
.gauge-fill{height:100%;border-radius:7px;transition:width .5s}
</style></head><body>

<h1><span class="dot" id="plc-dot"></span> FactoryLM Simulation Dashboard</h1>
<div class="flow">
  <span class="node">Mock PLC</span><span class="arrow">→</span>
  <span class="node">plc-modbus :PLC_PORT</span><span class="arrow">→</span>
  <span class="node">diagnosis :DIAG_PORT</span><span class="arrow">→</span>
  <span class="node">LLM Router</span><span class="arrow">→</span>
  <span class="node">Response</span>
</div>

<div class="grid" style="margin-top:12px">

<!-- PLC I/O Panel -->
<div class="card">
  <h2>PLC I/O — Micro 820 (simulated)</h2>
  <table id="io-table"><tr><td colspan="2" class="off">Loading…</td></tr></table>
  <div class="latency" id="plc-latency"></div>
</div>

<!-- Controls -->
<div class="card">
  <h2>Controls</h2>
  <div style="margin-bottom:10px">
    <button class="btn btn-go" onclick="plcWrite(4,true)">▶ Start Conveyor</button>
    <button class="btn btn-stop" onclick="plcWrite(4,false)">■ Stop</button>
  </div>
  <div style="margin-bottom:10px">
    <button class="btn btn-warn" onclick="injectFault('estop')">⚠ E-Stop</button>
    <button class="btn btn-clear" onclick="injectFault('clear');plcWrite(4,true)">Release E-Stop</button>
  </div>
  <hr style="border-color:#1a2030;margin:8px 0">
  <h2 style="margin-top:6px">Inject Fault</h2>
  <button class="btn btn-fault" onclick="injectFault('overload')">Overload</button>
  <button class="btn btn-fault" onclick="injectFault('overheat')">Overheat</button>
  <button class="btn btn-fault" onclick="injectFault('jam')">Jam</button>
  <button class="btn btn-fault" onclick="injectFault('sensor')">Sensor Fail</button>
  <button class="btn btn-clear" onclick="injectFault('clear')">Clear Faults</button>

  <hr style="border-color:#1a2030;margin:8px 0">
  <h2 style="margin-top:6px">VFD</h2>
  <div style="font-size:.8rem;color:#78909c">Current</div>
  <div class="gauge"><div class="gauge-fill" id="current-gauge" style="width:0%;background:#00e676"></div></div>
  <div style="font-size:.8rem;color:#78909c">Temperature</div>
  <div class="gauge"><div class="gauge-fill" id="temp-gauge" style="width:0%;background:#00e5ff"></div></div>
</div>

<!-- Diagnosis Panel -->
<div class="card">
  <h2>AI Diagnosis</h2>
  <input id="q" placeholder="Ask: Why did the conveyor stop?" onkeydown="if(event.key==='Enter')diagnose()">
  <button class="btn btn-go" onclick="diagnose()">Diagnose</button>
  <button class="btn btn-clear" onclick="diagnose('What is the current machine status?')">Quick Check</button>
  <div id="diagnosis-box">Ask a question or click Quick Check…</div>
  <div class="latency" id="diag-latency"></div>
</div>
</div>

<script>
const PLC_URL = window.location.protocol + '//' + window.location.hostname + ':' + (PLC_PORT_PLACEHOLDER);
const DIAG_URL = '';  // same origin

// Update flow diagram with actual ports
document.querySelector('.flow').innerHTML = document.querySelector('.flow').innerHTML
  .replace(':PLC_PORT', ':' + PLC_PORT_PLACEHOLDER)
  .replace(':DIAG_PORT', ':' + DIAG_PORT_PLACEHOLDER);

async function plcWrite(addr, val) {
  try {
    await fetch(PLC_URL + '/api/plc/write-coil', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({address: addr, value: val})
    });
  } catch(e) { console.warn('PLC write failed:', e); }
}

async function injectFault(type) {
  try {
    await fetch(DIAG_URL + '/fault-inject', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({fault_type: type})
    });
  } catch(e) { console.warn('Fault inject failed:', e); }
}

async function diagnose(quickQ) {
  const box = document.getElementById('diagnosis-box');
  const q = quickQ || document.getElementById('q').value;
  if (!q) { box.textContent = 'Type a question first.'; return; }
  box.textContent = 'Thinking…';
  const t0 = performance.now();
  try {
    const r = await fetch(DIAG_URL + '/diagnose', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({question: q})
    });
    const data = await r.json();
    const ms = Math.round(performance.now() - t0);
    box.textContent = data.diagnosis || JSON.stringify(data, null, 2);
    document.getElementById('diag-latency').textContent =
      `${ms}ms total (server: ${data.latency_ms}ms)`;
  } catch(e) {
    box.textContent = 'Error: ' + e.message;
  }
}

// Poll PLC I/O
async function pollIO() {
  const dot = document.getElementById('plc-dot');
  try {
    const t0 = performance.now();
    const r = await fetch(PLC_URL + '/api/plc/io');
    const data = await r.json();
    const ms = Math.round(performance.now() - t0);
    dot.classList.add('on');
    document.getElementById('plc-latency').textContent = `PLC read: ${ms}ms`;
    renderIO(data);
  } catch(e) {
    dot.classList.remove('on');
    document.getElementById('plc-latency').textContent = 'PLC offline';
  }
}

function renderIO(data) {
  const c = data.coils || {};
  const inp = data.inputs || {};
  const out = data.outputs || {};
  const reg = data.registers || {};

  const bool = (v) => v ? '<span class="on">ON</span>' : '<span class="off">OFF</span>';
  const rows = [
    ['Conveyor', bool(c.Conveyor)],
    ['Emitter', bool(c.Emitter)],
    ['Entry Sensor', bool(c.SensorStart)],
    ['Exit Sensor', bool(c.SensorEnd)],
    ['Run Command', bool(c.RunCommand)],
    ['───────', '───────'],
    ['E-Stop NO', bool(inp.DI_01)],
    ['E-Stop NC', bool(inp.DI_02)],
    ['Switch Center', bool(inp.DI_00)],
    ['Switch Right', bool(inp.DI_03)],
    ['Pushbutton', bool(inp.DI_04)],
    ['───────', '───────'],
    ['Switch LED', bool(out.DO_00)],
    ['E-Stop LED', bool(out.DO_01)],
    ['───────', '───────'],
    ['Items Counted', `<span class="val">${reg.ItemCount || 0}</span>`],
    ['Conveyor Hz', `<span class="val">${reg.ConveyorHz || 0}</span>`],
    ['Current (A)', `<span class="val">${((reg.MotorCurrentX10 || 0) / 10).toFixed(1)}</span>`],
    ['Temp (°C)', `<span class="val">${((reg.MotorTempX10 || 0) / 10).toFixed(1)}</span>`],
    ['VFD Status', `<span class="val">${['Idle','Running','FAULT'][reg.VFDStatus || 0]}</span>`],
    ['Error Code', reg.ErrorCode > 0
      ? `<span class="alert">${reg.ErrorCode}</span>`
      : '<span class="off">0</span>'],
  ];

  document.getElementById('io-table').innerHTML =
    rows.map(([k,v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');

  // Update gauges
  const maxCurrent = 10.0;  // 10A full scale
  const currentA = (reg.MotorCurrentX10 || 0) / 10;
  const currentPct = Math.min(100, (currentA / maxCurrent) * 100);
  const cGauge = document.getElementById('current-gauge');
  cGauge.style.width = currentPct + '%';
  cGauge.style.background = currentA > 8 ? '#ff5252' : currentA > 6 ? '#ff9100' : '#00e676';

  const maxTemp = 80.0;
  const tempC = (reg.MotorTempX10 || 0) / 10;
  const tempPct = Math.min(100, ((tempC - 20) / (maxTemp - 20)) * 100);
  const tGauge = document.getElementById('temp-gauge');
  tGauge.style.width = Math.max(0, tempPct) + '%';
  tGauge.style.background = tempC > 70 ? '#ff5252' : tempC > 50 ? '#ff9100' : '#00e5ff';
}

setInterval(pollIO, 2000);
pollIO();
</script></body></html>"""


@app.get('/sim', response_class=HTMLResponse)
async def sim_dashboard():
    """Simulation dashboard — visualizes full PLC → Diagnosis → LLM data flow."""
    html = SIM_DASHBOARD_HTML.replace(
        'PLC_PORT_PLACEHOLDER', PLC_MODBUS_URL.split(':')[-1]
    ).replace(
        'DIAG_PORT_PLACEHOLDER', '8200'
    )
    return HTMLResponse(content=html)


@app.post('/fault-inject')
async def fault_inject(payload: dict):
    """Proxy fault injection to plc-modbus mock API."""
    fault_type = payload.get('fault_type', 'clear')
    try:
        r = requests.post(
            f'{PLC_MODBUS_URL}/api/plc/mock/fault',
            json={'fault_type': fault_type},
            timeout=5,
        )
        return r.json()
    except Exception as e:
        return {'error': str(e), 'fault_type': fault_type}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8200)
