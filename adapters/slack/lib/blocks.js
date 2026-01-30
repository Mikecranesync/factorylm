/**
 * Slack Block Kit Builder
 * Creates rich message layouts for Slack
 * @module adapters/slack/lib/blocks
 */

class BlockBuilder {
  /**
   * Build a diagnostic result message
   * @param {Object} result - Diagnostic result
   * @returns {Array} Block Kit blocks
   */
  diagnostic(result) {
    const blocks = [
      {
        type: 'header',
        text: {
          type: 'plain_text',
          text: '🔍 Resultado de Diagnóstico',
          emoji: true
        }
      },
      {
        type: 'section',
        fields: [
          {
            type: 'mrkdwn',
            text: `*Equipo:*\n${result.equipment || 'No especificado'}`
          },
          {
            type: 'mrkdwn',
            text: `*Confianza:*\n${result.confidence || 'N/A'}%`
          }
        ]
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Causa Probable:*\n${result.cause || 'Análisis en proceso...'}`
        }
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Recomendación:*\n${result.recommendation || 'Contacte soporte técnico'}`
        }
      },
      {
        type: 'divider'
      },
      {
        type: 'context',
        elements: [
          {
            type: 'mrkdwn',
            text: `Analizado por FactoryLM • ${new Date().toLocaleString('es-VE')}`
          }
        ]
      }
    ];
    
    // Add actions if needed
    if (result.showActions !== false) {
      blocks.push({
        type: 'actions',
        elements: [
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '✅ Útil',
              emoji: true
            },
            value: `helpful_${result.id}`,
            action_id: 'feedback_helpful'
          },
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '❌ No útil',
              emoji: true
            },
            value: `not_helpful_${result.id}`,
            action_id: 'feedback_not_helpful'
          },
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '📝 Más detalles',
              emoji: true
            },
            value: `details_${result.id}`,
            action_id: 'request_details'
          }
        ]
      });
    }
    
    return blocks;
  }
  
  /**
   * Build a maintenance alert message
   * @param {Object} alert - Alert data
   * @returns {Array} Block Kit blocks
   */
  alert(alert) {
    const severityEmoji = {
      critical: '🔴',
      high: '🟠',
      medium: '🟡',
      low: '🟢'
    };
    
    const emoji = severityEmoji[alert.severity] || '⚠️';
    
    return [
      {
        type: 'header',
        text: {
          type: 'plain_text',
          text: `${emoji} Alerta de Mantenimiento`,
          emoji: true
        }
      },
      {
        type: 'section',
        fields: [
          {
            type: 'mrkdwn',
            text: `*Equipo:*\n${alert.equipment}`
          },
          {
            type: 'mrkdwn',
            text: `*Severidad:*\n${alert.severity?.toUpperCase() || 'MEDIA'}`
          },
          {
            type: 'mrkdwn',
            text: `*Ubicación:*\n${alert.location || 'No especificada'}`
          },
          {
            type: 'mrkdwn',
            text: `*Estado:*\n${alert.status || 'Pendiente'}`
          }
        ]
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Descripción:*\n${alert.description || 'Sin descripción adicional'}`
        }
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*Acción Requerida:*\n${alert.action || 'Verificar equipo'}`
        }
      },
      {
        type: 'divider'
      },
      {
        type: 'actions',
        elements: [
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '👀 Asignarme',
              emoji: true
            },
            style: 'primary',
            value: `assign_${alert.id}`,
            action_id: 'alert_assign'
          },
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '✅ Resolver',
              emoji: true
            },
            value: `resolve_${alert.id}`,
            action_id: 'alert_resolve'
          },
          {
            type: 'button',
            text: {
              type: 'plain_text',
              text: '📋 Ver historial',
              emoji: true
            },
            value: `history_${alert.equipment}`,
            action_id: 'alert_history'
          }
        ]
      }
    ];
  }
  
  /**
   * Build a simple text section
   * @param {string} text - Markdown text
   * @returns {Object} Section block
   */
  text(text) {
    return {
      type: 'section',
      text: {
        type: 'mrkdwn',
        text
      }
    };
  }
  
  /**
   * Build a header
   * @param {string} text - Header text
   * @returns {Object} Header block
   */
  header(text) {
    return {
      type: 'header',
      text: {
        type: 'plain_text',
        text,
        emoji: true
      }
    };
  }
  
  /**
   * Build a divider
   * @returns {Object} Divider block
   */
  divider() {
    return { type: 'divider' };
  }
  
  /**
   * Build a context (small text)
   * @param {string} text - Context text
   * @returns {Object} Context block
   */
  context(text) {
    return {
      type: 'context',
      elements: [
        {
          type: 'mrkdwn',
          text
        }
      ]
    };
  }
  
  /**
   * Build an image block
   * @param {string} url - Image URL
   * @param {string} altText - Alt text
   * @param {string} title - Optional title
   * @returns {Object} Image block
   */
  image(url, altText, title = null) {
    const block = {
      type: 'image',
      image_url: url,
      alt_text: altText
    };
    
    if (title) {
      block.title = {
        type: 'plain_text',
        text: title
      };
    }
    
    return block;
  }
  
  /**
   * Build equipment status blocks
   * @param {Array} equipment - Array of equipment status
   * @returns {Array} Block Kit blocks
   */
  equipmentStatus(equipment) {
    const blocks = [
      this.header('📊 Estado de Equipos'),
      this.divider()
    ];
    
    for (const item of equipment) {
      const statusEmoji = item.status === 'ok' ? '🟢' : 
                         item.status === 'warning' ? '🟡' : '🔴';
      
      blocks.push({
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `${statusEmoji} *${item.name}*\n${item.description || ''}`
        },
        accessory: {
          type: 'button',
          text: {
            type: 'plain_text',
            text: 'Detalles',
            emoji: true
          },
          value: `details_${item.id}`,
          action_id: 'equipment_details'
        }
      });
    }
    
    blocks.push(
      this.divider(),
      this.context(`Última actualización: ${new Date().toLocaleString('es-VE')}`)
    );
    
    return blocks;
  }
  
  /**
   * Build help message blocks
   * @returns {Array} Block Kit blocks
   */
  help() {
    return [
      this.header('📚 Ayuda - FactoryLM'),
      this.text(`Soy su asistente de mantenimiento con inteligencia artificial. Puedo ayudarle a:

• *Diagnosticar problemas* - Describa los síntomas y le sugeriré causas y soluciones
• *Analizar imágenes* - Envíe fotos del equipo para análisis visual
• *Consultar historial* - Vea intervenciones anteriores en equipos
• *Recibir alertas* - Notificaciones de mantenimiento pendiente`),
      this.divider(),
      this.text(`*Comandos disponibles:*
\`ayuda\` - Este mensaje
\`estado\` - Ver estado de equipos
\`historial [equipo]\` - Ver historial de un equipo
\`buscar [término]\` - Buscar en base de conocimiento`),
      this.divider(),
      this.context('FactoryLM • IA para Mantenimiento Industrial')
    ];
  }
}

module.exports = { BlockBuilder };
