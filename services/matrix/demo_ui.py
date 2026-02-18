"""
FactoryLM Demo UI — Fault Diagnosis Dashboard
==============================================
FastAPI app with live IO display and "Why stopped?" diagnosis.

Run: uvicorn services.matrix.demo_ui:app --host 0.0.0.0 --port 8080
"""

import os
import sys
import time
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from diagnosis.conveyor_faults import detect_faults, format_diagnosis_for_technician
from diagnosis.prompts import build_diagnosis_prompt, SYSTEM_PROMPT
from cosmos.client import CosmosClient

# Configuration
MATRIX_API = os.getenv("MATRIX_API", "http://100.72.2.99:8000")
NVIDIA_API_KEY = os.getenv("NVIDIA_COSMOS_API_KEY", "")

app = FastAPI(title="FactoryLM Demo", version="1.0.0")


# ============================================================================
# Models
# ============================================================================

class DiagnoseRequest(BaseModel):
    question: str = "Why is this equipment stopped?"


class DiagnoseResponse(BaseModel):
    question: str
    answer: str
    faults_detected: list
    model: str
    latency_ms: int
    timestamp: str


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/tags")
async def get_live_tags():
    """Fetch latest tags from Matrix API."""
    try:
        resp = httpx.get(f"{MATRIX_API}/api/tags?limit=1", timeout=5)
        resp.raise_for_status()
        tags_list = resp.json()
        if tags_list:
            return tags_list[0]
        return {"error": "No tags available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/faults")
async def get_faults():
    """Detect faults from current tags."""
    tags = await get_live_tags()
    if "error" in tags:
        return tags

    faults = detect_faults(tags)
    return {
        "faults": [
            {
                "code": f.fault_code,
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "causes": f.likely_causes,
                "checks": f.suggested_checks
            }
            for f in faults
        ],
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest):
    """
    AI-powered fault diagnosis.

    Measures latency from request to LLM response.
    """
    start_time = time.time()

    # Get current tags
    tags = await get_live_tags()
    if "error" in tags:
        return DiagnoseResponse(
            question=request.question,
            answer=f"Cannot fetch PLC data: {tags['error']}",
            faults_detected=[],
            model="error",
            latency_ms=int((time.time() - start_time) * 1000),
            timestamp=datetime.now().isoformat()
        )

    # Detect faults
    faults = detect_faults(tags)

    # Build prompt
    prompt = build_diagnosis_prompt(
        question=request.question,
        tags=tags,
        faults=faults
    )

    # Call LLM
    try:
        client = CosmosClient()

        # Use analyze_incident which already handles Cosmos/Llama fallback
        result = client.analyze_incident(
            incident_id=f"DEMO-{int(time.time())}",
            node_id=tags.get("node_id", "factory-io"),
            tags=tags,
            context=f"Technician question: {request.question}"
        )

        answer = f"{result.summary}\n\nRoot Cause: {result.root_cause}\n\n"
        if result.suggested_checks:
            answer += "Suggested Checks:\n"
            for check in result.suggested_checks[:5]:
                answer += f"  - {check}\n"

        model_used = result.cosmos_model

    except Exception as e:
        # Fallback to rule-based diagnosis
        answer = "AI analysis unavailable. Rule-based diagnosis:\n\n"
        for fault in faults:
            answer += format_diagnosis_for_technician(fault) + "\n\n"
        model_used = "rule-based"

    latency_ms = int((time.time() - start_time) * 1000)

    return DiagnoseResponse(
        question=request.question,
        answer=answer,
        faults_detected=[f.fault_code for f in faults if f.severity.value != "info"],
        model=model_used,
        latency_ms=latency_ms,
        timestamp=datetime.now().isoformat()
    )


