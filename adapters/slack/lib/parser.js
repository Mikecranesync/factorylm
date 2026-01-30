/**
 * Slack Message Parser
 * Parses incoming Slack events into a standard format
 * @module adapters/slack/lib/parser
 */

class MessageParser {
  /**
   * Parse a direct message event
   * @param {Object} message - Slack message event
   * @returns {Object} Parsed message
   */
  parse(message) {
    return {
      // Message identifiers
      id: message.client_msg_id || message.ts,
      ts: message.ts,
      threadTs: message.thread_ts,
      
      // Participants
      userId: message.user,
      channel: message.channel,
      channelType: message.channel_type,
      
      // Content
      text: this.cleanText(message.text || ''),
      rawText: message.text || '',
      
      // Attachments
      files: this.parseFiles(message.files),
      
      // Metadata
      isThread: !!message.thread_ts,
      isEdited: !!message.edited,
      
      // Timestamp
      timestamp: new Date(parseFloat(message.ts) * 1000),
      
      // Original event
      _raw: message
    };
  }
  
  /**
   * Parse an app_mention event
   * @param {Object} event - Slack app_mention event
   * @returns {Object} Parsed mention
   */
  parseMention(event) {
    return {
      // Message identifiers
      id: event.client_msg_id || event.ts,
      ts: event.ts,
      threadTs: event.thread_ts,
      
      // Participants
      userId: event.user,
      channel: event.channel,
      
      // Content (remove the @mention)
      text: this.removeMention(event.text || ''),
      rawText: event.text || '',
      
      // Attachments
      files: this.parseFiles(event.files),
      
      // Metadata
      isThread: !!event.thread_ts,
      
      // Timestamp
      timestamp: new Date(parseFloat(event.ts) * 1000),
      
      // Original event
      _raw: event
    };
  }
  
  /**
   * Clean text by removing special Slack formatting
   * @param {string} text - Raw text
   * @returns {string} Cleaned text
   */
  cleanText(text) {
    return text
      // Remove user mentions: <@U12345> -> @user
      .replace(/<@([A-Z0-9]+)>/g, '@user')
      // Remove channel mentions: <#C12345|channel> -> #channel
      .replace(/<#([A-Z0-9]+)\|([^>]+)>/g, '#$2')
      // Remove URLs: <https://...|label> -> label or URL
      .replace(/<(https?:\/\/[^|>]+)\|([^>]+)>/g, '$2')
      .replace(/<(https?:\/\/[^>]+)>/g, '$1')
      // Remove special commands: <!here>, <!channel>, <!everyone>
      .replace(/<!(\w+)>/g, '@$1')
      .trim();
  }
  
  /**
   * Remove bot mention from text
   * @param {string} text - Text with mention
   * @returns {string} Text without mention
   */
  removeMention(text) {
    return text
      .replace(/<@[A-Z0-9]+>/g, '')
      .trim();
  }
  
  /**
   * Parse file attachments
   * @param {Array} files - Slack files array
   * @returns {Array} Parsed files
   */
  parseFiles(files) {
    if (!files || !Array.isArray(files)) {
      return [];
    }
    
    return files.map(file => ({
      id: file.id,
      name: file.name,
      title: file.title,
      mimetype: file.mimetype,
      filetype: file.filetype,
      size: file.size,
      url: file.url_private,
      downloadUrl: file.url_private_download,
      thumbnail: file.thumb_360 || file.thumb_160,
      type: this.getFileType(file.mimetype)
    }));
  }
  
  /**
   * Determine file type from mimetype
   * @param {string} mimetype - MIME type
   * @returns {string} Simplified type
   */
  getFileType(mimetype) {
    if (!mimetype) return 'unknown';
    
    if (mimetype.startsWith('image/')) return 'image';
    if (mimetype.startsWith('audio/')) return 'audio';
    if (mimetype.startsWith('video/')) return 'video';
    if (mimetype.includes('pdf')) return 'pdf';
    if (mimetype.includes('spreadsheet') || mimetype.includes('excel')) return 'spreadsheet';
    if (mimetype.includes('document') || mimetype.includes('word')) return 'document';
    
    return 'file';
  }
  
  /**
   * Extract user IDs mentioned in text
   * @param {string} text - Raw text
   * @returns {string[]} Array of user IDs
   */
  extractMentionedUsers(text) {
    const matches = text.match(/<@([A-Z0-9]+)>/g) || [];
    return matches.map(m => m.replace(/<@|>/g, ''));
  }
  
  /**
   * Extract channel IDs mentioned in text
   * @param {string} text - Raw text
   * @returns {string[]} Array of channel IDs
   */
  extractMentionedChannels(text) {
    const matches = text.match(/<#([A-Z0-9]+)\|[^>]+>/g) || [];
    return matches.map(m => m.match(/<#([A-Z0-9]+)/)[1]);
  }
  
  /**
   * Check if message has images
   * @param {Object} message - Parsed message
   * @returns {boolean}
   */
  hasImages(message) {
    return message.files.some(f => f.type === 'image');
  }
  
  /**
   * Get first image from message
   * @param {Object} message - Parsed message
   * @returns {Object|null}
   */
  getFirstImage(message) {
    return message.files.find(f => f.type === 'image') || null;
  }
}

module.exports = { MessageParser };
