# PRD-002: FactoryLM Voice HMI & Voice Interface
## Phase 1: Voice-First HMI, Speech I/O, Voice Agent Loop

**Domain:** factorylm.com  
**GitHub:** github.com/factorylm/voice-hmi  
**Product:** FactoryLM Voice (Voice Interface Layer)  
**Version:** 0.2.0  
**Depends On:** PRD-001 (factorylm/core)  
**Status:** PRE-BUILD - Voice Phase  

---

## Executive Summary

FactoryLM Voice is the voice-first HMI layer that enables technicians to speak to machines in natural language. This phase delivers:

- CLI voice interface (listen → process → speak)
- Real-time speech-to-text (SpeechRecognition + optional Whisper)
- Real-time text-to-speech (pyttsx3 + optional RealtimeTTS)
- Voice agent loop (main interaction pattern)
- Web-based voice dashboard (optional Phase 1B)
- Integration with FactoryLM Core LLM abstraction

**This is the customer-facing MVP.**

---

## Architecture Overview

```
factorylm/
├── core/                          (Infrastructure from PRD-001)
│
├── voice-hmi/                     (This repo)
│   ├── src/
│   │   ├── factorylm_voice/
│   │   │   ├── __init__.py
│   │   │   ├── config.py          (Voice-specific config)
│   │   │   ├── stt.py             (Speech-to-Text interface)
│   │   │   │   ├── base.py        (Abstract STT)
│   │   │   │   ├── speech_recognition_impl.py
│   │   │   │   └── whisper_impl.py (Optional)
│   │   │   ├── tts.py             (Text-to-Speech interface)
│   │   │   │   ├── base.py        (Abstract TTS)
│   │   │   │   ├── pyttsx3_impl.py
│   │   │   │   └── realtime_tts_impl.py (Optional)
│   │   │   ├── voice_agent.py     (Main voice loop orchestrator)
│   │   │   ├── cli.py             (Command-line interface)
│   │   │   └── web/               (Optional Phase 1B)
│   │   │       ├── app.py
│   │   │       ├── routes.py
│   │   │       └── static/
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_stt.py
│   │   │   ├── test_tts.py
│   │   │   └── test_voice_agent.py
│   │   ├── integration/
│   │   │   └── test_voice_loop.py
│   │   └── conftest.py
│   ├── docs/
│   │   ├── VOICE_DESIGN.md
│   │   ├── STT_PROVIDERS.md
│   │   ├── TTS_PROVIDERS.md
│   │   └── USAGE.md
│   ├── requirements.txt
│   ├── setup.py
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
```

---

## Detailed Implementation Requirements

### 1. Speech-to-Text Abstraction Layer (stt.py)

#### 1.1 Base STT Interface (stt/base.py)

```python
from abc import ABC, abstractmethod
from typing import Optional

class STTResult:
    """Standardized STT response"""
    def __init__(self, text: str, confidence: float, provider: str):
        self.text = text
        self.confidence = confidence
        self.provider = provider

class BaseSTTClient(ABC):
    """Abstract interface for all STT providers"""
    
    @abstractmethod
    def listen_for_question(self, timeout: int = 5) -> Optional[STTResult]:
        """Listen for voice input and convert to text"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name (e.g., 'SpeechRecognition', 'Whisper')"""
        pass
```

Requirements:
- [ ] Abstract methods clearly defined
- [ ] Standardized response object
- [ ] Type hints on all methods
- [ ] Docstrings for all methods

#### 1.2 SpeechRecognition Implementation (stt/speech_recognition_impl.py)

Requirements:
- [ ] Use Google Speech Recognition (free, works offline-ish)
- [ ] Implement BaseSTTClient interface
- [ ] Handle microphone exceptions gracefully
- [ ] Support ambient noise adjustment
- [ ] Return STTResult with confidence score
- [ ] Timeout after 5 seconds of silence

#### 1.3 Whisper Implementation (stt/whisper_impl.py - Optional)

Requirements:
- [ ] Use OpenAI Whisper library
- [ ] Implement BaseSTTClient interface
- [ ] Support both local and API modes
- [ ] Fallback to local model if API fails
- [ ] Better accuracy than SpeechRecognition

#### 1.4 STT Factory (stt/__init__.py)

```python
def create_stt_client(provider: str) -> BaseSTTClient:
    if provider == "speech_recognition":
        return SpeechRecognitionClient()
    elif provider == "whisper":
        return WhisperClient()
    else:
        raise ValueError(f"Unknown STT provider: {provider}")
```

### 2. Text-to-Speech Abstraction Layer (tts.py)

#### 2.1 Base TTS Interface (tts/base.py)

