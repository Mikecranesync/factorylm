# PEPPER Persona System

Multi-persona architecture for context-aware AI behavior in FactoryLM.

## Overview

The Persona system enables PEPPER to adapt its personality, capabilities, and communication style based on user mode:

- **SOUL_GOD.md**: Pepper Prime for Mike (unrestricted access, technical, direct)
- **SOUL_DEMO.md**: Pepper for customers/technicians (guardrails, simplified language, helpful)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Request                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   User Mode Detection │
            │   (GOD or DEMO)       │
            └───────────┬───────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────┐              ┌────────────────┐
│  Pepper Prime │              │     Pepper     │
│   (GOD Mode)  │              │  (DEMO Mode)   │
├───────────────┤              ├────────────────┤
│ Full Access   │              │ Read-Only      │
│ Sass: 7/10    │              │ Sass: 2/10     │
│ Technical OK  │              │ Plain English  │
│ Can Challenge │              │ Professional   │
└───────┬───────┘              └────────┬───────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Response Formatter   │
            │  (OUTPUT FORMAT LAW)  │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   User Response       │
            └───────────────────────┘
```

## Components

### 1. **models.py**
Defines data structures:
- `UserMode` enum: GOD or DEMO
- `Persona` dataclass: Configuration for each personality

### 2. **loader.py**
`PersonaLoader` class:
- Loads SOUL_*.md files
- Parses persona attributes
- Builds system prompts
- Manages persona caching

### 3. **formatter.py**
`ResponseFormatter` class:
- Enforces OUTPUT FORMAT LAW
- Strips raw JSON from responses
- Simplifies technical jargon (Demo mode)
- Formats equipment status, fault codes, procedures

### 4. **SOUL_GOD.md**
Pepper Prime personality definition:
- Name: Pepper Prime
- User: Mike Harper only
- Access: Unrestricted (filesystem, shell, PLC read, deployments)
- Voice: Direct, capable, slightly sassy (7/10)
- Can curse mildly, can challenge bad ideas
- Follows AI Engineering Operating System
- OUTPUT FORMAT LAW enforced (unless technical output requested)

### 5. **SOUL_DEMO.md**
Pepper personality definition:
- Name: Pepper
- Users: Factory technicians, maintenance crews
- Access: Diagnostic only (no writes, no system access)
- Voice: Professional, helpful, patient (2/10 sass)
- No cursing, no challenging (only clarifying)
- Strict OUTPUT FORMAT LAW enforcement
- Simplifies jargon for accessibility

## Usage

### Basic Example

```python
from personas import PersonaLoader, ResponseFormatter, UserMode

# Initialize loader
loader = PersonaLoader()

# Load persona based on user
if user_id == MIKE_ID:
    persona = loader.load_persona(UserMode.GOD)
else:
    persona = loader.load_persona(UserMode.DEMO)

# Build system prompt
system_prompt = loader.build_system_prompt(persona)

# Format responses
formatter = ResponseFormatter(persona)
formatted_response = formatter.format_response(ai_output)
```

### Greeting Messages

```python
# Get greeting for new conversation
greeting = loader.get_greeting(UserMode.DEMO)
# Returns: "Hi! I'm Pepper, your maintenance assistant. How can I help?"

greeting = loader.get_greeting(UserMode.GOD)
# Returns: "Hey boss. What do you need?"
```

### Response Formatting

```python
formatter = ResponseFormatter(demo_persona)

# Equipment status
status = formatter.format_equipment_status(
    "Motor M-3",
    {"running": True, "current": 12.5, "temperature": 65}
)

# Fault codes
fault = formatter.format_fault_code(
    code="E-47",
    description="Photo eye obstruction",
    causes=["Dirty sensor", "Misalignment"],
    actions=["Clean lens", "Check alignment"]
)

