/**
 * WebSocket hook for real-time telemetry streaming
 */

import { useEffect, useRef, useCallback } from 'react';
import { useConveyorStore } from '../store';
import { getTelegramInitData } from '../utils/telegram';
import type { WSMessage, TelemetryPoint, VFDStatus, Run } from '../types';

const WS_RECONNECT_DELAY = 3000;
const WS_MAX_RECONNECT_ATTEMPTS = 5;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<number | null>(null);

  const {
    setStatus,
    setActiveRun,
    addTelemetryPoint,
    setWsConnected,
  } = useConveyorStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Build WebSocket URL with auth
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const initData = getTelegramInitData();
    const url = `${protocol}//${host}/ws/telemetry${initData ? `?initData=${encodeURIComponent(initData)}` : ''}`;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('[WebSocket] Connected');
      setWsConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);

        switch (message.type) {
          case 'status':
            setStatus(message.data as VFDStatus);
            break;
          case 'telemetry':
            addTelemetryPoint(message.data as TelemetryPoint);
            break;
          case 'runComplete':
            setActiveRun(message.data as Run);
            break;
          case 'error':
            console.error('[WebSocket] Error:', message.data);
            break;
        }
      } catch (err) {
        console.error('[WebSocket] Parse error:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected');
      setWsConnected(false);
      wsRef.current = null;

      // Attempt reconnection
      if (reconnectAttempts.current < WS_MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current++;
        console.log(`[WebSocket] Reconnecting (${reconnectAttempts.current}/${WS_MAX_RECONNECT_ATTEMPTS})...`);
        reconnectTimeout.current = window.setTimeout(connect, WS_RECONNECT_DELAY);
      }
    };

    wsRef.current = ws;
  }, [setStatus, setActiveRun, addTelemetryPoint, setWsConnected]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return {
    connect,
    disconnect,
    isConnected: useConveyorStore((s) => s.wsConnected),
  };
}
