import json
import os  # Real GROQ_API_KEY lives in Doppler / environment variables

path = "/root/.openclaw/openclaw.json"
with open(path) as f:
    d = json.load(f)

# Add Groq API key to env
d["env"]["GROQ_API_KEY"] = os.environ["GROQ_API_KEY"]

# Add Groq as provider
if "providers" not in d["models"]:
    d["models"]["providers"] = {}

d["models"]["providers"]["groq"] = {
    "baseUrl": "https://api.groq.com/openai/v1",
    "apiKey": os.environ["GROQ_API_KEY"],  # Real key in Doppler
    "api": "openai-completions",
    "models": [
        {
            "id": "llama-3.3-70b-versatile",
            "name": "Llama 3.3 70B (Groq)",
            "reasoning": False,
            "input": ["text"],
            "contextWindow": 131072,
            "maxTokens": 32768
        },
        {
            "id": "llama-3.1-8b-instant",
            "name": "Llama 3.1 8B Instant (Groq)",
            "reasoning": False,
            "input": ["text"],
            "contextWindow": 131072,
            "maxTokens": 8192
        },
        {
            "id": "deepseek-r1-distill-llama-70b",
            "name": "DeepSeek R1 70B (Groq)",
            "reasoning": True,
            "input": ["text"],
            "contextWindow": 131072,
            "maxTokens": 16384
        }
    ]
}

# Set Groq llama-3.3-70b as primary (fast + free tier), Anthropic as fallback
d["agents"]["defaults"]["model"]["primary"] = "groq/llama-3.3-70b-versatile"
d["agents"]["defaults"]["model"]["fallbacks"] = [
    "groq/deepseek-r1-distill-llama-70b",
    "anthropic/claude-sonnet-4-20250514",
    "google/gemini-2.5-flash"
]

with open(path, "w") as f:
    json.dump(d, f, indent=2)

print("DONE: Added Groq provider, primary=groq/llama-3.3-70b-versatile")
