/**
 * AlarmBanner - Fixed alarm strip at top
 *
 * ISA-101 compliant alarm banner with:
 * - Flashing for unacknowledged alarms
 * - Solid state after acknowledgment
 * - ACK and RESET buttons
 */

import { AlertTriangle, X } from 'lucide-react';
import { HMIButton } from './HMIButton';

interface AlarmBannerProps {
  faultCode: number;
  faultText: string;
  acknowledged?: boolean;
  timestamp?: number;
  onAcknowledge?: () => void;
  onReset?: () => void;
  onDismiss?: () => void;
}

export function AlarmBanner({
  faultCode,
  faultText,
  acknowledged = false,
  timestamp,
  onAcknowledge,
  onReset,
  onDismiss,
}: AlarmBannerProps) {
  if (faultCode === 0) return null;

  const formattedTime = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  return (
    <div
      className={`
        fixed top-0 left-0 right-0 z-50
        px-4 py-3
        border-b-2 border-hmi-alarm-critical
        flex items-center gap-3
        ${acknowledged
          ? 'bg-gradient-to-r from-[#200000] via-[#300000] to-[#200000]'
          : 'bg-gradient-to-r from-[#2a0000] via-[#500000] to-[#2a0000] animate-alarm-flash'
        }
      `}
    >
      {/* Alarm icon */}
      <AlertTriangle
        className={`w-6 h-6 flex-shrink-0 ${acknowledged ? 'text-hmi-alarm-critical' : 'text-white'}`}
      />

      {/* Alarm details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-white text-sm">
            FAULT {faultCode.toString().padStart(4, '0')}
          </span>
          {timestamp && (
            <span className="text-hmi-text-muted text-xs">
              @ {formattedTime}
            </span>
          )}
        </div>
        <div className="font-mono text-xs text-red-300 uppercase truncate">
          {faultText || 'UNKNOWN FAULT'}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {!acknowledged && onAcknowledge && (
          <HMIButton
            size="sm"
            variant="default"
            onClick={onAcknowledge}
          >
            ACK
          </HMIButton>
        )}
        {onReset && (
          <HMIButton
            size="sm"
            variant="danger"
            onClick={onReset}
          >
            RESET
          </HMIButton>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1 text-hmi-text-muted hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>
    </div>
  );
}
