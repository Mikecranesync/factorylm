# PRD-003: FactoryLM PLC Client & Modbus Integration
## Phase 2: Micro 820 Communication, Modbus TCP, Machine State Reader

**Domain:** factorylm.com  
**GitHub:** github.com/factorylm/plc-client  
**Product:** FactoryLM PLC Client (Industrial I/O Layer)  
**Version:** 0.3.0  
**Depends On:** PRD-001 (factorylm/core)  
**Status:** PRE-BUILD - PLC Integration Phase  

---

## Executive Summary

FactoryLM PLC Client provides unified access to industrial PLCs via Modbus TCP. This phase delivers:

- Modbus TCP abstraction layer (works with any PLC)
- Micro 820 support out-of-box
- Extensible PLC interface (support for AB, Siemens, etc.)
- Register/coil reading and writing
- Error handling and retry logic
- Mock PLC for testing
- Integration with Voice HMI (PRD-002)

**This is the industrial bridge to real hardware.**

---

## Architecture Overview

```
factorylm/
├── core/                          (Infrastructure)
├── voice-hmi/                     (Voice interface)
│
├── plc-client/                    (This repo)
│   ├── src/
│   │   ├── factorylm_plc/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── plc/
│   │   │   │   ├── base.py        (Abstract PLC interface)
│   │   │   │   ├── micro820.py    (Micro 820 implementation)
│   │   │   │   ├── modbus_client.py (Generic Modbus TCP)
│   │   │   │   └── mock_plc.py    (For testing)
│   │   │   ├── modbus/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py      (Modbus TCP wrapper)
│   │   │   │   └── registers.py   (Register definitions)
│   │   │   └── models.py          (Data classes for states)
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_modbus_client.py
│   │   │   ├── test_micro820.py
│   │   │   └── test_mock_plc.py
│   │   ├── integration/
│   │   │   └── test_plc_connection.py
│   │   └── fixtures/
│   │       └── mock_plc_responses.py
│   ├── docs/
│   │   ├── MODBUS_GUIDE.md
│   │   ├── MICRO_820_SETUP.md
│   │   ├── PLC_INTERFACE.md
│   │   └── REGISTER_MAP.md
│   ├── requirements.txt
│   ├── setup.py
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
```

---

## Detailed Implementation Requirements

### 1. Abstract PLC Interface (plc/base.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class MachineState:
    """Standardized machine state from any PLC"""
    motor_speed: int          # RPM
    motor_current: int        # Amps
    temperature: float        # Celsius
    pressure: int             # PSI
    motor_running: bool
    motor_stopped: bool
    fault_alarm: bool
    timestamp: float          # Unix timestamp
    raw_registers: Dict       # Raw register values for debugging

class BasePLCClient(ABC):
    """Abstract interface for all PLC providers"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to PLC"""
        pass
    
    @abstractmethod
    def read_state(self) -> Optional[MachineState]:
        """Read current machine state"""
        pass
    
    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """Write to a holding register"""
        pass
    
    @abstractmethod
    def write_coil(self, address: int, value: bool) -> bool:
        """Write to a coil"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status"""
        pass
