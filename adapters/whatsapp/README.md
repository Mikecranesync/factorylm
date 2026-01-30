# FactoryLM WhatsApp Adapter

WhatsApp Business API integration for FactoryLM industrial maintenance platform.

## 🇻🇪 Built for Venezuela

This adapter was specifically designed for the Venezuelan oil market where WhatsApp is the dominant messaging platform. Features include:

- Spanish-first message templates
- Voice note support (technicians can describe problems verbally)
- Image handling (equipment photos)
- Offline-friendly design

## Installation

```bash
npm install @factorylm/whatsapp-adapter
# or
cd adapters/whatsapp && npm install
```

## Configuration

### Environment Variables

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=+14155238886
```

### Basic Setup

```javascript
const express = require('express');
const { WhatsAppAdapter } = require('@factorylm/whatsapp-adapter');

const app = express();

const whatsapp = new WhatsAppAdapter({
  accountSid: process.env.TWILIO_ACCOUNT_SID,
  authToken: process.env.TWILIO_AUTH_TOKEN,
  whatsappNumber: process.env.TWILIO_WHATSAPP_NUMBER,
  
  // Handle incoming messages
  onMessage: async (message, adapter) => {
    console.log(`From ${message.from}: ${message.text}`);
    
    // Your AI processing here
    const response = await processWithAI(message.text);
    
    // Send response
    await adapter.send(message.from, response);
  }
});

// Mount webhook routes
app.use(whatsapp.getRouter());

app.listen(3000);
```

## Message Object

Incoming messages are parsed into this format:

```javascript
{
  id: 'SMxxxxx',           // Twilio Message SID
  from: '+584121234567',   // Sender phone number
  to: '+14155238886',      // Your WhatsApp number
  profileName: 'Juan',     // WhatsApp profile name
  text: 'El motor vibra',  // Message text
  media: [                 // Attachments
    {
      type: 'image',
      contentType: 'image/jpeg',
      url: 'https://...'
    }
  ],
  location: {              // If location shared
    latitude: 10.4806,
    longitude: -66.9036,
    address: 'Maracaibo, Venezuela'
  },
  isForwarded: false,
  timestamp: Date
}
```

## Sending Messages

### Text Message

```javascript
await whatsapp.send('+584121234567', 'Diagnóstico completado');
```

### With Media

```javascript
await whatsapp.sendMedia(
  '+584121234567',
  'Aquí está el diagrama del circuito',
  'https://example.com/diagram.png'
);
```

### Using Templates (Proactive)

For messages outside the 24-hour conversation window:

```javascript
await whatsapp.sendTemplate('+584121234567', 'maintenance_alert', {
  equipment: 'Bomba P-101',
  status: 'Alarma alta',
  location: 'Planta Maracaibo',
  action: 'Verificar presión de entrada'
});
```

## Built-in Templates (Spanish)

| Template | Purpose |
|----------|---------|
| `maintenance_alert` | Equipment alerts |
| `diagnostic_result` | AI diagnosis results |
| `maintenance_reminder` | Scheduled maintenance |
| `welcome` | New user onboarding |
| `help` | Available commands |
| `error` | Error messages |

## Twilio Setup

### Development (Sandbox)

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Messaging > Try it out > Send a WhatsApp message
3. Follow instructions to join sandbox
4. Use sandbox number for testing

### Production

1. Apply for WhatsApp Business API access
2. Complete Facebook Business verification
3. Submit message templates for approval
4. Configure production phone number

## Webhook Configuration

Configure your Twilio webhook URL:

```
https://your-domain.com/whatsapp/webhook
```

For local development, use ngrok:

```bash
ngrok http 3000
# Use the ngrok URL in Twilio console
```

## Rate Limiting

Built-in rate limiting prevents API abuse:

- 60 messages/minute per recipient
- 1000 messages/hour per recipient
- 100 messages/minute global

## Testing

```bash
npm test
```

## Related

- [GitHub Issue #10](https://github.com/Mikecranesync/factorylm/issues/10)
- [WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)

## License

MIT - FactoryLM Team
