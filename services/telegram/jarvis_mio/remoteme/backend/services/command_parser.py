"""
Command Parser Service
======================
Parse natural language commands using Claude.
"""

import json
import logging
from typing import Dict, Any, Optional
import anthropic
from langfuse import observe

from backend.config import settings

logger = logging.getLogger(__name__)

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None


COMMAND_PARSER_PROMPT = """You are a command parser for RemoteMe, an AI that controls computers remotely.

Parse the user's natural language command into a structured format.

Available intents:
- screenshot: Take a screenshot of the screen
- shell: Run a shell/terminal command
- interpret: Use Open Interpreter for complex tasks (opening apps, browsing, file operations)
- click: Click at screen coordinates
- type: Type text
- keypress: Press a key or key combination

Available nodes:
- plc-laptop: PLC development laptop
- travel-laptop: Travel/presentation laptop

Output JSON only, no explanation:
{
    "intent": "screenshot|shell|interpret|click|type|keypress",
    "node": "plc-laptop|travel-laptop",
    "args": {
        // For shell: {"command": "the command"}
        // For interpret: {"instruction": "natural language instruction"}
        // For click: {"x": 100, "y": 200}
        // For type: {"text": "text to type"}
        // For keypress: {"key": "ctrl+s"}
        // For screenshot: {}
    },
    "confidence": 0.0-1.0
}

If you can't parse the command, return:
{"intent": "unknown", "confidence": 0.0, "reason": "explanation"}

Examples:
- "take a screenshot" → {"intent": "screenshot", "node": "plc-laptop", "args": {}, "confidence": 1.0}
- "run dir on plc laptop" → {"intent": "shell", "node": "plc-laptop", "args": {"command": "dir"}, "confidence": 0.95}
- "open chrome and go to google" → {"intent": "interpret", "node": "plc-laptop", "args": {"instruction": "open chrome and go to google.com"}, "confidence": 0.9}
- "click at 500, 300" → {"intent": "click", "node": "plc-laptop", "args": {"x": 500, "y": 300}, "confidence": 0.95}
"""


@observe(name="parse_command")
async def parse_command(text: str) -> Dict[str, Any]:
    """
    Parse natural language command into structured format.
    
    Args:
        text: User's natural language command
        
    Returns:
        Parsed command with intent, node, args, and confidence
    """
    
    # Quick pattern matching for common commands (save API calls)
    text_lower = text.lower().strip()
    
    # Screenshot
    if text_lower in ["screenshot", "screen", "ss", "snap"]:
        return {
            "intent": "screenshot",
            "node": "plc-laptop",
            "args": {},
            "confidence": 1.0
        }
    
    # Shell commands with explicit prefix
    if text_lower.startswith("run ") or text_lower.startswith("shell ") or text_lower.startswith("cmd "):
        command = text[4:].strip() if text_lower.startswith("run ") else text[6:].strip()
        return {
            "intent": "shell",
            "node": "plc-laptop",
            "args": {"command": command},
            "confidence": 0.95
        }
    
    # If no Anthropic key, return unknown
    if not client:
        logger.warning("No Anthropic API key, using fallback parsing")
        return {
            "intent": "interpret",  # Default to interpret for natural language
            "node": "plc-laptop",
            "args": {"instruction": text},
            "confidence": 0.5
        }
    
    # Use Claude for complex parsing
    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Fast and cheap
            max_tokens=500,
            system=COMMAND_PARSER_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        
        # Parse JSON response
        result_text = response.content[0].text.strip()
        
        # Extract JSON if wrapped in code blocks
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        result = json.loads(result_text)
        logger.info(f"Parsed '{text}' → {result}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response: {e}")
        return {
            "intent": "interpret",
            "node": "plc-laptop", 
            "args": {"instruction": text},
            "confidence": 0.3
        }
    except Exception as e:
        logger.error(f"Claude parsing error: {e}")
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "reason": str(e)
        }
