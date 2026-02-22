"""
Command Parser Service
======================
Parse natural language commands using Groq (primary) with Anthropic fallback.
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

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
- "ss on travel" → {"intent": "screenshot", "node": "travel-laptop", "args": {}, "confidence": 0.95}
"""


async def _call_groq(text: str) -> Optional[Dict[str, Any]]:
    """Call Groq API for command parsing."""
    if not settings.GROQ_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": COMMAND_PARSER_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.1
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                result_text = data["choices"][0]["message"]["content"].strip()
                
                # Extract JSON if wrapped in code blocks
                if "```" in result_text:
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
                
                result = json.loads(result_text)
                logger.info(f"Groq parsed '{text}' → {result}")
                return result
            else:
                logger.warning(f"Groq API error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Groq parsing error: {e}")
        return None


async def _call_anthropic(text: str) -> Optional[Dict[str, Any]]:
    """Call Anthropic API for command parsing (fallback)."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=COMMAND_PARSER_PROMPT,
            messages=[{"role": "user", "content": text}]
        )
        
        result_text = response.content[0].text.strip()
        
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        result = json.loads(result_text)
        logger.info(f"Anthropic parsed '{text}' → {result}")
        return result
        
    except Exception as e:
        logger.error(f"Anthropic parsing error: {e}")
        return None


async def parse_command(text: str) -> Dict[str, Any]:
    """
    Parse natural language command into structured format.
    Uses Groq (primary) with Anthropic fallback.
    
    Args:
        text: User's natural language command
        
    Returns:
        Parsed command with intent, node, args, and confidence
    """
    
    # Quick pattern matching for common commands (save API calls)
    text_lower = text.lower().strip()
    
    # Detect node from text
    node = "plc-laptop"  # default
    if "travel" in text_lower:
        node = "travel-laptop"
    
    # Screenshot shortcuts
    if text_lower in ["screenshot", "screen", "ss", "snap"] or text_lower.startswith("ss "):
        return {
            "intent": "screenshot",
            "node": node,
            "args": {},
            "confidence": 1.0
        }
    
    # Shell commands with explicit prefix
    if text_lower.startswith("run ") or text_lower.startswith("shell ") or text_lower.startswith("cmd "):
        prefix_len = 4 if text_lower.startswith("run ") else (6 if text_lower.startswith("shell ") else 4)
        command = text[prefix_len:].strip()
        # Remove node reference from command
        command = command.replace("on plc-laptop", "").replace("on travel-laptop", "").replace("on plc", "").replace("on travel", "").strip()
        return {
            "intent": "shell",
            "node": node,
            "args": {"command": command},
            "confidence": 0.95
        }
    
    # Try Groq first (fast & free-tier friendly)
    result = await _call_groq(text)
    if result:
        return result
    
    # Fallback to Anthropic
    result = await _call_anthropic(text)
    if result:
        return result
    
    # Last resort: fallback to interpret intent
    logger.warning("All AI parsers failed, using fallback")
    return {
        "intent": "interpret",
        "node": node,
        "args": {"instruction": text},
        "confidence": 0.3
    }
