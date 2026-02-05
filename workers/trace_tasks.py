"""
Trace Tasks - Self-Monitoring for Trust Verification
=====================================================
Every action Jarvis takes gets logged here.
Mike can verify any claim against these logs.
"""

import os
import json
import hashlib
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from typing import Dict, Optional, List

from celery_app import app
from observability import traced, track_llm_call, track_api_call
from workers.base_worker import with_celery_tracing

# Trace storage
TRACE_DIR = Path("/opt/factorylm-sync/traces")
TRACE_DIR.mkdir(parents=True, exist_ok=True)

KNOWLEDGE_DIR = Path("/opt/factorylm-sync/automatons-output")
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def get_today_trace_file() -> Path:
    """Get today's trace file."""
    return TRACE_DIR / f"{datetime.utcnow().strftime('%Y-%m-%d')}-traces.jsonl"


def append_trace(trace: Dict):
    """Append trace to today's file."""
    trace_file = get_today_trace_file()
    with open(trace_file, 'a') as f:
        f.write(json.dumps(trace) + '\n')


@app.task(name='trace.log_action')
@with_celery_tracing("log_action")
@traced(name="log_action", layer="execution")
def log_action(
    action_type: str,
    intent: str,
    details: Dict,
    session_id: str = None
) -> Dict:
    """
    Log any action before/after execution.
    
    action_type: command, file_write, file_read, api_call, decision, claim
    intent: Why am I doing this?
    details: What exactly am I doing?
    """
    trace = {
        "trace_id": str(uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action_type": action_type,
        "intent": intent,
        "details": details,
        "session_id": session_id or "unknown",
    }
    
    append_trace(trace)
    
    return trace


@app.task(name='trace.log_result')
@with_celery_tracing("log_result")
@traced(name="log_result", layer="execution")
def log_result(
    trace_id: str,
    success: bool,
    result: Dict,
    duration_ms: int = None,
    error: str = None
) -> Dict:
    """Log the result of an action."""
    trace = {
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "result",
        "success": success,
        "result": result,
        "duration_ms": duration_ms,
        "error": error,
    }
    
    append_trace(trace)
    
    return trace


@app.task(name='trace.log_knowledge')
@with_celery_tracing("log_knowledge")
@traced(name="log_knowledge", layer="execution")
def log_knowledge(
    title: str,
    content: str,
    source: str,
    tags: List[str] = None,
    vendor: str = None,
    product: str = None
) -> Dict:
    """
    Log a knowledge atom with full provenance.
    """
    atom = {
        "atom_id": str(uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "knowledge_atom",
        "title": title,
        "content": content,
        "source": source,
        "tags": tags or [],
        "vendor": vendor,
        "product": product,
    }
    
    # Append to traces
    append_trace(atom)
    
    # Also save to knowledge file
    knowledge_file = KNOWLEDGE_DIR / f"knowledge-{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
    with open(knowledge_file, 'a') as f:
        f.write(json.dumps(atom) + '\n')
    
    return atom


@app.task(name='trace.log_claim')
@with_celery_tracing("log_claim")
@traced(name="log_claim", layer="execution")
def log_claim(
    claim: str,
    evidence_type: str,
    evidence_path: str = None,
    evidence_content: str = None
) -> Dict:
    """
    Log a claim I'm making with evidence.
    
    evidence_type: file, command_output, api_response, database_record
    """
    claim_record = {
        "claim_id": str(uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "claim",
        "claim": claim,
        "evidence_type": evidence_type,
        "evidence_path": evidence_path,
        "evidence_hash": hashlib.sha256(
            (evidence_content or "").encode()
        ).hexdigest() if evidence_content else None,
    }
    
    append_trace(claim_record)
    
    return claim_record


@app.task(name='trace.verify_claim')
@with_celery_tracing("verify_claim")
@traced(name="verify_claim", layer="execution")
def verify_claim(claim_id: str) -> Dict:
    """
    Verify a claim against evidence.
    """
    # Find the claim in traces
    today_file = get_today_trace_file()
    claim_record = None
    
    if today_file.exists():
        with open(today_file, 'r') as f:
            for line in f:
                trace = json.loads(line)
                if trace.get("claim_id") == claim_id:
                    claim_record = trace
                    break
    
    if not claim_record:
        return {"verified": False, "error": "Claim not found"}
    
    # Verify based on evidence type
    evidence_type = claim_record.get("evidence_type")
    evidence_path = claim_record.get("evidence_path")
    
    if evidence_type == "file":
        if evidence_path and Path(evidence_path).exists():
            return {
                "verified": True,
                "claim_id": claim_id,
                "claim": claim_record.get("claim"),
                "evidence": f"File exists: {evidence_path}",
                "verified_at": datetime.utcnow().isoformat() + "Z",
            }
        else:
            return {
                "verified": False,
                "claim_id": claim_id,
                "claim": claim_record.get("claim"),
                "error": f"File not found: {evidence_path}",
            }
    
    # Default: can't verify
    return {"verified": None, "error": "Cannot verify this evidence type automatically"}


@app.task(name='trace.get_trust_score')
@with_celery_tracing("get_trust_score")
@traced(name="get_trust_score", layer="execution")
def get_trust_score(hours: int = 24) -> Dict:
    """
    Calculate trust score for the last N hours.
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    claims = []
    verified = 0
    failed = 0
    
    # Read recent trace files
    for trace_file in TRACE_DIR.glob("*.jsonl"):
        with open(trace_file, 'r') as f:
            for line in f:
                try:
                    trace = json.loads(line)
                    if trace.get("type") == "claim":
                        ts = datetime.fromisoformat(trace["timestamp"].rstrip("Z"))
                        if ts >= cutoff:
                            claims.append(trace)
                except:
                    continue
    
    # Verify each claim
    for claim in claims:
        result = verify_claim(claim.get("claim_id"))
        if result.get("verified") == True:
            verified += 1
        elif result.get("verified") == False:
            failed += 1
    
    total = len(claims)
    score = (verified / total * 100) if total > 0 else 100  # No claims = full trust
    
    return {
        "period_hours": hours,
        "total_claims": total,
        "verified": verified,
        "failed": failed,
        "unverifiable": total - verified - failed,
        "trust_score": round(score, 1),
        "calculated_at": datetime.utcnow().isoformat() + "Z",
    }


@app.task(name='trace.get_recent')
@with_celery_tracing("get_recent_traces")
@traced(name="get_recent_traces", layer="execution")
def get_recent_traces(hours: int = 1, action_types: List[str] = None) -> Dict:
    """
    Get recent traces for verification.
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    traces = []
    
    for trace_file in TRACE_DIR.glob("*.jsonl"):
        with open(trace_file, 'r') as f:
            for line in f:
                try:
                    trace = json.loads(line)
                    ts = datetime.fromisoformat(trace["timestamp"].rstrip("Z"))
                    if ts >= cutoff:
                        if action_types is None or trace.get("action_type") in action_types:
                            traces.append(trace)
                except:
                    continue
    
    return {
        "period_hours": hours,
        "count": len(traces),
        "traces": traces,
    }


@app.task(name='trace.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health() -> Dict:
    """Health check for trace system."""
    today_file = get_today_trace_file()
    trace_count = 0
    
    if today_file.exists():
        with open(today_file, 'r') as f:
            trace_count = sum(1 for _ in f)
    
    return {
        "status": "ok",
        "trace_dir": str(TRACE_DIR),
        "today_file": str(today_file),
        "today_traces": trace_count,
        "syncs_to": "All devices via Syncthing",
    }
