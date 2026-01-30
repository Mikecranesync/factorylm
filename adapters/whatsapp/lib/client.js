/**
 * WhatsApp Client - Twilio API wrapper
 * @module adapters/whatsapp/lib/client
 */

const twilio = require('twilio');

class WhatsAppClient {
  /**
   * Create a WhatsApp client
   * @param {Object} config
   * @param {string} config.accountSid - Twilio Account SID
   * @param {string} config.authToken - Twilio Auth Token
   * @param {string} config.whatsappNumber - WhatsApp number (e.g., +14155238886)
   */
  constructor(config) {
    this.client = twilio(config.accountSid, config.authToken);
    this.fromNumber = this.formatWhatsAppNumber(config.whatsappNumber);
  }
  
  /**
   * Format phone number for WhatsApp
   * @param {string} number - Phone number
   * @returns {string} Formatted number (whatsapp:+1234567890)
   */
  formatWhatsAppNumber(number) {
    // Remove any existing whatsapp: prefix
    let clean = number.replace(/^whatsapp:/, '');
    
    // Ensure + prefix
    if (!clean.startsWith('+')) {
      clean = '+' + clean;
    }
    
    return `whatsapp:${clean}`;
  }
  
  /**
   * Send a text message
   * @param {string} to - Recipient phone number
   * @param {string} body - Message text
   * @returns {Promise<Object>} Twilio message object
   */
  async sendText(to, body) {
    const toNumber = this.formatWhatsAppNumber(to);
    
    try {
      const message = await this.client.messages.create({
        body,
        from: this.fromNumber,
        to: toNumber
      });
      
      return {
        success: true,
        sid: message.sid,
        status: message.status,
        to: message.to,
        body: message.body
      };
    } catch (error) {
      console.error('WhatsApp send error:', error.message);
      return {
        success: false,
        error: error.message,
        code: error.code
      };
    }
  }
  
  /**
   * Send a message with media attachment
   * @param {string} to - Recipient phone number
   * @param {string} body - Message text
   * @param {string|string[]} mediaUrl - Media URL(s)
   * @returns {Promise<Object>}
   */
  async sendMedia(to, body, mediaUrl) {
    const toNumber = this.formatWhatsAppNumber(to);
    const mediaUrls = Array.isArray(mediaUrl) ? mediaUrl : [mediaUrl];
    
    try {
      const message = await this.client.messages.create({
        body,
        from: this.fromNumber,
        to: toNumber,
        mediaUrl: mediaUrls
      });
      
      return {
        success: true,
        sid: message.sid,
        status: message.status,
        to: message.to,
        numMedia: mediaUrls.length
      };
    } catch (error) {
      console.error('WhatsApp media send error:', error.message);
      return {
        success: false,
        error: error.message,
        code: error.code
      };
    }
  }
  
  /**
   * Get message status
   * @param {string} messageSid - Message SID
   * @returns {Promise<Object>}
   */
  async getMessageStatus(messageSid) {
    try {
      const message = await this.client.messages(messageSid).fetch();
      return {
        sid: message.sid,
        status: message.status,
        errorCode: message.errorCode,
        errorMessage: message.errorMessage
      };
    } catch (error) {
      return {
        error: error.message
      };
    }
  }
}

module.exports = { WhatsAppClient };