```

Requirements:
- [ ] Standardized MachineState dataclass
- [ ] All methods documented
- [ ] Type hints on everything
- [ ] Exception handling defined

### 2. Modbus TCP Client (modbus/client.py)

Requirements:
- [ ] Use pymodbus library
- [ ] Implement connection pooling (reuse connections)
- [ ] Support register address configuration
- [ ] Support coil address configuration
- [ ] Timeout handling (default 5 seconds)
- [ ] Retry logic (3 attempts before failing)
- [ ] Logging of all reads/writes
- [ ] Error codes translated to readable messages

```python
class ModbusTCPClient:
    def __init__(self, host: str, port: int = 502, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
    
    def read_registers(self, start_addr: int, count: int) -> List[int]:
        """Read multiple holding registers"""
        # Implement with retry logic
        pass
    
    def read_coils(self, start_addr: int, count: int) -> List[bool]:
        """Read multiple coils"""
        pass
```

### 3. Micro 820 Implementation (plc/micro820.py)

Requirements:
- [ ] Extend BasePLCClient
- [ ] Hardcoded register mapping for Micro 820:
  - Holding Reg 100: motor_speed
  - Holding Reg 101: motor_current
  - Holding Reg 102: temperature (scaled 10x)
  - Holding Reg 103: pressure
  - Coil 0: motor_running
  - Coil 1: motor_stopped
  - Coil 2: fault_alarm
- [ ] Parse temperature from raw register (divide by 10)
- [ ] Timestamp all reads
- [ ] Check connection before reads
- [ ] Log all errors to logger

```python
class Micro820PLC(BasePLCClient):
    # Register addresses (from CCW configuration)
    REG_MOTOR_SPEED = 100
    REG_MOTOR_CURRENT = 101
    REG_TEMPERATURE = 102
    REG_PRESSURE = 103
    
    COIL_MOTOR_RUNNING = 0
    COIL_MOTOR_STOPPED = 1
    COIL_FAULT_ALARM = 2
    
    def __init__(self, ip: str, port: int = 502):
        self.modbus = ModbusTCPClient(ip, port)
    
    def read_state(self) -> MachineState:
        # Read all registers and coils in one operation
        # Parse into MachineState
        pass
```

### 4. Mock PLC (plc/mock_plc.py)

Requirements:
- [ ] Implement BasePLCClient
- [ ] Simulate realistic machine behavior
- [ ] Temperature increases when motor is running
- [ ] Current changes with speed
- [ ] Pressure stays constant
- [ ] No network calls (all in-memory)
- [ ] Perfect for testing without real hardware

```python
class MockPLC(BasePLCClient):
    def __init__(self):
        self.motor_speed = 0
        self.motor_current = 0
        self.temperature = 25.0
        self.pressure = 100
        self.motor_running = False
        self.last_update = time.time()
    
    def read_state(self) -> MachineState:
        # Simulate: if motor running, temperature rises slowly
        if self.motor_running:
            elapsed = time.time() - self.last_update
            self.temperature += 0.1 * elapsed
        return MachineState(...)
```

### 5. Register Definitions (modbus/registers.py)

```python
class RegisterMap:
    """Central registry of register addresses"""
    
    # Micro 820 registers
    MICRO_820 = {
        "motor_speed": 100,
        "motor_current": 101,
        "temperature": 102,
        "pressure": 103,
    }
    
    MICRO_820_COILS = {
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
    }
    
    # Future: AB CompactLogix, Siemens S7-1200, etc.
```

### 6. Data Models (models.py)

```python
from dataclasses import dataclass
from typing import Dict
import time

@dataclass
class MachineState:
    motor_speed: int
    motor_current: int
    temperature: float
    pressure: int
    motor_running: bool
    motor_stopped: bool
    fault_alarm: bool
    timestamp: float = None
    raw_registers: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.raw_registers is None:
            self.raw_registers = {}
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return {
            "motor_speed": self.motor_speed,
            "motor_current": self.motor_current,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "motor_running": self.motor_running,
            "motor_stopped": self.motor_stopped,
            "fault_alarm": self.fault_alarm,
            "timestamp": self.timestamp,
        }
```

### 7. Configuration (config.py)

```python
PLC_TYPE = os.getenv("PLC_TYPE", "micro820")  # micro820, mock, etc.
PLC_HOST = os.getenv("PLC_HOST", "192.168.1.100")
PLC_PORT = int(os.getenv("PLC_PORT", 502))
PLC_TIMEOUT = int(os.getenv("PLC_TIMEOUT", 5))
```

### 8. Factory Function (plc/__init__.py)

```python
def create_plc_client(plc_type: str, host: str, port: int) -> BasePLCClient:
    if plc_type == "micro820":
        return Micro820PLC(host, port)
    elif plc_type == "mock":
        return MockPLC()
    else:
        raise ValueError(f"Unknown PLC type: {plc_type}")
```

### 9. Testing Strategy

#### 9.1 Unit Tests

- [ ] test_modbus_client.py
  - Mock Modbus responses
  - Test register reading
  - Test error handling

- [ ] test_micro820.py
  - Test MachineState parsing
  - Test temperature scaling
  - Test coil reading

- [ ] test_mock_plc.py
  - Test simulated behavior
  - Test temperature changes
  - No network calls

#### 9.2 Integration Tests

- [ ] test_plc_connection.py
  - Test with MockPLC (no real hardware)
  - Test full read_state flow
  - Test error recovery

### 10. Requirements & Dependencies

```
# From core
factorylm-core>=0.1.0

# Modbus
pymodbus==3.6.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0
```

---

## Ralph Loop Instructions for Claude Code

```text
You are building FactoryLM PLC Client: the industrial bridge to hardware.

HOMEWORK PHASE (Do First):
1. Study pymodbus library (examples, tutorials)
2. Review Modbus TCP protocol basics
3. Understand Micro 820 register configuration
4. Document in HOMEWORK.md

DESIGN PHASE (Plan Second):
1. Verify abstraction pattern works for multiple PLC types
2. Plan MockPLC simulator for testing
3. Plan register mapping strategy
4. Design error handling for network failures
5. Document in DESIGN.md

EXECUTION PHASE (Code Third - Using Ralph Loop):
1. Create directory structure
2. Implement BasePLCClient abstract class
3. Implement ModbusTCPClient wrapper
4. Implement Micro820PLC (real hardware)
5. Implement MockPLC (testing without hardware)
6. Create MachineState dataclass
7. Add all unit tests
8. Add integration tests
9. Test with MockPLC only (no real Micro 820 needed)
10. Document register mapping
11. When all criteria met, output success summary

CRITICAL REQUIREMENTS:
- All tests pass WITHOUT real hardware (use MockPLC)
- Register addresses configurable
- MachineState standardized and reusable
- Temperature parsing correct (divide by 10)
- Timestamp all reads
- Clear logging of all errors
- Coverage 80%+

When complete, append "FACTORYLM_PLC_COMPLETE" to end of this PRD.
```

---

## Integration with Voice HMI (PRD-002)

Voice HMI will use PLC client:

```python
from factorylm_plc import create_plc_client
from factorylm_plc.config import PLC_TYPE, PLC_HOST

plc = create_plc_client(PLC_TYPE, PLC_HOST)
machine_state = plc.read_state()

# Pass to LLM
response = llm.analyze_machine_state(question, machine_state.to_dict())
```

---

## Completion Criteria

- [ ] GitHub repo created (factorylm/plc-client)
- [ ] Complete directory structure
- [ ] BasePLCClient interface
- [ ] ModbusTCPClient wrapper
- [ ] Micro820PLC implementation
- [ ] MockPLC implementation
- [ ] MachineState dataclass
- [ ] Factory function
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] 80%+ code coverage
- [ ] All documentation
- [ ] Imports from core working
- [ ] `.env.example`
- [ ] README with examples
- [ ] Initial commit to GitHub

---

## Success Criteria (End State)

```
FACTORYLM_PLC_COMPLETE

✓ Can read Micro 820 state via Modbus TCP
✓ Can test with MockPLC (no real hardware needed)
✓ MachineState standardized for LLM integration
✓ Error handling for network failures
✓ Ready for Voice HMI integration
✓ Ready for future PLC types (AB, Siemens, etc.)

Example usage:
from factorylm_plc import create_plc_client
plc = create_plc_client("micro820", "192.168.1.100")
state = plc.read_state()
print(f"Motor speed: {state.motor_speed} RPM")
print(f"Temperature: {state.temperature}°C")
```

---

## Timeline

- **Days 1-2:** Research + Plan
- **Days 3-5:** Implement Modbus + PLC logic
- **Days 6:** Testing + Documentation
- **Day 7:** Polish + Commit

**Total: 1 week to FACTORYLM_PLC_COMPLETE**

---

**BUILD AFTER PRD-002. Feeds into Voice HMI for real hardware.**

---

# PRD-004: FactoryLM Web Dashboard & Monitoring UI
## Phase 3: Real-Time Monitoring, Historical Analytics, Admin Interface

**Domain:** factorylm.com  
**GitHub:** github.com/factorylm/web-dashboard  
**Product:** FactoryLM Dashboard (Web UI & Analytics)  
**Version:** 0.4.0  
**Depends On:** PRD-001 (core), PRD-002 (voice), PRD-003 (plc-client)  
**Status:** PRE-BUILD - Web UI Phase  

---

## Executive Summary

FactoryLM Dashboard provides a web-based monitoring and analytics interface. This phase delivers:

- Real-time machine state visualization
- Historical data logging and replay
- Chat interface for text-based questions (alternative to voice)
- Admin panel for system configuration
- API for external integrations
- WebSocket-based live updates
- Optional video integration (for future phases)

**This is the tech/supervisor view of the system.**

---

## Architecture Overview

```
factorylm/
├── core/                    (Infrastructure)
├── voice-hmi/               (Voice interface)
├── plc-client/              (PLC integration)
│
├── web-dashboard/           (This repo)
│   ├── backend/
│   │   ├── app.py           (Flask app)
│   │   ├── config.py
│   │   ├── routes/
│   │   │   ├── api.py       (REST API)
│   │   │   ├── web.py       (Web routes)
│   │   │   └── ws.py        (WebSocket)
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── plc_service.py
│   │   │   └── analytics.py
│   │   └── models/
│   │       ├── db.py        (SQLAlchemy)
│   │       └── schemas.py   (Pydantic)
│   ├── frontend/
│   │   ├── index.html
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── main.js
│   │   │   ├── websocket.js
│   │   │   └── charts.js
│   │   └── components/
│   │       ├── dashboard.html
│   │       ├── chat.html
│   │       └── admin.html
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_routes.py
│   │   └── conftest.py
│   ├── docs/
│   │   ├── API_DOCS.md
│   │   ├── DEPLOYMENT.md
│   │   └── FRONTEND_GUIDE.md
│   ├── requirements.txt
│   ├── setup.py
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
```

---

## Detailed Implementation Requirements

### 1. Flask Backend (app.py)

```python
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
db = SQLAlchemy(app)

# Register blueprints
app.register_blueprint(api_routes)
app.register_blueprint(web_routes)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
```

Requirements:
- [ ] Flask 3.0.0+
- [ ] Socket.IO for real-time updates
- [ ] SQLAlchemy for data persistence
- [ ] CORS support
- [ ] Error handling middleware

### 2. API Routes (routes/api.py)

```python
@app.route("/api/machine-state", methods=["GET"])
def get_machine_state():
    """Get current machine state"""
    state = plc_service.read_state()
    return jsonify(state.to_dict())

@app.route("/api/ask", methods=["POST"])
def ask_question():
    """Ask LLM a question about the machine"""
    data = request.json
    question = data.get("question")
    state = plc_service.read_state()
    answer = llm_service.analyze(question, state)
    return jsonify({"answer": answer})

@app.route("/api/history", methods=["GET"])
def get_history():
    """Get historical machine states"""
    limit = request.args.get("limit", 100)
    history = analytics.get_history(limit)
    return jsonify(history)
```

Requirements:
- [ ] REST API endpoints
- [ ] JSON responses
- [ ] Error handling with proper status codes
- [ ] Input validation

### 3. WebSocket Routes (routes/ws.py)

```python
@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")
    # Send current state
    state = plc_service.read_state()
    emit("state_update", state.to_dict())

@socketio.on("ask")
def handle_ask(data):
    question = data.get("question")
    state = plc_service.read_state()
    answer = llm_service.analyze(question, state)
    emit("answer", {"text": answer}, broadcast=True)

# Background task to push updates
@socketio.on_event("start_monitoring")
def start_monitoring():
    def emit_updates():
        while True:
            state = plc_service.read_state()
            socketio.emit("state_update", state.to_dict())
            time.sleep(0.5)  # 500ms updates
    
    thread = Thread(target=emit_updates, daemon=True)
    thread.start()
```

Requirements:
- [ ] Real-time state broadcasting
- [ ] Question handling
- [ ] Answer broadcasting
- [ ] Connection management

### 4. Frontend Dashboard (frontend/index.html + js/)

Requirements:
- [ ] Live gauge charts (motor speed, temperature, pressure, current)
- [ ] Real-time updates via WebSocket
- [ ] Status indicators (motor running, fault alarm)
- [ ] Chat interface for text questions
- [ ] Message history display
- [ ] Responsive design (mobile + desktop)

```html
<!-- Dashboard showing live machine state -->
<div class="dashboard">
    <div class="metric motor-speed">
        <h3>Motor Speed</h3>
        <span class="value" id="motor_speed">0</span> RPM
    </div>
    <div class="metric temperature">
        <h3>Temperature</h3>
        <span class="value" id="temperature">0</span>°C
    </div>
    <!-- ... more metrics ... -->
</div>

<!-- Chat interface -->
<div class="chat">
    <div class="messages" id="messages"></div>
    <input type="text" id="question" placeholder="Ask about the machine...">
    <button onclick="askQuestion()">Send</button>
</div>
```

### 5. Services (services/)

#### 5.1 LLM Service

```python
class LLMService:
    def analyze(self, question: str, state: MachineState) -> str:
        from factorylm import create_llm_client
        llm = create_llm_client(LLM_PROVIDER, LLM_API_KEY)
        response = llm.analyze_machine_state(question, state.to_dict())
        return response.text
```

#### 5.2 PLC Service

```python
class PLCService:
    def __init__(self):
        from factorylm_plc import create_plc_client
        self.plc = create_plc_client(PLC_TYPE, PLC_HOST)
    
    def read_state(self) -> MachineState:
        return self.plc.read_state()
```

#### 5.3 Analytics Service

```python
class AnalyticsService:
    def log_state(self, state: MachineState):
        """Log machine state to database"""
        record = StateHistory(
            motor_speed=state.motor_speed,
            temperature=state.temperature,
            timestamp=state.timestamp
        )
        db.session.add(record)
        db.session.commit()
    
    def get_history(self, limit: int = 100):
        """Get recent state history"""
        records = StateHistory.query.order_by(
            StateHistory.timestamp.desc()
        ).limit(limit).all()
        return [r.to_dict() for r in records]
```

### 6. Database Models (models/db.py)

```python
class StateHistory(db.Model):
    """Historical machine state records"""
    id = db.Column(db.Integer, primary_key=True)
    motor_speed = db.Column(db.Integer)
    motor_current = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    pressure = db.Column(db.Integer)
    motor_running = db.Column(db.Boolean)
    fault_alarm = db.Column(db.Boolean)
    timestamp = db.Column(db.Float)
    
    def to_dict(self):
        return {
            "motor_speed": self.motor_speed,
            "temperature": self.temperature,
            # ...
            "timestamp": self.timestamp,
        }

class ChatMessage(db.Model):
    """Chat history"""
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500))
    answer = db.Column(db.Text)
    timestamp = db.Column(db.Float)
