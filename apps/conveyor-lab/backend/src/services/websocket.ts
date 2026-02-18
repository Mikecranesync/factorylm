/**
 * WebSocket server for real-time telemetry streaming
 *
 * Clients connect to receive:
 * - VFD status updates (every 100ms when running)
 * - Telemetry points during active runs
 * - Run completion events
 */

import { WebSocketServer, WebSocket } from 'ws';
import { Server } from 'http';
import { getConveyor, getConnectionMode, IConveyorController } from './conveyor.js';
import type { VFDStatus, TelemetryPoint } from '../types/index.js';

interface WSMessage {
  type: 'status' | 'telemetry' | 'runComplete' | 'error';
  data: any;
  timestamp: number;
}

class TelemetryWebSocket {
  private wss: WebSocketServer | null = null;
  private clients: Set<WebSocket> = new Set();
  private conveyor: IConveyorController | null = null;

  /**
   * Attach WebSocket server to HTTP server
   */
  attach(server: Server): void {
    this.wss = new WebSocketServer({
      server,
      path: '/ws/telemetry',
    });

    this.conveyor = getConveyor();

    this.wss.on('connection', (ws) => {
      console.log('[WS] Client connected');
      this.clients.add(ws);

      // Send current status immediately
      const conveyor = getConveyor();
      this.send(ws, {
        type: 'status',
        data: {
          ...conveyor.getStatus(),
          connectionMode: getConnectionMode(),
        },
        timestamp: Date.now(),
      });

      ws.on('close', () => {
        console.log('[WS] Client disconnected');
        this.clients.delete(ws);
      });

      ws.on('error', (error) => {
        console.error('[WS] Client error:', error);
        this.clients.delete(ws);
      });

      // Handle incoming messages (for future use)
      ws.on('message', (message) => {
        try {
          const data = JSON.parse(message.toString());
          console.log('[WS] Received:', data);
          // Could add subscription filters here
        } catch (error) {
          console.error('[WS] Invalid message:', error);
        }
      });
    });

    // Subscribe to conveyor events
    this.conveyor.on('status', (status: VFDStatus) => {
      this.broadcast({
        type: 'status',
        data: {
          ...status,
          connectionMode: getConnectionMode(),
        },
        timestamp: Date.now(),
      });
    });

    this.conveyor.on('telemetry', (point: TelemetryPoint) => {
      this.broadcast({
        type: 'telemetry',
        data: point,
        timestamp: Date.now(),
      });
    });

    this.conveyor.on('runComplete', (data: { runId: string; summary: any }) => {
      this.broadcast({
        type: 'runComplete',
        data,
        timestamp: Date.now(),
      });
    });

    console.log(`[WS] WebSocket server attached at /ws/telemetry (mode: ${getConnectionMode()})`);
  }

  /**
   * Send message to a single client
   */
  private send(ws: WebSocket, message: WSMessage): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  /**
   * Broadcast message to all connected clients
   */
  private broadcast(message: WSMessage): void {
    const payload = JSON.stringify(message);
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    }
  }

  /**
   * Get connected client count
   */
  getClientCount(): number {
    return this.clients.size;
  }
}

export const telemetryWebSocket = new TelemetryWebSocket();
