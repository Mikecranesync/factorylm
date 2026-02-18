/**
 * VFD Status and Control Routes
 *
 * GET  /api/status  - Get current VFD status
 * POST /api/command - Send command to VFD
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { conveyorSimulator } from '../services/conveyor-simulator.js';
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
    const status = conveyorSimulator.getStatus();
    res.json(status);
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
router.post('/', (req: Request, res: Response) => {
  try {
    const parsed = commandSchema.safeParse(req.body);

    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid command',
        details: parsed.error.errors,
      });
    }

    const { action, value, runId } = parsed.data;
    let status;

    switch (action) {
      case 'start':
        status = conveyorSimulator.start(runId);
        break;

      case 'stop':
        status = conveyorSimulator.stop();
        break;

      case 'set_speed':
        if (typeof value !== 'number') {
          return res.status(400).json({ error: 'Speed value must be a number' });
        }
        status = conveyorSimulator.setSpeed(value);
        break;

      case 'set_direction':
        if (value !== 'forward' && value !== 'reverse') {
          return res.status(400).json({ error: 'Direction must be "forward" or "reverse"' });
        }
        status = conveyorSimulator.setDirection(value as Direction);
        break;

      case 'clear_fault':
        status = conveyorSimulator.clearFault();
        break;

      case 'inject_fault':
        // Dev/test only
        if (typeof value !== 'number') {
          return res.status(400).json({ error: 'Fault code must be a number' });
        }
        status = conveyorSimulator.injectFault(value);
        break;

      default:
        return res.status(400).json({ error: `Unknown action: ${action}` });
    }

    res.json({
      success: true,
      status,
    });
  } catch (error) {
    console.error('[Command] Error:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Command failed',
    });
  }
});

export default router;
