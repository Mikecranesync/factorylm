/**
 * VFD Status and Control Routes
 *
 * GET  /api/status  - Get current VFD status
 * POST /api/command - Send command to VFD
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { getConveyor, getConnectionMode } from '../services/conveyor.js';
import type { VFDCommand, Direction } from '../types/index.js';

const router = Router();

// Command schema validation
const commandSchema = z.object({
  action: z.enum(['start', 'stop', 'set_speed', 'set_direction', 'clear_fault', 'inject_fault']),
  value: z.union([z.number(), z.enum(['forward', 'reverse'])]).optional(),
  runId: z.string().optional(),
});

/**
 * GET /api/status
 * Returns current VFD/conveyor status
 */
router.get('/', (req: Request, res: Response) => {
  try {
    const conveyor = getConveyor();
    const status = conveyor.getStatus();
    res.json({
      ...status,
      connectionMode: getConnectionMode(),
    });
  } catch (error) {
    console.error('[Status] Error:', error);
    res.status(500).json({ error: 'Failed to get status' });
  }
});

/**
 * POST /api/command
 * Send a command to the VFD
 *
 * Body: { action: "start"|"stop"|"set_speed"|"set_direction", value?: number|string, runId?: string }
 */
router.post('/', async (req: Request, res: Response) => {
  try {
    const parsed = commandSchema.safeParse(req.body);

    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid command',
        details: parsed.error.errors,
      });
    }

    const { action, value, runId } = parsed.data;
    const conveyor = getConveyor();
    let status;

    switch (action) {
      case 'start':
        status = await conveyor.start(runId);
        break;

      case 'stop':
        status = await conveyor.stop();
        break;

      case 'set_speed':
        if (typeof value !== 'number') {
          return res.status(400).json({ error: 'Speed value must be a number' });
        }
        status = await conveyor.setSpeed(value);
        break;

      case 'set_direction':
        if (value !== 'forward' && value !== 'reverse') {
          return res.status(400).json({ error: 'Direction must be "forward" or "reverse"' });
        }
        status = await conveyor.setDirection(value as Direction);
        break;

      case 'clear_fault':
        status = await conveyor.clearFault();
        break;

      case 'inject_fault':
        // Dev/test only
        if (typeof value !== 'number') {
          return res.status(400).json({ error: 'Fault code must be a number' });
        }
        status = conveyor.injectFault(value);
        break;

      default:
        return res.status(400).json({ error: `Unknown action: ${action}` });
    }

    res.json({
      success: true,
      status,
      connectionMode: getConnectionMode(),
    });
  } catch (error) {
    console.error('[Command] Error:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Command failed',
    });
  }
});

export default router;
