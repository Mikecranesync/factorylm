# FactoryLM Integration for Clawdbot

**Priority: HIGH - Demo on Feb 10th**
**Created: 2026-02-02**

## Mission

Route factory-related questions to the FactoryLM Diagnosis Service running on localhost:8200.

## Detection Keywords

When a user message contains ANY of these keywords, route to FactoryLM:
- factory, plc, motor, conveyor, production, machine
- alarm, fault, error, status, diagnostic
- micro 820, allen-bradley, modbus
- temperature, pressure, sensor, actuator

## How to Call

```bash
curl -X POST http://localhost:8200/diagnose \
  -H 'Content-Type: application/json' \
  -d '{"question": "USER_MESSAGE_HERE"}'
```

## Response Format

The service returns JSON:
```json
{
  "question": "original question",
  "diagnosis": "AI-generated diagnosis to send back to user",
  "latency_ms": 1500
}
```

Send the 'diagnosis' field back to the user.

## Example Flow

1. User: "What's the status of my motor?"
2. Clawdbot detects: "motor" keyword
3. Clawdbot calls: POST localhost:8200/diagnose with {"question": "What's the status of my motor?"}
4. Service returns: {"diagnosis": "The motor is running normally at 1750 RPM..."}
5. Clawdbot replies: "The motor is running normally at 1750 RPM..."

## Test Command

```bash
curl -s -X POST http://localhost:8200/diagnose -H 'Content-Type: application/json' -d '{"question": "test"}' | jq .diagnosis
```

## Service Status

- URL: http://localhost:8200
- Health: http://localhost:8200/health
- Network: http://localhost:8200/network (shows laptop connectivity)
