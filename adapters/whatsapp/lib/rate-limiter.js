/**
 * Rate Limiter for WhatsApp API
 * Prevents exceeding WhatsApp/Twilio rate limits
 * @module adapters/whatsapp/lib/rate-limiter
 */

class RateLimiter {
  /**
   * Create a rate limiter
   * @param {Object} options
   * @param {number} options.maxPerMinute - Max messages per minute per recipient
   * @param {number} options.maxPerHour - Max messages per hour per recipient
   * @param {number} options.globalMaxPerMinute - Global max messages per minute
   */
  constructor(options = {}) {
    this.maxPerMinute = options.maxPerMinute || 60;
    this.maxPerHour = options.maxPerHour || 1000;
    this.globalMaxPerMinute = options.globalMaxPerMinute || 100;
    
    // Track per-recipient
    this.recipients = new Map();
    
    // Track global
    this.globalMinute = [];
    
    // Cleanup interval
    this.cleanupInterval = setInterval(() => this.cleanup(), 60000);
  }
  
  /**
   * Check if sending is allowed
   * @param {string} recipient - Recipient phone number
   * @returns {boolean} True if allowed
   */
  check(recipient) {
    const now = Date.now();
    
    // Check global limit
    if (!this.checkGlobal(now)) {
      return false;
    }
    
    // Check per-recipient limit
    if (!this.checkRecipient(recipient, now)) {
      return false;
    }
    
    // Record the send
    this.record(recipient, now);
    
    return true;
  }
  
  /**
   * Check global rate limit
   */
  checkGlobal(now) {
    const minuteAgo = now - 60000;
    this.globalMinute = this.globalMinute.filter(t => t > minuteAgo);
    return this.globalMinute.length < this.globalMaxPerMinute;
  }
  
  /**
   * Check per-recipient rate limit
   */
  checkRecipient(recipient, now) {
    let record = this.recipients.get(recipient);
    
    if (!record) {
      return true;
    }
    
    const minuteAgo = now - 60000;
    const hourAgo = now - 3600000;
    
    // Filter old entries
    record.minute = record.minute.filter(t => t > minuteAgo);
    record.hour = record.hour.filter(t => t > hourAgo);
    
    // Check limits
    if (record.minute.length >= this.maxPerMinute) {
      console.warn(`Rate limit: ${recipient} exceeded per-minute limit`);
      return false;
    }
    
    if (record.hour.length >= this.maxPerHour) {
      console.warn(`Rate limit: ${recipient} exceeded per-hour limit`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Record a send
   */
  record(recipient, now) {
    // Global
    this.globalMinute.push(now);
    
    // Per-recipient
    let record = this.recipients.get(recipient);
    if (!record) {
      record = { minute: [], hour: [] };
      this.recipients.set(recipient, record);
    }
    
    record.minute.push(now);
    record.hour.push(now);
  }
  
  /**
   * Get current rate for recipient
   * @param {string} recipient
   * @returns {Object} Rate info
   */
  getRate(recipient) {
    const now = Date.now();
    const record = this.recipients.get(recipient);
    
    if (!record) {
      return { minuteCount: 0, hourCount: 0 };
    }
    
    const minuteAgo = now - 60000;
    const hourAgo = now - 3600000;
    
    return {
      minuteCount: record.minute.filter(t => t > minuteAgo).length,
      hourCount: record.hour.filter(t => t > hourAgo).length,
      maxPerMinute: this.maxPerMinute,
      maxPerHour: this.maxPerHour
    };
  }
  
  /**
   * Cleanup old entries
   */
  cleanup() {
    const now = Date.now();
    const hourAgo = now - 3600000;
    
    for (const [recipient, record] of this.recipients) {
      record.hour = record.hour.filter(t => t > hourAgo);
      record.minute = record.minute.filter(t => t > now - 60000);
      
      // Remove empty records
      if (record.hour.length === 0) {
        this.recipients.delete(recipient);
      }
    }
    
    this.globalMinute = this.globalMinute.filter(t => t > now - 60000);
  }
  
  /**
   * Reset all limits
   */
  reset() {
    this.recipients.clear();
    this.globalMinute = [];
  }
  
  /**
   * Stop cleanup interval
   */
  destroy() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }
  }
}

module.exports = { RateLimiter };
