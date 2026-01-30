/**
 * FactoryLM WhatsApp Adapter
 * 
 * Enables FactoryLM to communicate with technicians via WhatsApp.
 * Uses Twilio WhatsApp API for messaging.
 * 
 * @module adapters/whatsapp
 * @see https://github.com/Mikecranesync/factorylm/issues/10
 */

const express = require('express');
const twilio = require('twilio');
const { WhatsAppClient } = require('./lib/client');
const { MessageParser } = require('./lib/parser');
const { TemplateManager } = require('./lib/templates');
const { RateLimiter } = require('./lib/rate-limiter');

class WhatsAppAdapter {
  /**
   * Create a WhatsApp adapter instance
   * @param {Object} config - Configuration options
   * @param {string} config.accountSid - Twilio Account SID
   * @param {string} config.authToken - Twilio Auth Token
   * @param {string} config.whatsappNumber - WhatsApp sender number (with country code)
   * @param {string} config.webhookPath - Path for incoming webhook (default: /whatsapp/webhook)
   * @param {Function} config.onMessage - Callback for incoming messages
   */
  constructor(config) {
    this.validateConfig(config);
    
    this.config = {
      webhookPath: '/whatsapp/webhook',
      ...config
    };
    
    // Initialize components
    this.client = new WhatsAppClient({
      accountSid: config.accountSid,
      authToken: config.authToken,
      whatsappNumber: config.whatsappNumber
    });
    
    this.parser = new MessageParser();
    this.templates = new TemplateManager();
    this.rateLimiter = new RateLimiter({
      maxPerMinute: 60,
      maxPerHour: 1000
    });
    
    this.onMessage = config.onMessage || (() => {});
    
    // Track conversations for 24-hour window
    this.conversations = new Map();
  }
  
  /**
   * Validate required configuration
   */
  validateConfig(config) {
    const required = ['accountSid', 'authToken', 'whatsappNumber'];
    for (const key of required) {
      if (!config[key]) {
        throw new Error(`WhatsAppAdapter: Missing required config: ${key}`);
      }
    }
  }
  
  /**
   * Get Express router for webhook endpoints
   * @returns {express.Router}
   */
  getRouter() {
    const router = express.Router();
    
    // Webhook for incoming messages
    router.post(this.config.webhookPath, express.urlencoded({ extended: false }), 
      this.handleIncomingWebhook.bind(this));
    
    // Status callback
    router.post(`${this.config.webhookPath}/status`, express.urlencoded({ extended: false }),
      this.handleStatusCallback.bind(this));
    
    return router;
  }
  
  /**
   * Handle incoming WhatsApp webhook
   */
  async handleIncomingWebhook(req, res) {
    try {
      // Validate Twilio signature in production
      if (process.env.NODE_ENV === 'production') {
        const signature = req.headers['x-twilio-signature'];
        const url = `${req.protocol}://${req.get('host')}${req.originalUrl}`;
        
        if (!twilio.validateRequest(this.config.authToken, signature, url, req.body)) {
          console.error('WhatsApp: Invalid Twilio signature');
          return res.status(403).send('Invalid signature');
        }
      }
      
      // Parse incoming message
      const message = this.parser.parse(req.body);
      
      // Update conversation tracking (for 24-hour window)
      this.updateConversation(message.from);
      
      // Log incoming message
      console.log(`WhatsApp IN [${message.from}]: ${message.text || '[media]'}`);
      
      // Call message handler
      await this.onMessage(message, this);
      
      // Respond to Twilio
      res.status(200).send('OK');
      
    } catch (error) {
      console.error('WhatsApp webhook error:', error);
      res.status(500).send('Error processing message');
    }
  }
  
  /**
   * Handle status callback from Twilio
   */
  handleStatusCallback(req, res) {
    const { MessageSid, MessageStatus, To, ErrorCode } = req.body;
    
    if (ErrorCode) {
      console.error(`WhatsApp delivery error [${MessageSid}]: ${ErrorCode}`);
    } else {
      console.log(`WhatsApp status [${MessageSid}]: ${MessageStatus}`);
    }
    
    res.status(200).send('OK');
  }
  
  /**
   * Send a text message
   * @param {string} to - Recipient phone number (with country code)
   * @param {string} text - Message text
   * @returns {Promise<Object>} Twilio message response
   */
  async send(to, text) {
    // Check rate limits
    if (!this.rateLimiter.check(to)) {
      throw new Error('Rate limit exceeded for recipient');
    }
    
    // Check if within 24-hour conversation window
    const inWindow = this.isInConversationWindow(to);
    
    if (!inWindow) {
      console.warn(`WhatsApp: Outside 24hr window for ${to}, may need template`);
    }
    
    console.log(`WhatsApp OUT [${to}]: ${text.substring(0, 50)}...`);
    
    return this.client.sendText(to, text);
  }
  
  /**
   * Send a message with media
   * @param {string} to - Recipient phone number
   * @param {string} text - Message text
   * @param {string} mediaUrl - URL of media to send
   * @returns {Promise<Object>}
   */
  async sendMedia(to, text, mediaUrl) {
    if (!this.rateLimiter.check(to)) {
      throw new Error('Rate limit exceeded for recipient');
    }
    
    console.log(`WhatsApp OUT [${to}]: ${text.substring(0, 30)}... [media: ${mediaUrl}]`);
    
    return this.client.sendMedia(to, text, mediaUrl);
  }
  
  /**
   * Send a template message (for proactive messaging outside 24hr window)
   * @param {string} to - Recipient phone number
   * @param {string} templateName - Approved template name
   * @param {Object} variables - Template variables
   * @returns {Promise<Object>}
   */
  async sendTemplate(to, templateName, variables) {
    const template = this.templates.get(templateName);
    if (!template) {
      throw new Error(`Unknown template: ${templateName}`);
    }
    
    const text = this.templates.render(templateName, variables);
    return this.client.sendText(to, text);
  }
  
  /**
   * Update conversation tracking
   */
  updateConversation(phoneNumber) {
    this.conversations.set(phoneNumber, {
      lastMessage: Date.now(),
      windowExpires: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
    });
  }
  
  /**
   * Check if within 24-hour conversation window
   */
  isInConversationWindow(phoneNumber) {
    const conv = this.conversations.get(phoneNumber);
    if (!conv) return false;
    return Date.now() < conv.windowExpires;
  }
  
  /**
   * Clean up expired conversation windows
   */
  cleanupConversations() {
    const now = Date.now();
    for (const [phone, conv] of this.conversations) {
      if (now > conv.windowExpires) {
        this.conversations.delete(phone);
      }
    }
  }
}

module.exports = { WhatsAppAdapter };