```

### 7. Requirements & Dependencies

```
# Core
factorylm-core>=0.1.0
factorylm-voice>=0.2.0
factorylm-plc>=0.3.0

# Web framework
flask==3.0.0
flask-socketio==5.3.5
python-socketio==5.9.0
python-engineio==4.8.0
flask-sqlalchemy==3.1.0
python-dotenv==1.0.0

# Frontend (included in static/)
chart.js (CDN)
socket.io-client (CDN)

# Testing
pytest==7.4.3
pytest-cov==4.1.0
```

---

## Ralph Loop Instructions for Claude Code

```text
You are building FactoryLM Dashboard: the web monitoring interface.

HOMEWORK PHASE:
1. Review Flask + Socket.IO patterns
2. Study real-time dashboard examples
3. Plan frontend architecture
4. Document in HOMEWORK.md

DESIGN PHASE:
1. Plan API endpoints needed
2. Plan WebSocket messages
3. Design database schema
4. Plan frontend component structure
5. Document in DESIGN.md

EXECUTION PHASE:
1. Create directory structure
2. Implement Flask app with blueprints
3. Implement REST API endpoints
4. Implement WebSocket handlers
5. Create database models
6. Build frontend HTML/CSS/JS
7. Add API tests
8. Add integration tests
9. Create API documentation
10. When all criteria met, output success summary

