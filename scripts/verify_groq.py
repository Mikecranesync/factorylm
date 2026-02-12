import json
cfg = json.load(open('/root/.clawdbot/clawdbot.json'))
print('PROVIDERS:', list(cfg['models']['providers'].keys()))
print('PRIMARY:', cfg['agents']['defaults']['model']['primary'])
print('FALLBACKS:', cfg['agents']['defaults']['model']['fallbacks'])
print('GROQ MODELS:', [m['id'] for m in cfg['models']['providers']['groq']['models']])
print('GROQ_API_KEY set:', 'GROQ_API_KEY' in cfg.get('env', {}))
