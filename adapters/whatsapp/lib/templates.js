/**
 * WhatsApp Template Manager
 * Manages message templates for proactive messaging
 * @module adapters/whatsapp/lib/templates
 */

/**
 * Default templates (Spanish for Venezuela market)
 * These need to be approved by WhatsApp before use in production
 */
const DEFAULT_TEMPLATES = {
  // Maintenance alert template
  maintenance_alert: {
    name: 'maintenance_alert',
    language: 'es',
    content: `⚠️ Alerta de Mantenimiento

Equipo: {{equipment}}
Estado: {{status}}
Ubicación: {{location}}

Acción requerida: {{action}}

Responda a este mensaje para más detalles.`,
    variables: ['equipment', 'status', 'location', 'action']
  },
  
  // Diagnostic result template
  diagnostic_result: {
    name: 'diagnostic_result',
    language: 'es',
    content: `🔍 Resultado de Diagnóstico

Su consulta sobre {{equipment}} ha sido analizada.

Causa probable: {{cause}}
Confianza: {{confidence}}%

Recomendación: {{recommendation}}

¿Necesita ayuda adicional? Responda a este mensaje.`,
    variables: ['equipment', 'cause', 'confidence', 'recommendation']
  },
  
  // Scheduled maintenance reminder
  maintenance_reminder: {
    name: 'maintenance_reminder',
    language: 'es',
    content: `📅 Recordatorio de Mantenimiento

Equipo: {{equipment}}
Tipo: {{maintenance_type}}
Fecha programada: {{scheduled_date}}

Por favor confirme la disponibilidad respondiendo:
✅ Confirmar
❌ Reprogramar`,
    variables: ['equipment', 'maintenance_type', 'scheduled_date']
  },
  
  // Welcome message for new users
  welcome: {
    name: 'welcome',
    language: 'es',
    content: `👋 ¡Bienvenido a FactoryLM!

Soy su asistente de mantenimiento con inteligencia artificial.

Puede enviarme:
📝 Descripción de fallas o síntomas
📷 Fotos del equipo
🎤 Notas de voz

Le ayudaré a diagnosticar problemas y encontrar soluciones.

Escriba "ayuda" para ver todos los comandos disponibles.`,
    variables: []
  },
  
  // Help message
  help: {
    name: 'help',
    language: 'es',
    content: `📚 Comandos Disponibles

• Describa un problema → Diagnóstico automático
• Envíe foto → Análisis visual del equipo
• "estado" → Ver equipos pendientes
• "historial" → Últimas intervenciones
• "ayuda" → Este mensaje

También puede enviar notas de voz describiendo el problema.

¿En qué puedo ayudarle?`,
    variables: []
  },
  
  // Error/fallback message
  error: {
    name: 'error',
    language: 'es',
    content: `❌ Error

Lo siento, hubo un problema procesando su solicitud.

{{error_message}}

Por favor intente de nuevo o contacte soporte técnico.`,
    variables: ['error_message']
  }
};

class TemplateManager {
  constructor() {
    this.templates = new Map();
    
    // Load default templates
    for (const [name, template] of Object.entries(DEFAULT_TEMPLATES)) {
      this.templates.set(name, template);
    }
  }
  
  /**
   * Get a template by name
   * @param {string} name - Template name
   * @returns {Object|null} Template object
   */
  get(name) {
    return this.templates.get(name) || null;
  }
  
  /**
   * Register a new template
   * @param {string} name - Template name
   * @param {Object} template - Template definition
   */
  register(name, template) {
    this.templates.set(name, {
      name,
      ...template
    });
  }
  
  /**
   * Render a template with variables
   * @param {string} name - Template name
   * @param {Object} variables - Variable values
   * @returns {string} Rendered template
   */
  render(name, variables = {}) {
    const template = this.get(name);
    if (!template) {
      throw new Error(`Template not found: ${name}`);
    }
    
    let content = template.content;
    
    // Replace variables
    for (const [key, value] of Object.entries(variables)) {
      const placeholder = new RegExp(`{{${key}}}`, 'g');
      content = content.replace(placeholder, value || '');
    }
    
    // Check for unreplaced variables
    const unreplaced = content.match(/{{(\w+)}}/g);
    if (unreplaced) {
      console.warn(`Template ${name} has unreplaced variables:`, unreplaced);
    }
    
    return content;
  }
  
  /**
   * List all template names
   * @returns {string[]}
   */
  list() {
    return Array.from(this.templates.keys());
  }
  
  /**
   * Get template variables
   * @param {string} name - Template name
   * @returns {string[]} Variable names
   */
  getVariables(name) {
    const template = this.get(name);
    return template ? template.variables : [];
  }
}

module.exports = { TemplateManager, DEFAULT_TEMPLATES };
