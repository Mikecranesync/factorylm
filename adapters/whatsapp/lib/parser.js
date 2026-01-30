/**
 * WhatsApp Message Parser
 * Parses incoming Twilio webhook payloads
 * @module adapters/whatsapp/lib/parser
 */

class MessageParser {
  /**
   * Parse incoming Twilio webhook body
   * @param {Object} body - Request body from Twilio
   * @returns {Object} Parsed message object
   */
  parse(body) {
    const {
      MessageSid,
      AccountSid,
      From,
      To,
      Body,
      NumMedia,
      MediaContentType0,
      MediaUrl0,
      MediaContentType1,
      MediaUrl1,
      ProfileName,
      WaId,
      Forwarded,
      FrequentlyForwarded,
      ButtonText,
      ButtonPayload,
      Latitude,
      Longitude,
      Address
    } = body;
    
    // Parse phone number (remove whatsapp: prefix)
    const from = this.parsePhoneNumber(From);
    const to = this.parsePhoneNumber(To);
    
    // Build media array if present
    const media = this.parseMedia(body, parseInt(NumMedia) || 0);
    
    // Parse location if present
    const location = Latitude && Longitude ? {
      latitude: parseFloat(Latitude),
      longitude: parseFloat(Longitude),
      address: Address || null
    } : null;
    
    // Parse button response if present
    const button = ButtonText ? {
      text: ButtonText,
      payload: ButtonPayload
    } : null;
    
    return {
      // Message identifiers
      id: MessageSid,
      accountSid: AccountSid,
      
      // Participants
      from,
      to,
      profileName: ProfileName || null,
      whatsappId: WaId || null,
      
      // Content
      text: Body || '',
      media,
      location,
      button,
      
      // Metadata
      isForwarded: Forwarded === 'true',
      isFrequentlyForwarded: FrequentlyForwarded === 'true',
      
      // Timestamp
      timestamp: new Date(),
      
      // Original body (for debugging)
      _raw: body
    };
  }
  
  /**
   * Parse phone number from WhatsApp format
   * @param {string} number - Number in format whatsapp:+1234567890
   * @returns {string} Clean phone number
   */
  parsePhoneNumber(number) {
    if (!number) return null;
    return number.replace(/^whatsapp:/, '');
  }
  
  /**
   * Parse media attachments
   * @param {Object} body - Request body
   * @param {number} numMedia - Number of media items
   * @returns {Array} Array of media objects
   */
  parseMedia(body, numMedia) {
    const media = [];
    
    for (let i = 0; i < numMedia; i++) {
      const contentType = body[`MediaContentType${i}`];
      const url = body[`MediaUrl${i}`];
      
      if (url) {
        media.push({
          index: i,
          contentType,
          url,
          type: this.getMediaType(contentType)
        });
      }
    }
    
    return media;
  }
  
  /**
   * Determine media type from content type
   * @param {string} contentType - MIME type
   * @returns {string} Simplified type (image, audio, video, document)
   */
  getMediaType(contentType) {
    if (!contentType) return 'unknown';
    
    if (contentType.startsWith('image/')) return 'image';
    if (contentType.startsWith('audio/')) return 'audio';
    if (contentType.startsWith('video/')) return 'video';
    if (contentType.includes('pdf')) return 'document';
    if (contentType.includes('document')) return 'document';
    
    return 'file';
  }
  
  /**
   * Check if message is a voice note
   * @param {Object} message - Parsed message
   * @returns {boolean}
   */
  isVoiceNote(message) {
    return message.media.some(m => 
      m.type === 'audio' && 
      (m.contentType.includes('ogg') || m.contentType.includes('opus'))
    );
  }
  
  /**
   * Check if message has images
   * @param {Object} message - Parsed message
   * @returns {boolean}
   */
  hasImages(message) {
    return message.media.some(m => m.type === 'image');
  }
  
  /**
   * Get first image URL from message
   * @param {Object} message - Parsed message
   * @returns {string|null}
   */
  getFirstImageUrl(message) {
    const image = message.media.find(m => m.type === 'image');
    return image ? image.url : null;
  }
}

module.exports = { MessageParser };
