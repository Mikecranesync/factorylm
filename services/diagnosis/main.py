#!/usr/bin/env python3
"""
FactoryLM Diagnosis Service
Bridges Telegram/Jarvis -> PLC Laptop -> Micro 820 -> LLM -> Response

Run with: uvicorn diagnosis_service:app --host 0.0.0.0 --port 8200
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('factorylm')

# Configuration
PLC_LAPTOP_URL = os.getenv('PLC_LAPTOP_URL', 'http://100.72.2.99:8765')
TRAVEL_LAPTOP_URL = os.getenv('TRAVEL_LAPTOP_URL', 'http://100.83.251.23:8765')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile')

app = FastAPI(
    title='FactoryLM Diagnosis Service',
    description='AI-powered factory diagnostics via natural language',
    version='1.0.0'
)

class DiagnosisRequest(BaseModel):
    question: str
    include_system_info: bool = True

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

def get_plc_state() -> dict:
    """Read PLC state from the PLC laptop via Jarvis Node API."""
    try:
        # Get system info first
        r = requests.get(f'{PLC_LAPTOP_URL}/system-info', timeout=10)
        system_info = r.json()

        # Try to read actual PLC data if available
        # This calls the factorylm-plc-client on the PLC laptop
        plc_command = """python -c "
try:
    import sys
    sys.path.insert(0, 'C:/Users/hharp/OneDrive/Desktop/FactoryLM/plc-client-factoryio')
    from factorylm_plc import create_plc_client
    plc = create_plc_client('factoryio_micro820')
    state = plc.read_state()
    print(state.to_llm_context())
except Exception as e:
    print(f'PLC Read Error: {e}')
" """

        r = requests.post(f'{PLC_LAPTOP_URL}/shell', json={
            'command': plc_command,
            'timeout': 30
        }, timeout=35)

        shell_result = r.json()
        plc_output = shell_result.get('stdout', '')

        return {
            'system': system_info,
            'plc_state': plc_output if plc_output else 'No PLC data available',
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f'Failed to get PLC state: {e}')
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def ask_llm(question: str, plc_context: str) -> str:
    """Send question + PLC context to LLM for diagnosis."""
    if not GROQ_API_KEY:
        return f'[LLM not configured - showing raw PLC data]\n\n{plc_context}'

    prompt = f'''You are an expert industrial maintenance AI assistant for FactoryLM.
You help factory technicians diagnose equipment issues quickly and accurately.

Current PLC/Machine State:
{plc_context}

Technician Question: {question}

Provide a concise, actionable diagnosis. If there is an alarm or fault:
1. Explain the likely cause
2. Recommend immediate action
3. Suggest preventive measures

Keep your response under 200 words. Be direct and practical.'''

    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 500,
                'temperature': 0.3
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f'LLM API error: {response.status_code} - {response.text}')
            return f'LLM Error: {response.status_code}. Raw PLC data:\n{plc_context}'
    except Exception as e:
        logger.error(f'LLM request failed: {e}')
        return f'LLM unavailable. Raw PLC data:\n{plc_context}'

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
    start_time = datetime.utcnow()

    # Get PLC state
    plc_data = get_plc_state()

    # Format context for LLM
    if 'error' in plc_data:
        plc_context = f'ERROR: Could not read PLC - {plc_data["error"]}'
    else:
        plc_context = plc_data.get('plc_state', 'No PLC state available')
        if request.include_system_info and 'system' in plc_data:
            sys_info = plc_data['system']
            plc_context = f'''System: {sys_info.get('hostname', 'Unknown')}
CPU: {sys_info.get('cpu_percent', '?')}%
Memory: {sys_info.get('memory_used_gb', '?')}/{sys_info.get('memory_total_gb', '?')} GB

PLC State:
{plc_context}'''

    # Get diagnosis from LLM
    diagnosis = ask_llm(request.question, plc_context)

    end_time = datetime.utcnow()
    latency = int((end_time - start_time).total_seconds() * 1000)

    return DiagnosisResponse(
        question=request.question,
        diagnosis=diagnosis,
        plc_data=plc_data,
        timestamp=end_time.isoformat(),
        latency_ms=latency
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8200)
