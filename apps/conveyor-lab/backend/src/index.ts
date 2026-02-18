/**
 * Factory LM — Conveyor Lab Backend
 *
 * Telegram Mini App backend for conveyor control and monitoring.
 *
 * Features:
 * - VFD status and control API
 * - Run management with telemetry logging
 * - WebSocket real-time updates
 * - Cosmos model analysis integration (TODO)
 *
 * Environment variables:
 * - PORT: HTTP port (default: 3001)
 * - TELEGRAM_BOT_TOKEN: For validating Mini App init data
 * - DB_PATH: SQLite database path
 * - NODE_ENV: 'development' or 'production'
 */

import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { initializeDatabase } from './models/database.js';
import statusRoutes from './routes/status.js';
import runsRoutes from './routes/runs.js';
import { telemetryWebSocket } from './services/websocket.js';
import { initializeConveyor, getConnectionMode } from './services/conveyor.js';

const PORT = parseInt(process.env.PORT || '3001', 10);
const isDev = process.env.NODE_ENV !== 'production';

// Initialize Express app
const app = express();

// Middleware
app.use(cors({
  origin: isDev ? '*' : [
    'https://t.me',
    'https://web.telegram.org',
    /\.factorylm\.com$/,
  ],
  credentials: true,
}));
app.use(express.json());

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`[HTTP] ${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
  });
  next();
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'conveyor-lab-backend',
    timestamp: Date.now(),
    wsClients: telemetryWebSocket.getClientCount(),
  });
});

// Mount routes
app.use('/api/status', statusRoutes);
app.use('/api/command', statusRoutes); // Same handlers, /api/command is POST
app.use('/api/runs', runsRoutes);

// Error handler
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('[Error]', err);
  res.status(500).json({
    error: isDev ? err.message : 'Internal server error',
  });
});

// Initialize database
initializeDatabase();

// Async startup
async function start() {
  // Initialize conveyor (auto-detect Factory I/O or use simulator)
  await initializeConveyor();

  // Create HTTP server and attach WebSocket
  const server = createServer(app);
  telemetryWebSocket.attach(server);

  // Start server
  server.listen(PORT, () => {
    const connectionMode = getConnectionMode();
    const modeLabel = connectionMode === 'factoryio' ? 'Factory I/O' : 'Simulator';
    console.log(`
╔══════════════════════════════════════════════════════════╗
║  🏭 Factory LM — Conveyor Lab Backend                    ║
╠══════════════════════════════════════════════════════════╣
║  HTTP:      http://localhost:${PORT}                        ║
║  WebSocket: ws://localhost:${PORT}/ws/telemetry             ║
║  Health:    http://localhost:${PORT}/api/health             ║
║  Mode:      ${isDev ? 'Development' : 'Production'}                               ║
║  Conveyor:  ${modeLabel.padEnd(15)}                        ║
╚══════════════════════════════════════════════════════════╝
    `);
  });

  return server;
}

const server = start().catch(err => {
  console.error('[Server] Failed to start:', err);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[Server] Shutting down...');
  const s = await server;
  if (s && typeof s.close === 'function') {
    s.close(() => {
      console.log('[Server] Goodbye!');
      process.exit(0);
    });
  } else {
    process.exit(0);
  }
});
