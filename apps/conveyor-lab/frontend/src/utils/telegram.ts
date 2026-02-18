/**
 * Telegram Web App utilities
 *
 * Helpers for working with the Telegram Mini Apps SDK.
 * See: https://core.telegram.org/bots/webapps
 */

import type { TelegramWebApp } from '../types';

/**
 * Get the Telegram WebApp instance
 */
export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp || null;
}

/**
 * Check if running inside Telegram
 */
export function isInsideTelegram(): boolean {
  const tg = getTelegramWebApp();
  return !!tg?.initData;
}

/**
 * Get Telegram init data for API calls
 */
export function getTelegramInitData(): string {
  return getTelegramWebApp()?.initData || '';
}

/**
 * Get current user info
 */
export function getTelegramUser() {
  return getTelegramWebApp()?.initDataUnsafe?.user || null;
}

/**
 * Initialize Telegram WebApp
 */
export function initTelegramWebApp(): void {
  const tg = getTelegramWebApp();
  if (tg) {
    // Notify Telegram that the app is ready
    tg.ready();

    // Expand to full height
    tg.expand();

    console.log('[Telegram] WebApp initialized', {
      colorScheme: tg.colorScheme,
      user: tg.initDataUnsafe?.user?.username,
    });
  } else {
    console.log('[Telegram] Not running inside Telegram');
  }
}

/**
 * Show haptic feedback
 */
export function hapticFeedback(type: 'success' | 'error' | 'warning' | 'light' | 'medium' | 'heavy'): void {
  const tg = getTelegramWebApp();
  if (!tg?.HapticFeedback) return;

  if (['success', 'error', 'warning'].includes(type)) {
    tg.HapticFeedback.notificationOccurred(type as 'success' | 'error' | 'warning');
  } else {
    tg.HapticFeedback.impactOccurred(type as 'light' | 'medium' | 'heavy');
  }
}

/**
 * Show/hide main button
 */
export function configureMainButton(options: {
  text?: string;
  visible?: boolean;
  onClick?: () => void;
}): void {
  const tg = getTelegramWebApp();
  if (!tg?.MainButton) return;

  if (options.text) {
    tg.MainButton.setText(options.text);
  }

  if (options.onClick) {
    tg.MainButton.onClick(options.onClick);
  }

  if (options.visible === true) {
    tg.MainButton.show();
  } else if (options.visible === false) {
    tg.MainButton.hide();
  }
}

/**
 * Show/hide back button
 */
export function configureBackButton(options: {
  visible?: boolean;
  onClick?: () => void;
}): void {
  const tg = getTelegramWebApp();
  if (!tg?.BackButton) return;

  if (options.onClick) {
    tg.BackButton.onClick(options.onClick);
  }

  if (options.visible === true) {
    tg.BackButton.show();
  } else if (options.visible === false) {
    tg.BackButton.hide();
  }
}
