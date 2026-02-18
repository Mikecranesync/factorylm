/**
 * Runs Routes
 *
 * POST /api/runs           - Create and start a run
 * GET  /api/runs           - List runs
 * GET  /api/runs/:id       - Get run detail
 * POST /api/runs/:id/feedback     - Add feedback
 * POST /api/runs/:id/model-analysis - Add Cosmos analysis
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import {
  runRepo,
  telemetryRepo,
  modelAnalysisRepo,
  feedbackRepo,
  mediaRepo,
} from '../models/repositories.js';
import { conveyorSimulator } from '../services/conveyor-simulator.js';
import { telegramAuth, devAuth } from '../middleware/telegram-auth.js';
import type { RunConfig } from '../types/index.js';

const router = Router();

// Apply auth middleware
router.use(telegramAuth(false)); // Optional auth
router.use(devAuth); // Dev fallback

// Validation schemas
const createRunSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(500).optional(),
  direction: z.enum(['forward', 'reverse']).default('forward'),
  targetSpeedHz: z.number().min(0).max(60).default(30),
  maxDurationSeconds: z.number().min(10).max(3600).default(300),
  tags: z.array(z.string()).default([]),
});

const feedbackSchema = z.object({
  modelAnalysisId: z.string().optional(),
  actionTaken: z.enum(['followed', 'partial', 'ignored']),
  rating: z.number().min(1).max(5),
  tags: z.array(z.string()).default([]),
  notes: z.string().max(1000).optional(),
});

const modelAnalysisSchema = z.object({
  cosmosModel: z.string().default('nvidia/cosmos-reason2-2b'),
  summary: z.string(),
  suggestedActions: z.array(z.string()),
  confidence: z.number().min(0).max(1),
  reasoning: z.string().optional(),
});

/**
 * POST /api/runs
 * Create and start a new run
 */
router.post('/', (req: Request, res: Response) => {
  try {
    const parsed = createRunSchema.safeParse(req.body);

    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid run configuration',
        details: parsed.error.errors,
      });
    }

    const userId = req.telegramUser?.id;
    if (!userId) {
      return res.status(401).json({ error: 'User authentication required' });
    }

    const config: RunConfig = parsed.data;

    // Create run in database
    const run = runRepo.create(userId, config);

    // Start the conveyor with this run
    const status = conveyorSimulator.start(run.id);

    // Update run status
    runRepo.start(run.id);

    res.status(201).json({
      run: runRepo.findById(run.id),
      status,
    });
  } catch (error) {
    console.error('[Runs] Create error:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to create run',
    });
  }
});

/**
 * GET /api/runs
 * List runs with optional filters
 */
router.get('/', (req: Request, res: Response) => {
  try {
    const limit = Math.min(parseInt(req.query.limit as string) || 50, 100);
    const offset = parseInt(req.query.offset as string) || 0;
    const tags = req.query.tags ? (req.query.tags as string).split(',') : undefined;
    const dateFrom = req.query.dateFrom ? parseInt(req.query.dateFrom as string) : undefined;
    const dateTo = req.query.dateTo ? parseInt(req.query.dateTo as string) : undefined;

    const runs = runRepo.findAll(limit, offset, { tags, dateFrom, dateTo });

    res.json({
      runs,
      pagination: {
        limit,
        offset,
        hasMore: runs.length === limit,
      },
    });
  } catch (error) {
    console.error('[Runs] List error:', error);
    res.status(500).json({ error: 'Failed to list runs' });
  }
});

/**
 * GET /api/runs/:id
 * Get run detail with telemetry, analysis, and feedback
 */
router.get('/:id', (req: Request, res: Response) => {
  try {
    const run = runRepo.findById(req.params.id);

    if (!run) {
      return res.status(404).json({ error: 'Run not found' });
    }

    // Get related data
    const telemetry = telemetryRepo.findByRunId(run.id);
    const modelAnalysis = modelAnalysisRepo.findByRunId(run.id);
    const feedback = feedbackRepo.findByRunId(run.id);
    const media = mediaRepo.findByRunId(run.id);

    res.json({
      run,
      telemetry,
      modelAnalysis,
      feedback,
      media,
    });
  } catch (error) {
    console.error('[Runs] Detail error:', error);
    res.status(500).json({ error: 'Failed to get run details' });
  }
});

/**
 * POST /api/runs/:id/feedback
 * Add feedback to a run
 */
router.post('/:id/feedback', (req: Request, res: Response) => {
  try {
    const run = runRepo.findById(req.params.id);
    if (!run) {
      return res.status(404).json({ error: 'Run not found' });
    }

    const parsed = feedbackSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid feedback',
        details: parsed.error.errors,
      });
    }

    const userId = req.telegramUser?.id;
    if (!userId) {
      return res.status(401).json({ error: 'User authentication required' });
    }

    const feedback = feedbackRepo.create({
      runId: run.id,
      userId,
      ...parsed.data,
    });

    res.status(201).json({ feedback });
  } catch (error) {
    console.error('[Runs] Feedback error:', error);
    res.status(500).json({ error: 'Failed to add feedback' });
  }
});

/**
 * POST /api/runs/:id/model-analysis
 * Add Cosmos model analysis to a run
 *
 * TODO: In production, this endpoint should:
 *   1. Accept video URL or telemetry data
 *   2. Call Cosmos Reason 2 API for analysis
 *   3. Store and return the result
 *
 * For now, this is a stub that accepts pre-computed analysis.
 */
router.post('/:id/model-analysis', (req: Request, res: Response) => {
  try {
    const run = runRepo.findById(req.params.id);
    if (!run) {
      return res.status(404).json({ error: 'Run not found' });
    }

    const parsed = modelAnalysisSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: 'Invalid model analysis',
        details: parsed.error.errors,
      });
    }

    const analysis = modelAnalysisRepo.create({
      runId: run.id,
      ...parsed.data,
    });

    res.status(201).json({ analysis });
  } catch (error) {
    console.error('[Runs] Model analysis error:', error);
    res.status(500).json({ error: 'Failed to add model analysis' });
  }
});

/**
 * POST /api/runs/:id/stop
 * Stop an active run
 */
router.post('/:id/stop', (req: Request, res: Response) => {
  try {
    const run = runRepo.findById(req.params.id);
    if (!run) {
      return res.status(404).json({ error: 'Run not found' });
    }

    if (run.status !== 'running') {
      return res.status(400).json({ error: 'Run is not active' });
    }

    const status = conveyorSimulator.stop();

    res.json({
      run: runRepo.findById(run.id),
      status,
    });
  } catch (error) {
    console.error('[Runs] Stop error:', error);
    res.status(500).json({ error: 'Failed to stop run' });
  }
});

export default router;
