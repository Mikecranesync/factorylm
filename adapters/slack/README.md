# FactoryLM Slack Adapter

Slack integration for FactoryLM industrial maintenance platform. Enables enterprise teams to interact with FactoryLM via Slack.

## Features

- Direct message conversations with AI assistant
- @mention support in channels
- Rich Block Kit message formatting
- File/image sharing for equipment photos
- Thread support for contextual conversations
- Spanish language support

## Installation

```bash
npm install @factorylm/slack-adapter
# or
cd adapters/slack && npm install
```

## Slack App Setup

### 1. Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name: "FactoryLM" (or your preference)
4. Select your workspace

### 2. Configure Bot

**OAuth & Permissions → Scopes (Bot Token Scopes):**
- `app_mentions:read` - Read @mentions
- `chat:write` - Send messages
- `files:read` - Access shared files
- `im:history` - Read DM history
- `im:read` - Read DM metadata
- `im:write` - Send DMs
- `users:read` - Get user info

### 3. Enable Socket Mode (Recommended)

1. Go to "Socket Mode" in sidebar
2. Enable Socket Mode
3. Generate App-Level Token with `connections:write` scope
4. Save the token (starts with `xapp-`)

### 4. Subscribe to Events

**Event Subscriptions → Subscribe to bot events:**
- `app_mention`
- `message.im`
- `file_shared` (optional)

### 5. Install to Workspace

1. Go to "Install App"
2. Click "Install to Workspace"
3. Authorize
4. Copy Bot User OAuth Token (starts with `xoxb-`)

## Configuration

### Environment Variables

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode
```

### Basic Setup

```javascript
const { SlackAdapter } = require('@factorylm/slack-adapter');

const slack = new SlackAdapter({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  appToken: process.env.SLACK_APP_TOKEN,
  socketMode: true,
  
  // Handle direct messages
  onMessage: async (message, { reply, replyBlocks }) => {
    console.log(`DM from ${message.userId}: ${message.text}`);
    
    // Your AI processing
    const response = await processWithAI(message.text);
    
    // Simple reply
    await reply(response);
    
    // Or rich reply with blocks
    // await replyBlocks(slack.buildDiagnosticBlocks(result));
  },
  
  // Handle @mentions (optional, defaults to onMessage)
  onMention: async (message, { replyInThread }) => {
    console.log(`Mentioned in ${message.channel}: ${message.text}`);
    await replyInThread('Analizando su consulta...');
  }
});

// Start the adapter
await slack.start();
```

## Message Object

Incoming messages are parsed into this format:

```javascript
{
  id: 'msg_123',           // Message ID
  ts: '1234567890.123456', // Slack timestamp
  threadTs: '...',         // Thread timestamp (if in thread)
  
  userId: 'U12345',        // Sender user ID
  channel: 'D12345',       // Channel/DM ID
  
  text: 'El motor vibra',  // Cleaned text
  rawText: '<@U123> El...', // Original text
  
  files: [                 // Attached files
    {
      id: 'F123',
      name: 'motor.jpg',
      type: 'image',
      url: 'https://...',
      downloadUrl: 'https://...'
    }
  ],
  
  isThread: false,
  timestamp: Date
}
```

## Sending Messages

### Simple Reply

```javascript
await reply('Diagnóstico completado');
```

### Rich Blocks

```javascript
const blocks = slack.buildDiagnosticBlocks({
  equipment: 'Bomba P-101',
  cause: 'Desgaste de rodamientos',
  confidence: 85,
  recommendation: 'Programar reemplazo de rodamientos'
});

await replyBlocks(blocks);
```

### To Specific Channel

```javascript
await slack.sendToChannel('C12345', 'Alerta de mantenimiento');
```

### Direct Message

```javascript
await slack.sendDM('U12345', 'Su diagnóstico está listo');
```

## Block Builders

Built-in block builders for common messages:

### Diagnostic Result

```javascript
const blocks = slack.buildDiagnosticBlocks({
  equipment: 'Bomba P-101',
  cause: 'Cavitación',
  confidence: 90,
  recommendation: 'Verificar presión de entrada',
  showActions: true
});
```

### Maintenance Alert

```javascript
const blocks = slack.buildAlertBlocks({
  id: 'alert_123',
  equipment: 'Motor M-205',
  severity: 'high',  // critical, high, medium, low
  location: 'Planta Maracaibo',
  status: 'Pendiente',
  description: 'Vibración anormal detectada',
  action: 'Inspección visual requerida'
});
```

## Multi-Workspace Support

For enterprise deployments across multiple workspaces:

```javascript
const workspaces = new Map();

function getAdapter(teamId) {
  if (!workspaces.has(teamId)) {
    // Load credentials from database
    const creds = loadCredentials(teamId);
    workspaces.set(teamId, new SlackAdapter(creds));
  }
  return workspaces.get(teamId);
}
```

## Testing

```bash
npm test
```

## Related

- [GitHub Issue #11](https://github.com/Mikecranesync/factorylm/issues/11)
- [Slack Bolt Documentation](https://slack.dev/bolt-js)
- [Block Kit Builder](https://app.slack.com/block-kit-builder)

## License

MIT - FactoryLM Team
