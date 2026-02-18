/**
 * Telegram Mini App authentication middleware
 *
 * Validates the init data from Telegram Web Apps SDK.
 * See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 *
 * TODO: Implement full HMAC validation for production:
 *   - Parse initData string from header/body
 *   - Compute HMAC-SHA256 using bot token
 *   - Compare with provided hash
 */

import { Request, Response, NextFunction } from 'express';
import crypto from 'crypto';
import { userRepo } from '../models/repositories.js';
import type { TelegramInitData, User } from '../types/index.js';

// Extend Express Request to include user
declare global {
  namespace Express {
    interface Request {
      telegramUser?: User;
      telegramInitData?: TelegramInitData;
    }
  }
}

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';

/**
 * Parse Telegram init data string into object
 */
function parseInitData(initDataString: string): Record<string, string> {
  const params: Record<string, string> = {};
  const pairs = initDataString.split('&');

  for (const pair of pairs) {
    const [key, value] = pair.split('=');
    params[decodeURIComponent(key)] = decodeURIComponent(value);
  }

  return params;
}

/**
 * Validate Telegram init data hash
 * See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
function validateInitData(initDataString: string, botToken: string): boolean {
  if (!botToken) {
    console.warn('[TelegramAuth] No bot token configured, skipping validation');
    return true; // Skip validation in dev mode
  }

  try {
    const params = parseInitData(initDataString);
    const hash = params.hash;
    delete params.hash;

    // Sort and create data check string
    const dataCheckString = Object.keys(params)
      .sort()
      .map((key) => `${key}=${params[key]}`)
      .join('\n');

    // Create secret key
    const secretKey = crypto.createHmac('sha256', 'WebAppData').update(botToken).digest();

    // Calculate hash
    const calculatedHash = crypto.createHmac('sha256', secretKey).update(dataCheckString).digest('hex');

    return calculatedHash === hash;
  } catch (error) {
    console.error('[TelegramAuth] Validation error:', error);
    return false;
  }
}

/**
 * Middleware to authenticate Telegram Mini App requests
 */
export function telegramAuth(required = true) {
  return async (req: Request, res: Response, next: NextFunction) => {
    // Get init data from header or body
    const initDataString =
      req.headers['x-telegram-init-data'] as string ||
      req.body?.telegramInitData ||
      req.query?.initData as string;

    if (!initDataString) {
      if (required) {
        return res.status(401).json({ error: 'Telegram init data required' });
      }
      return next();
    }

    // Validate hash (skip in dev if no token)
    if (BOT_TOKEN && !validateInitData(initDataString, BOT_TOKEN)) {
      return res.status(401).json({ error: 'Invalid Telegram init data' });
    }

    // Parse init data
    const params = parseInitData(initDataString);

    try {
      const userData = params.user ? JSON.parse(params.user) : null;

      if (userData?.id) {
        const initData: TelegramInitData = {
          queryId: params.query_id,
          user: {
            id: userData.id,
            firstName: userData.first_name,
            lastName: userData.last_name,
            username: userData.username,
            languageCode: userData.language_code,
          },
          authDate: parseInt(params.auth_date, 10),
          hash: params.hash,
        };

        req.telegramInitData = initData;

        // Upsert user in database
        req.telegramUser = userRepo.upsert(userData.id, {
          username: userData.username,
          firstName: userData.first_name,
          lastName: userData.last_name,
        });
      }
    } catch (error) {
      console.error('[TelegramAuth] Error parsing user data:', error);
    }

    if (required && !req.telegramUser) {
      return res.status(401).json({ error: 'Valid Telegram user required' });
    }

    next();
  };
}

/**
 * Dev-only middleware that creates a mock user
 */
export function devAuth(req: Request, res: Response, next: NextFunction) {
  if (process.env.NODE_ENV === 'development' && !req.telegramUser) {
    // Create a dev user
    req.telegramUser = userRepo.upsert(123456789, {
      username: 'dev_user',
      firstName: 'Dev',
      lastName: 'User',
    });
  }
  next();
}