@app.get("/", response_class=HTMLResponse)
async def demo_dashboard():
    """Demo dashboard with live IO and diagnosis."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FactoryLM Demo - Fault Diagnosis</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px;
            border-bottom: 2px solid #0f3460;
        }
        .header h1 {
            font-size: 24px;
            color: #00ff88;
        }
        .header p { color: #888; margin-top: 5px; }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }
        .panel {
            background: #12121a;
            border: 1px solid #2a2a3a;
            border-radius: 12px;
            overflow: hidden;
        }
        .panel-header {
            background: #1a1a2e;
            padding: 15px 20px;
            border-bottom: 1px solid #2a2a3a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header h2 {
            font-size: 16px;
            color: #fff;
        }
        .panel-body { padding: 20px; }
        .tag-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        .tag-item {
            background: #1a1a2e;
            padding: 12px 15px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .tag-name { color: #888; font-size: 13px; }
        .tag-value { font-weight: 600; font-size: 15px; }
        .tag-value.on { color: #00ff88; }
        .tag-value.off { color: #666; }
        .tag-value.warning { color: #ffaa00; }
        .tag-value.critical { color: #ff4444; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-ok { background: #00ff8820; color: #00ff88; }
        .status-warning { background: #ffaa0020; color: #ffaa00; }
        .status-critical { background: #ff444420; color: #ff4444; }
        .status-emergency { background: #ff000040; color: #ff0000; }
        .fault-list { margin-top: 15px; }
        .fault-item {
            background: #1a1a2e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #666;
        }
        .fault-item.warning { border-color: #ffaa00; }
        .fault-item.critical { border-color: #ff4444; }
        .fault-item.emergency { border-color: #ff0000; }
        .fault-title { font-weight: 600; margin-bottom: 5px; }
        .fault-desc { color: #888; font-size: 14px; }
        .diagnosis-box {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 20px;
            margin-top: 15px;
        }
        .diagnosis-question {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .diagnosis-question input {
            flex: 1;
            background: #0a0a0f;
            border: 1px solid #2a2a3a;
            border-radius: 8px;
            padding: 12px 15px;
            color: #fff;
            font-size: 14px;
        }
        .diagnosis-question input:focus {
            outline: none;
            border-color: #00ff88;
        }
        .btn {
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            color: #000;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .btn:hover { transform: scale(1.02); }
        .btn:active { transform: scale(0.98); }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .btn-secondary {
            background: #2a2a3a;
            color: #fff;
        }
        .diagnosis-result {
            background: #0a0a0f;
            border-radius: 8px;
            padding: 20px;
            margin-top: 15px;
            white-space: pre-wrap;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 13px;
            line-height: 1.6;
            max-height: 400px;
            overflow-y: auto;
        }
        .latency-badge {
            background: #2a2a3a;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            color: #888;
        }
        .latency-badge.fast { color: #00ff88; }
        .latency-badge.slow { color: #ffaa00; }
        .refresh-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #444;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>FactoryLM Demo</h1>
        <p>Live Fault Diagnosis for Conveyor Cell</p>
    </div>

    <div class="container">
        <!-- Live IO Panel -->
        <div class="panel">
            <div class="panel-header">
                <h2>Live I/O Status</h2>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span id="lastUpdate" class="latency-badge">--</span>
                    <div class="refresh-indicator"></div>
                </div>
            </div>
            <div class="panel-body">
                <div class="tag-grid" id="tagGrid">
                    <div class="tag-item"><span class="tag-name">Loading...</span></div>
                </div>
            </div>
        </div>

        <!-- Faults Panel -->
        <div class="panel">
            <div class="panel-header">
                <h2>Detected Faults</h2>
                <span id="faultCount" class="status-badge status-ok">0 Active</span>
            </div>
            <div class="panel-body">
                <div class="fault-list" id="faultList">
                    <div class="fault-item">
                        <div class="fault-title">Scanning...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Diagnosis Panel -->
    <div style="max-width: 1400px; margin: 0 auto; padding: 0 20px 20px;">
        <div class="panel">
            <div class="panel-header">
                <h2>AI Fault Diagnosis</h2>
                <span id="diagnosisModel" class="latency-badge">--</span>
            </div>
            <div class="panel-body">
                <div class="diagnosis-box">
                    <div class="diagnosis-question">
                        <input type="text" id="questionInput" placeholder="Ask a question... (e.g., Why is this stopped?)" value="Why is this equipment stopped?">
                        <button class="btn" onclick="runDiagnosis()">Diagnose</button>
                        <button class="btn btn-secondary" onclick="quickDiagnose()">Quick Check</button>
                    </div>
                    <div id="diagnosisResult" class="diagnosis-result" style="display: none;"></div>
                    <div id="diagnosisLatency" style="margin-top: 10px; display: none;">
                        <span class="latency-badge" id="latencyValue">--</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        FactoryLM v1 Demo | Pipeline: Factory I/O -> Modbus -> Matrix -> Llama 3.1 70B -> Diagnosis
    </div>

    <script>
        const API_BASE = '';

        // Tag display configuration
        const tagConfig = {
            motor_running: { label: 'Motor', type: 'bool' },
            motor_speed: { label: 'Motor Speed', type: 'percent' },
            motor_current: { label: 'Motor Current', type: 'amps' },
            temperature: { label: 'Temperature', type: 'temp', warn: 65, crit: 80 },
            pressure: { label: 'Pressure', type: 'psi', warn: 70, crit: 60 },
            conveyor_running: { label: 'Conveyor', type: 'bool' },
            conveyor_speed: { label: 'Conveyor Speed', type: 'percent' },
            sensor_1: { label: 'Sensor 1', type: 'bool' },
            sensor_2: { label: 'Sensor 2', type: 'bool' },
            fault_alarm: { label: 'Fault Alarm', type: 'alarm' },
            e_stop: { label: 'E-Stop', type: 'estop' },
            error_code: { label: 'Error Code', type: 'int' }
        };

        function formatTagValue(key, value, config) {
            if (!config) return { text: String(value), class: '' };

            switch (config.type) {
                case 'bool':
                    return { text: value ? 'RUNNING' : 'STOPPED', class: value ? 'on' : 'off' };
                case 'percent':
                    return { text: value + '%', class: '' };
                case 'amps':
                    const amps = parseFloat(value).toFixed(2);
                    return { text: amps + ' A', class: value > 5 ? 'critical' : '' };
                case 'temp':
                    const temp = parseFloat(value).toFixed(1);
                    let tempClass = '';
                    if (value > config.crit) tempClass = 'critical';
                    else if (value > config.warn) tempClass = 'warning';
                    return { text: temp + ' C', class: tempClass };
                case 'psi':
                    let psiClass = '';
                    if (value < config.crit) psiClass = 'critical';
                    else if (value < config.warn) psiClass = 'warning';
                    return { text: value + ' PSI', class: psiClass };
                case 'alarm':
                    return { text: value ? 'ACTIVE' : 'Clear', class: value ? 'critical' : 'on' };
                case 'estop':
                    return { text: value ? 'PRESSED' : 'Clear', class: value ? 'critical' : 'on' };
                case 'int':
                    return { text: value || 'None', class: value ? 'warning' : '' };
                default:
                    return { text: String(value), class: '' };
            }
        }

        async function fetchTags() {
            try {
                const resp = await fetch(API_BASE + '/api/tags');
                const tags = await resp.json();

                if (tags.error) {
                    console.error('Tag error:', tags.error);
                    return;
                }

                const grid = document.getElementById('tagGrid');
                grid.innerHTML = '';

                for (const [key, config] of Object.entries(tagConfig)) {
                    const value = tags[key];
                    if (value === undefined) continue;

                    const formatted = formatTagValue(key, value, config);
                    const item = document.createElement('div');
                    item.className = 'tag-item';
                    item.innerHTML = `
                        <span class="tag-name">${config.label}</span>
                        <span class="tag-value ${formatted.class}">${formatted.text}</span>
                    `;
                    grid.appendChild(item);
                }

                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();

            } catch (err) {
                console.error('Failed to fetch tags:', err);
            }
        }

        async function fetchFaults() {
            try {
                const resp = await fetch(API_BASE + '/api/faults');
                const data = await resp.json();

                if (data.error) {
                    console.error('Fault error:', data.error);
                    return;
                }

                const list = document.getElementById('faultList');
                const countBadge = document.getElementById('faultCount');

                const activeFaults = data.faults.filter(f => f.severity !== 'info');

                if (activeFaults.length === 0) {
                    list.innerHTML = '<div class="fault-item"><div class="fault-title" style="color: #00ff88;">No Active Faults</div><div class="fault-desc">System operating normally</div></div>';
                    countBadge.textContent = 'OK';
                    countBadge.className = 'status-badge status-ok';
                } else {
                    list.innerHTML = '';
                    for (const fault of activeFaults) {
                        const item = document.createElement('div');
                        item.className = `fault-item ${fault.severity}`;
                        item.innerHTML = `
                            <div class="fault-title">[${fault.code}] ${fault.title}</div>
                            <div class="fault-desc">${fault.description}</div>
                        `;
                        list.appendChild(item);
                    }

                    const maxSeverity = activeFaults[0].severity;
                    countBadge.textContent = activeFaults.length + ' Active';
                    countBadge.className = 'status-badge status-' + maxSeverity;
                }

            } catch (err) {
                console.error('Failed to fetch faults:', err);
            }
        }

        async function runDiagnosis() {
            const question = document.getElementById('questionInput').value;
            const resultDiv = document.getElementById('diagnosisResult');
            const latencyDiv = document.getElementById('diagnosisLatency');
            const modelBadge = document.getElementById('diagnosisModel');

            resultDiv.style.display = 'block';
            resultDiv.textContent = 'Analyzing...';
            latencyDiv.style.display = 'none';

            try {
                const resp = await fetch(API_BASE + '/api/diagnose', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });

                const data = await resp.json();

                resultDiv.textContent = data.answer;

                latencyDiv.style.display = 'block';
                const latencyEl = document.getElementById('latencyValue');
                latencyEl.textContent = data.latency_ms + 'ms';
                latencyEl.className = 'latency-badge ' + (data.latency_ms < 5000 ? 'fast' : 'slow');

                modelBadge.textContent = data.model;

            } catch (err) {
                resultDiv.textContent = 'Error: ' + err.message;
            }
        }

        function quickDiagnose() {
            document.getElementById('questionInput').value = 'Give me a quick status check of this equipment.';
            runDiagnosis();
        }

        // Initial load
        fetchTags();
        fetchFaults();

        // Auto-refresh every 2 seconds
        setInterval(fetchTags, 2000);
        setInterval(fetchFaults, 2000);

        // Enter key triggers diagnosis
        document.getElementById('questionInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') runDiagnosis();
        });
    </script>
</body>
</html>"""


# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "factorylm-demo",
        "matrix_api": MATRIX_API,
        "nvidia_api": bool(NVIDIA_API_KEY)
    }


if __name__ == "__main__":
    import uvicorn
    print("Starting FactoryLM Demo UI on http://0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
