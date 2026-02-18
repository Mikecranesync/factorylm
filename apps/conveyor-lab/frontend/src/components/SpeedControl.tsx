/**
 * Speed Control component with slider and presets
 */

import { useState, useCallback } from 'react';
import { Play, Square, RotateCcw } from 'lucide-react';
import { hapticFeedback } from '../utils/telegram';
import type { VFDStatus, Direction } from '../types';

interface SpeedControlProps {
  status: VFDStatus;
  onStart: () => void;
  onStop: () => void;
  onSetSpeed: (hz: number) => void;
  onSetDirection: (direction: Direction) => void;
  onClearFault: () => void;
  disabled?: boolean;
}

const SPEED_PRESETS = [
  { label: 'Slow', hz: 15 },
  { label: 'Medium', hz: 30 },
  { label: 'Fast', hz: 45 },
  { label: 'Max', hz: 60 },
];

export function SpeedControl({
  status,
  onStart,
  onStop,
  onSetSpeed,
  onSetDirection,
  onClearFault,
  disabled = false,
}: SpeedControlProps) {
  const [localSpeed, setLocalSpeed] = useState(status.commandHz);

  const handleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setLocalSpeed(value);
    hapticFeedback('light');
  }, []);

  const handleSliderRelease = useCallback(() => {
    onSetSpeed(localSpeed);
  }, [localSpeed, onSetSpeed]);

  const handlePresetClick = useCallback((hz: number) => {
    setLocalSpeed(hz);
    onSetSpeed(hz);
    hapticFeedback('medium');
  }, [onSetSpeed]);

  const isRunning = status.runState === 'running';
  const hasFault = status.runState === 'fault';

  return (
    <div className="bg-tg-secondary rounded-xl p-4 space-y-4">
      {/* Direction toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => onSetDirection('forward')}
          disabled={disabled || isRunning}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
            status.direction === 'forward'
              ? 'bg-tg-button text-tg-button'
              : 'bg-tg-bg text-tg-hint'
          } disabled:opacity-50`}
        >
          Forward
        </button>
        <button
          onClick={() => onSetDirection('reverse')}
          disabled={disabled || isRunning}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
            status.direction === 'reverse'
              ? 'bg-tg-button text-tg-button'
              : 'bg-tg-bg text-tg-hint'
          } disabled:opacity-50`}
        >
          Reverse
        </button>
      </div>

      {/* Speed slider */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-tg-hint">Speed</span>
          <span className="font-mono font-semibold">{localSpeed.toFixed(0)} Hz</span>
        </div>
        <input
          type="range"
          min="0"
          max="60"
          step="1"
          value={localSpeed}
          onChange={handleSliderChange}
          onMouseUp={handleSliderRelease}
          onTouchEnd={handleSliderRelease}
          disabled={disabled}
          className="w-full h-2 bg-tg-bg rounded-lg appearance-none cursor-pointer accent-tg-link disabled:opacity-50"
        />
      </div>

      {/* Speed presets */}
      <div className="flex gap-2">
        {SPEED_PRESETS.map((preset) => (
          <button
            key={preset.label}
            onClick={() => handlePresetClick(preset.hz)}
            disabled={disabled}
            className="flex-1 py-2 px-2 text-sm bg-tg-bg rounded-lg text-tg-hint hover:text-tg transition-colors disabled:opacity-50"
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Control buttons */}
      <div className="flex gap-3">
        {hasFault ? (
          <button
            onClick={onClearFault}
            disabled={disabled}
            className="flex-1 flex items-center justify-center gap-2 py-3 bg-red-500 text-white rounded-xl font-semibold disabled:opacity-50"
          >
            <RotateCcw className="w-5 h-5" />
            Clear Fault
          </button>
        ) : isRunning ? (
          <button
            onClick={onStop}
            disabled={disabled}
            className="flex-1 flex items-center justify-center gap-2 py-3 bg-red-500 text-white rounded-xl font-semibold disabled:opacity-50"
          >
            <Square className="w-5 h-5" />
            Stop
          </button>
        ) : (
          <button
            onClick={onStart}
            disabled={disabled}
            className="flex-1 flex items-center justify-center gap-2 py-3 bg-green-500 text-white rounded-xl font-semibold disabled:opacity-50"
          >
            <Play className="w-5 h-5" />
            Start
          </button>
        )}
      </div>
    </div>
  );
}
