// FactoryLM Diagnosis Skill for Clawdbot
// Routes factory questions to the diagnosis service

const DIAGNOSIS_URL = 'http://localhost:8200/diagnose';

const FACTORY_KEYWORDS = [
  'factory', 'plc', 'motor', 'conveyor', 'production', 'machine',
  'alarm', 'fault', 'status', 'diagnostic', 'sensor', 'actuator',
  'micro 820', 'allen-bradley', 'modbus', 'temperature', 'pressure'
];

function isFactoryQuestion(message) {
  const lower = message.toLowerCase();
  return FACTORY_KEYWORDS.some(keyword => lower.includes(keyword));
}

async function diagnose(question) {
  try {
    const response = await fetch(DIAGNOSIS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await response.json();
    return data.diagnosis || 'Unable to get diagnosis';
  } catch (error) {
    return 'Factory diagnosis service unavailable: ' + error.message;
  }
}

module.exports = {
  name: 'factorylm',
  description: 'AI-powered factory diagnostics',
  isFactoryQuestion,
  diagnose,

  // Main handler
  async handle(message) {
    if (!isFactoryQuestion(message)) {
      return null; // Not a factory question, let other handlers process
    }
    return await diagnose(message);
  }
};