# Procedures
procedure = formatter.format_procedure_steps(
    "Sensor Maintenance",
    steps=["Lock out equipment", "Clean sensor", "Test operation"],
    safety_notes=["Verify LOTO"]
)
```

### Tool Filtering

```python
# Build prompt with only currently available tools
available_tools = ["plc_read", "vector_search", "manual_search"]
system_prompt = loader.build_system_prompt(persona, available_tools)
```

## Persona Attributes

| Attribute | God Mode | Demo Mode |
|-----------|----------|-----------|
| **Name** | Pepper Prime | Pepper |
| **Sass Level** | 7/10 | 2/10 |
| **Formality** | 3/10 | 6/10 |
| **Can Curse** | Yes (mildly) | No |
| **Can Challenge** | Yes | No |
| **Filesystem Access** | ✅ Read/Write | ❌ |
| **Shell Execute** | ✅ | ❌ |
| **PLC Read** | ✅ | ✅ |
| **PLC Write** | ❌ (architecture) | ❌ |
| **External Comms** | ✅ (with confirm) | ❌ |
| **AI Layer 3** | ✅ | ⚠️ (if enabled) |

## OUTPUT FORMAT LAW

Both personas enforce the OUTPUT FORMAT LAW from SOUL.md:

**NEVER send:**
- Raw JSON (unless God mode explicitly requests)
- Code snippets in messages
- Technical metrics without context
- Developer jargon

**ALWAYS send:**
- Plain English an 11-year-old can understand
- Simple ✅ or ❌ indicators
- One sentence summaries
- Equipment-specific references

**Exception:** God mode can request technical output with phrases like:
- "Show me the JSON"
- "Dump the logs"
- "Raw data"
- "Debug output"

## Testing

Run the test suite:

```bash
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\telegram\pepper\personas
pytest test_personas.py -v
```

Test coverage includes:
- Persona loading and caching
- Tool and guardrail configuration
- System prompt generation
- Response formatting
- JSON stripping
- Jargon simplification
- Status indicators
- Equipment/fault/procedure formatting

## Examples

Run the example script to see all features:

```bash
python example_usage.py
```

Demonstrates:
1. Loading both personas
2. Comparing tools and guardrails
3. Response formatting in each mode
4. Equipment status formatting
5. Fault code explanations
6. Maintenance procedures
7. Tool filtering

## Integration

### With Telegram Bot

```python
from personas import PersonaLoader, ResponseFormatter, UserMode

# In bot initialization
loader = PersonaLoader()

# Per-user persona selection
def get_user_mode(user_id: int) -> UserMode:
    if user_id == MIKE_TELEGRAM_ID:
        return UserMode.GOD
    else:
        return UserMode.DEMO

# In message handler
async def handle_message(update, context):
    user_id = update.effective_user.id
    mode = get_user_mode(user_id)

    persona = loader.load_persona(mode)
    formatter = ResponseFormatter(persona)

    # Build system prompt for AI
    system_prompt = loader.build_system_prompt(persona)

    # Get AI response
    ai_response = await get_ai_response(system_prompt, user_message)

    # Format response
    allow_tech = formatter.should_allow_technical(user_message)
    formatted = formatter.format_response(ai_response, allow_technical=allow_tech)

    # Send to user
    await update.message.reply_text(formatted)
```

### With LLM APIs

```python
# Build system prompt
system_prompt = loader.build_system_prompt(persona)

# Call LLM
response = anthropic.messages.create(
    model="claude-opus-4-5-20251101",
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}]
)

# Format response
formatted = formatter.format_response(response.content[0].text)
```

## File Structure

```
personas/
├── __init__.py           # Package exports
├── models.py             # Persona and UserMode definitions
├── loader.py             # PersonaLoader class
├── formatter.py          # ResponseFormatter class
├── SOUL_GOD.md          # Pepper Prime personality
├── SOUL_DEMO.md         # Pepper personality
├── test_personas.py     # Test suite
├── example_usage.py     # Usage examples
└── README.md            # This file
```

## Design Principles

1. **Separation of Concerns**: Personality definition (SOUL.md) separate from code
2. **Markdown-First**: Human-readable personality definitions
3. **Type Safety**: Dataclasses and enums for configuration
4. **Caching**: Personas loaded once and cached
5. **Extensibility**: Easy to add new personas (SOUL_*.md)
6. **Testability**: Comprehensive test coverage
7. **OUTPUT FORMAT LAW**: Enforced across all personas

## Adding New Personas

To add a new persona:

1. Create `SOUL_NEWMODE.md` following the existing format
2. Add mode to `UserMode` enum in `models.py`
3. Define tools and guardrails in `loader.py` `_parse_persona()`
4. Test with `test_personas.py`

Example:
```python
# In models.py
class UserMode(Enum):
    GOD = "god"
    DEMO = "demo"
    SUPERVISOR = "supervisor"  # New mode

# Create SOUL_SUPERVISOR.md with personality definition
```

## References

- **AI Engineering Operating System**: Defined in SOUL.md
- **FactoryLM Vision**: `C:\Users\hharp\OneDrive\Desktop\FactoryLM\README.md`
- **Project Context**: `C:\Users\hharp\OneDrive\Desktop\FactoryLM\CLAUDE.md`

---

**Built for FactoryLM** — Making factory technicians more effective through context-aware AI assistance.