```python
from abc import ABC, abstractmethod

class BaseTTSClient(ABC):
    """Abstract interface for all TTS providers"""
    
    @abstractmethod
    def speak(self, text: str, rate: int = 150) -> None:
        """Speak the given text out loud"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name"""
        pass
```

Requirements:
- [ ] Simple, clean interface
- [ ] Support speech rate adjustment
- [ ] Cross-platform (Windows, macOS, Linux)
- [ ] No blocking behavior

#### 2.2 pyttsx3 Implementation (tts/pyttsx3_impl.py)

Requirements:
- [ ] Use pyttsx3 for offline TTS
- [ ] Works on all platforms
- [ ] Configurable speech rate
- [ ] No internet required
- [ ] Fast response

#### 2.3 RealtimeTTS Implementation (tts/realtime_tts_impl.py - Optional)

Requirements:
- [ ] Streams speech while text is being generated
- [ ] Lower latency than pyttsx3
- [ ] Support multiple voices
- [ ] Better quality

#### 2.4 TTS Factory (tts/__init__.py)

```python
def create_tts_client(provider: str) -> BaseTTSClient:
    if provider == "pyttsx3":
        return PyTTSX3Client()
    elif provider == "realtime_tts":
        return RealtimeTTSClient()
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
```

### 3. Voice Agent Loop (voice_agent.py)

This is the core orchestrator that ties STT + LLM + TTS together.

```python
class VoiceAgent:
    def __init__(self, llm_provider: str, stt_provider: str, tts_provider: str):
        self.llm = create_llm_client(llm_provider, ...)
        self.stt = create_stt_client(stt_provider)
        self.tts = create_tts_client(tts_provider)
    
    def run_loop(self):
        """Main voice interaction loop"""
        while True:
            # 1. Listen for question
            stt_result = self.stt.listen_for_question()
            if not stt_result:
                self.tts.speak("Sorry, I didn't hear that. Try again.")
                continue
            
            # 2. Check for exit command
            if "exit" in stt_result.text.lower():
                self.tts.speak("Goodbye!")
                break
            
            # 3. Read current machine state (from PRD-003)
            machine_state = self.plc_client.read_state()
            
            # 4. Call LLM to analyze
            llm_response = self.llm.analyze_machine_state(
                stt_result.text, 
                machine_state
            )
            
            # 5. Speak the answer
            self.tts.speak(llm_response.text)
```

Requirements:
- [ ] Main loop handles all exceptions gracefully
- [ ] Supports text input fallback for testing (no mic needed)
- [ ] Logs all interactions for debugging
- [ ] Metrics tracking (latency, success rate)
- [ ] Clean shutdown on "exit" command

### 4. CLI Interface (cli.py)

Requirements:
- [ ] Entry point: `python -m factorylm_voice`
- [ ] Argument parser for:
  - `--stt-provider` (default: speech_recognition)
  - `--tts-provider` (default: pyttsx3)
  - `--llm-provider` (from core, default: groq)
  - `--test-mode` (use text input instead of mic)
- [ ] Clear startup message with instructions
- [ ] Error handling with helpful messages

### 5. Web Dashboard (Optional Phase 1B - web/)

Requirements:
- [ ] Flask app with routes
- [ ] `/` - Live dashboard showing:
  - Last question heard
  - Machine state (mocked or from PRD-003)
  - Last answer given
  - System status
- [ ] WebSocket for real-time updates
- [ ] Text input fallback for testing

### 6. Configuration (config.py)

```python
STT_PROVIDER = os.getenv("STT_PROVIDER", "speech_recognition")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "pyttsx3")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
```

### 7. Testing Strategy

#### 7.1 Unit Tests (tests/unit/)

- [ ] test_stt.py
  - Mock microphone input
  - Verify STTResult structure
  - Test error handling

- [ ] test_tts.py
  - Mock audio output
  - Verify speak() called correctly
  - Test rate parameter

- [ ] test_voice_agent.py
  - Mock STT/TTS/LLM
  - Verify correct flow through loop
  - Test exit command handling

#### 7.2 Integration Tests (tests/integration/)

- [ ] test_voice_loop.py
  - End-to-end with mocked STT/TTS/LLM
  - Verify real-world scenario
  - Test error recovery

### 8. Requirements & Dependencies

```
# From core
factorylm-core>=0.1.0

# Voice I/O
SpeechRecognition==3.10.0
pyaudio==0.2.13
pyttsx3==2.90

# Optional (production)
openai-whisper==20231117
realtime-tts==0.4.0

# Web dashboard (optional)
flask==3.0.0
flask-socketio==5.3.5
python-socketio==5.9.0
python-engineio==4.8.0

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0
```

