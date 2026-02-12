import json

with open('/root/.clawdbot/clawdbot.json') as f:
    cfg = json.load(f)

cfg['env']['GROQ_API_KEY'] = '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'

cfg['models']['providers']['groq'] = {
    'baseUrl': 'https://api.groq.com/openai/v1',
    'apiKey': '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',
    'api': 'openai-completions',
    'models': [
        {'id': 'llama-3.3-70b-versatile', 'name': 'Llama 3.3 70B (Groq)', 'reasoning': False, 'input': ['text'], 'contextWindow': 131072, 'maxTokens': 32768, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}},
        {'id': 'llama-3.1-8b-instant', 'name': 'Llama 3.1 8B Instant (Groq)', 'reasoning': False, 'input': ['text'], 'contextWindow': 131072, 'maxTokens': 8192, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}},
        {'id': 'deepseek-r1-distill-llama-70b', 'name': 'DeepSeek R1 70B (Groq)', 'reasoning': True, 'input': ['text'], 'contextWindow': 131072, 'maxTokens': 16384, 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}}
    ]
}

cfg['agents']['defaults']['model'] = {
    'primary': 'groq/llama-3.3-70b-versatile',
    'fallbacks': ['groq/deepseek-r1-distill-llama-70b', 'anthropic/claude-sonnet-4-20250514', 'google/gemini-2.5-flash']
}

with open('/root/.clawdbot/clawdbot.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print('Done - Groq added to Hostinger')