CRITICAL REQUIREMENTS:
- API endpoints documented in API_DOCS.md
- Real-time updates via WebSocket (500ms)
- Chat interface for text questions
- Historical data logging
- 80%+ test coverage
- Responsive design

When complete, append "FACTORYLM_DASHBOARD_COMPLETE" to end of this PRD.
```

---

## Completion Criteria

- [ ] Flask app with Socket.IO
- [ ] REST API endpoints
- [ ] WebSocket handlers
- [ ] Database models (SQLAlchemy)
- [ ] Frontend dashboard (HTML/CSS/JS)
- [ ] Chat interface
- [ ] Real-time updates
- [ ] Historical analytics
- [ ] All tests passing (80%+ coverage)
- [ ] API documentation
- [ ] Deployment guide
- [ ] `.env.example`
- [ ] README
- [ ] Initial commit to GitHub

---

## Success Criteria (End State)

```
FACTORYLM_DASHBOARD_COMPLETE

✓ Supervisor can see live machine state in browser
✓ Can ask questions via chat interface
✓ See historical data and trends
✓ Real-time updates every 500ms
✓ Mobile-responsive design
✓ Ready for integration with ML layer (Phase 4)

Example usage:
$ python app.py
[*] Running on http://0.0.0.0:5000
[*] Open browser to http://localhost:5000
[*] See live dashboard with real-time updates
```

---

## Timeline

- **Days 1-2:** Research + Plan
- **Days 3-6:** Backend + Frontend development
- **Day 7:** Testing + Documentation
- **Day 8:** Polish + Commit

**Total: 1-2 weeks to FACTORYLM_DASHBOARD_COMPLETE**

---

**BUILD AFTER PRD-003. Provides supervisor view of system.**