---

## Ralph Loop Instructions for Claude Code

```text
You are building FactoryLM Voice: the voice-first HMI interface.

HOMEWORK PHASE (Do First):
1. Review SpeechRecognition, Whisper, pyttsx3, RealtimeTTS documentation
2. Study patterns from Whisper Real-Time GUI repo
3. Understand audio I/O on different OSs
4. Document in HOMEWORK.md

DESIGN PHASE (Plan Second):
1. Plan STT/TTS abstraction layers
2. Verify both can be tested without real hardware
3. Plan voice agent loop state machine
4. Design error recovery strategy
5. Document in DESIGN.md

EXECUTION PHASE (Code Third - Using Ralph Loop):
1. Create directory structure
2. Implement BaseSTTClient + SpeechRecognitionClient
3. Implement BaseTTSClient + PyTTSX3Client
4. Implement VoiceAgent orchestrator
5. Implement CLI interface with arg parser
6. Add unit tests for each component
7. Add integration test for full voice loop
8. Test with mock STT/TTS (no real mic/speakers needed in CI)
9. Add CLI documentation
10. When all criteria met, output success summary

CRITICAL REQUIREMENTS:
- All tests pass WITHOUT requiring real microphone/speakers
- Use TEXT_MODE for testing (sys.stdin instead of microphone)
- All components follow abstraction pattern from core
- Clear exit strategy ("exit" command)
- Graceful error handling (no crashes)
- All interactions logged
- Coverage 80%+

When complete, append "FACTORYLM_VOICE_COMPLETE" to end of this PRD.
```

---

## Integration with PRD-001 (Core)

Voice HMI imports from core:

```python
from factorylm import create_llm_client
from factorylm.config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL

# In voice_agent.py
self.llm = create_llm_client(LLM_PROVIDER, LLM_API_KEY, LLM_MODEL)
```

This keeps LLM logic centralized.

---

## Integration with PRD-003 (PLC Client)

Voice HMI will import from PLC client once available:

```python
from factorylm_plc import create_plc_client
from factorylm_plc.config import MICRO_820_IP, MICRO_820_PORT

# In voice_agent.py
self.plc_client = create_plc_client(MICRO_820_IP, MICRO_820_PORT)
machine_state = self.plc_client.read_state()
```

For now, **mock machine_state** in tests:

```python
mock_state = {
    "motor_speed": 75,
    "motor_current": 15,
    "temperature": 65.0,
    "pressure": 102,
    "motor_running": True,
    "fault_alarm": False
}
```

---

## Completion Criteria

- [ ] GitHub repo created (factorylm/voice-hmi)
- [ ] Directory structure complete
- [ ] BaseSTTClient + SpeechRecognitionClient implemented
- [ ] BaseTTSClient + PyTTSX3Client implemented
- [ ] VoiceAgent orchestrator implemented
- [ ] CLI interface working
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Text mode for testing without hardware
- [ ] 80%+ code coverage
- [ ] All documentation written
- [ ] Imports from factorylm.core working
- [ ] `.env.example` with all vars
- [ ] README with usage instructions
- [ ] Initial commit to GitHub

---

## Success Criteria (End State)

```
FACTORYLM_VOICE_COMPLETE

✓ Technician can speak question to CLI
✓ System hears and understands (with any LLM provider)
✓ System speaks answer back
✓ Works without microphone in test mode (uses stdin)
✓ Graceful error handling
✓ Can be extended with web dashboard (Phase 1B)
✓ Ready for PLC integration (Phase 2)

Example usage:
$ python -m factorylm_voice --test-mode
[*] FactoryLM Voice HMI ready
[*] Test mode: using stdin instead of microphone
[*] Enter your question (or "exit" to quit):
> Why is motor current high?
[*] Analyzing...
[*] Analyzing machine state... (mocked)
[*] Speaking: "Motor is running at normal speed. Check bearing..."
[Speaker plays audio]
```

---

## Timeline

- **Days 1-2:** Research + Plan (HOMEWORK + DESIGN)
- **Days 3-5:** Implement Voice Loop + CLI
- **Days 6:** Testing + Documentation
- **Day 7:** Polish + Commit

**Total: 1 week to FACTORYLM_VOICE_COMPLETE**

---

## Phase 1B Enhancement (Optional - After Core MVP)

- Add web dashboard (Flask)
- Add real-time transcription display
- Add voice indicator (listening, thinking, speaking)
- Add session history
- Add metrics (latency, success rate)

---

**START AFTER PRD-001 COMPLETE. This is the customer-facing MVP.**
