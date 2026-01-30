/**
 * FactoryLM Slack Adapter
 * 
 * Enables FactoryLM to communicate with enterprise teams via Slack.
 * Uses Slack Bolt framework for event handling.
 * 
 * @module adapters/slack
 * @see https://github.com/Mikecranesync/factorylm/issues/11
 */

const { App, ExpressReceiver } = require('@slack/bolt');
const { BlockBuilder } = require('./lib/blocks');
const { MessageParser } = require('./lib/parser');

class SlackAdapter {
  /**
   * Create a Slack adapter instance
   * @param {Object} config - Configuration options
   * @param {string} config.token - Slack Bot Token (xoxb-...)
   * @param {string} config.signingSecret - Slack Signing Secret
   * @param {string} config.appToken - Slack App Token for Socket Mode (xapp-...)
   * @param {boolean} config.socketMode - Use Socket Mode (default: true)
   * @param {Function} config.onMessage - Callback for incoming messages
   * @param {Function} config.onMention - Callback for @mentions
   */
  constructor(config) {
    this.validateConfig(config);
    this.config = config;
    
    // Initialize components
    this.blocks = new BlockBuilder();
    this.parser = new MessageParser();
    this.onMessage = config.onMessage || (() => {});
    this.onMention = config.onMention || this.onMessage;
    
    // Initialize Slack app
    this.initializeApp();
  }
  
  /**
   * Validate required configuration
   */
  validateConfig(config) {
    const required = ['token', 'signingSecret'];
    for (const key of required) {
      if (!config[key]) {
        throw new Error(`SlackAdapter: Missing required config: ${key}`);
      }
    }
    
    if (config.socketMode && !config.appToken) {
      throw new Error('SlackAdapter: appToken required for Socket Mode');
    }
  }
  
  /**
   * Initialize Slack Bolt app
   */
  initializeApp() {
    const appConfig = {
      token: this.config.token,
      signingSecret: this.config.signingSecret
    };
    
    if (this.config.socketMode !== false) {
      // Socket Mode (recommended for development and internal apps)
      appConfig.socketMode = true;
      appConfig.appToken = this.config.appToken;
    }
    
    this.app = new App(appConfig);
    
    // Register event handlers
    this.registerHandlers();
  }
  
  /**
   * Register Slack event handlers
   */
  registerHandlers() {
    // Handle direct messages
    this.app.message(async ({ message, say, client }) => {
      // Ignore bot messages
      if (message.bot_id) return;
      
      // Parse message
      const parsed = this.parser.parse(message);
      
      console.log(`Slack DM [${parsed.userId}]: ${parsed.text.substring(0, 50)}...`);
      
      // Call handler
      try {
        await this.onMessage(parsed, {
          say,
          reply: (text) => this.reply(say, text),
          replyBlocks: (blocks) => this.replyBlocks(say, blocks),
          client
        });
      } catch (error) {
        console.error('Slack message handler error:', error);
        await say('Lo siento, hubo un error procesando su mensaje.');
      }
    });
    
    // Handle @mentions in channels
    this.app.event('app_mention', async ({ event, say, client }) => {
      const parsed = this.parser.parseMention(event);
      
      console.log(`Slack mention [${parsed.channel}/${parsed.userId}]: ${parsed.text.substring(0, 50)}...`);
      
      try {
        await this.onMention(parsed, {
          say,
          reply: (text) => this.reply(say, text),
          replyBlocks: (blocks) => this.replyBlocks(say, blocks),
          replyInThread: (text) => this.replyInThread(client, event, text),
          client
        });
      } catch (error) {
        console.error('Slack mention handler error:', error);
        await say('Lo siento, hubo un error procesando su mensaje.');
      }
    });
    
    // Handle file shares
    this.app.event('file_shared', async ({ event, client }) => {
      console.log(`Slack file shared: ${event.file_id}`);
      // File handling can be added here
    });
    
    // Handle reactions (optional - for feedback)
    this.app.event('reaction_added', async ({ event }) => {
      console.log(`Reaction added: ${event.reaction} by ${event.user}`);
    });
  }
  
  /**
   * Start the Slack app
   * @param {number} port - Port for HTTP mode (ignored in Socket Mode)
   */
  async start(port = 3000) {
    await this.app.start(port);
    console.log(`Slack adapter started${this.config.socketMode !== false ? ' (Socket Mode)' : ` on port ${port}`}`);
  }
  
  /**
   * Stop the Slack app
   */
  async stop() {
    await this.app.stop();
  }
  
  /**
   * Get Express receiver for custom server integration
   * @returns {ExpressReceiver}
   */
  getReceiver() {
    if (this.config.socketMode !== false) {
      throw new Error('Cannot get receiver in Socket Mode');
    }
    return this.receiver;
  }
  
  /**
   * Send a simple text reply
   */
  async reply(say, text) {
    await say(text);
  }
  
  /**
   * Send a reply with Block Kit formatting
   */
  async replyBlocks(say, blocks) {
    await say({ blocks });
  }
  
  /**
   * Reply in a thread
   */
  async replyInThread(client, event, text) {
    await client.chat.postMessage({
      channel: event.channel,
      thread_ts: event.ts,
      text
    });
  }
  
  /**
   * Send a message to a channel
   * @param {string} channel - Channel ID
   * @param {string} text - Message text
   */
  async sendToChannel(channel, text) {
    await this.app.client.chat.postMessage({
      channel,
      text
    });
  }
  
  /**
   * Send blocks to a channel
   * @param {string} channel - Channel ID
   * @param {Array} blocks - Block Kit blocks
   * @param {string} text - Fallback text
   */
  async sendBlocksToChannel(channel, blocks, text = '') {
    await this.app.client.chat.postMessage({
      channel,
      text,
      blocks
    });
  }
  
  /**
   * Send a direct message to a user
   * @param {string} userId - User ID
   * @param {string} text - Message text
   */
  async sendDM(userId, text) {
    // Open DM channel
    const result = await this.app.client.conversations.open({
      users: userId
    });
    
    // Send message
    await this.app.client.chat.postMessage({
      channel: result.channel.id,
      text
    });
  }
  
  /**
   * Upload a file
   * @param {string} channel - Channel ID
   * @param {Buffer|string} content - File content or path
   * @param {Object} options - Upload options
   */
  async uploadFile(channel, content, options = {}) {
    await this.app.client.files.uploadV2({
      channel_id: channel,
      content,
      filename: options.filename || 'file',
      title: options.title,
      initial_comment: options.comment
    });
  }
  
  /**
   * Build diagnostic result blocks
   */
  buildDiagnosticBlocks(result) {
    return this.blocks.diagnostic(result);
  }
  
  /**
   * Build maintenance alert blocks
   */
  buildAlertBlocks(alert) {
    return this.blocks.alert(alert);
  }
}

module.exports = { SlackAdapter };
