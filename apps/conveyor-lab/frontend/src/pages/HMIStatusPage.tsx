/**
 * HMIStatusPage - Industrial HMI layout
 *
 * Main control panel with:
 * - Alarm banner (if fault)
 * - RUN/STOP buttons with status lamps
 * - Speed and Current gauges
 * - Digital readouts
 * - Direction and speed controls
 * - Mini telemetry chart
 * - PTT voice interface
 */

import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { History, Wifi, WifiOff, ArrowLeft, ArrowRight } from 'lucide-react';
import { AlarmBanner } from '../components/AlarmBanner';
import { StatusLamp } from '../components/StatusLamp';
import { NumericDisplay } from '../components/NumericDisplay';
import { AnalogGauge } from '../components/AnalogGauge';
import { HMIButton } from '../components/HMIButton';
import { PTTButton } from '../components/PTTButton';
import { TrendChart } from '../components/TrendChart';
import { useStatus } from '../hooks/useStatus';
import { useWebSocket } from '../hooks/useWebSocket';
import { useConveyorStore } from '../store';
import { initTelegramWebApp, hapticFeedback } from '../utils/telegram';

// Import HMI theme
import '../styles/hmi-theme.css';

export function HMIStatusPage() {
  const {
    status,
    isLoading,
    isCommandPending,
    start,
    stop,
    setSpeed,
    setDirection,
    clearFault,
  } = useStatus();

  const { isConnected } = useWebSocket();
  const telemetryBuffer = useConveyorStore((s) => s.telemetryBuffer);
  const activeRun = useConveyorStore((s) => s.activeRun);

  const [alarmAcknowledged, setAlarmAcknowledged] = useState(false);
  const [localSpeed, setLocalSpeed] = useState(30);

  // Initialize Telegram WebApp
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  // Sync speed with status
  useEffect(() => {
    if (status) {
      setLocalSpeed(status.commandHz);
    }
  }, [status?.commandHz]);

  // Reset alarm acknowledgment on new fault
  useEffect(() => {
    if (status?.faultCode && status.faultCode > 0) {
      setAlarmAcknowledged(false);
    }
  }, [status?.faultCode]);

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalSpeed(parseFloat(e.target.value));
    hapticFeedback('light');
  };

  const handleSpeedRelease = () => {
    setSpeed(localSpeed);
  };

  const handleVoiceCommand = useCallback(async (transcript: string): Promise<string> => {
    // TODO: Route to Clawdbot via Telegram
    console.log('[Voice] Transcript:', transcript);

    // For now, return mock response
    // This will be replaced with actual Telegram bot integration
    return `Received command: "${transcript}". AI routing coming soon.`;
  }, []);

  if (isLoading && !status) {
    return (
      <div className="min-h-screen bg-hmi-bg flex items-center justify-center">
        <div className="animate-spin w-10 h-10 border-4 border-hmi-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  const isRunning = status?.runState === 'running';
  const isFaulted = status?.runState === 'fault';
  const isStopped = status?.runState === 'stopped';

  return (
    <div className="min-h-screen bg-hmi-bg text-hmi-text-normal font-hmi">
      {/* Alarm Banner */}
      {status && status.faultCode > 0 && (
        <AlarmBanner
          faultCode={status.faultCode}
          faultText={status.faultText}
          acknowledged={alarmAcknowledged}
          timestamp={status.timestamp}
          onAcknowledge={() => {
            setAlarmAcknowledged(true);
            hapticFeedback('medium');
          }}
          onReset={clearFault}
        />
      )}

      {/* Main content with top padding for alarm banner */}
      <div className={`p-4 space-y-4 ${status && status.faultCode > 0 ? 'pt-20' : ''}`}>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-hmi-text-active uppercase tracking-wider">
              Conveyor Lab
            </h1>
            <div className={`flex items-center gap-1 text-xs ${isConnected ? 'text-hmi-running' : 'text-hmi-text-muted'}`}>
              {isConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
              <span>{isConnected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
          </div>
          <Link
            to="/runs"
            className="flex items-center gap-1 text-hmi-accent text-sm hover:text-hmi-text-active transition-colors"
          >
            <History className="w-4 h-4" />
            HISTORY
          </Link>
        </div>

        {/* Control buttons row */}
        <div className="flex gap-3">
          <HMIButton
            onClick={start}
            disabled={isCommandPending || isRunning}
            active={isRunning}
            variant="success"
            showLamp
            lampState={isRunning ? 'on' : 'off'}
            size="lg"
            className="flex-1"
          >
            RUN
          </HMIButton>
          <HMIButton
            onClick={stop}
            disabled={isCommandPending || isStopped}
            variant={isRunning ? 'danger' : 'default'}
            showLamp
            lampState={isStopped ? 'on' : 'off'}
            size="lg"
            className="flex-1"
          >
            STOP
          </HMIButton>
        </div>

        {/* Status indicator */}
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-3 flex items-center justify-center gap-4">
          <StatusLamp
            state={isFaulted ? 'fault' : isRunning ? 'on' : 'off'}
            size="lg"
          />
          <div className="text-center">
            <div className="text-xs text-hmi-text-label uppercase">STATUS</div>
            <div className={`text-lg font-bold uppercase ${
              isFaulted ? 'text-hmi-fault' : isRunning ? 'text-hmi-running' : 'text-hmi-text-muted'
            }`}>
              {status?.runState || 'OFFLINE'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-hmi-text-label uppercase">DIRECTION</div>
            <div className="flex items-center gap-1 text-lg font-bold text-hmi-text-active">
              {status?.direction === 'reverse' ? (
                <ArrowLeft className="w-5 h-5" />
              ) : (
                <ArrowRight className="w-5 h-5" />
              )}
              {status?.direction?.toUpperCase() || '--'}
            </div>
          </div>
        </div>

        {/* Gauges row */}
        <div className="grid grid-cols-2 gap-3">
          <AnalogGauge
            value={status?.actualHz || 0}
            min={0}
            max={60}
            label="Speed"
            unit="Hz"
            warningThreshold={50}
            alarmThreshold={58}
            size={140}
          />
          <AnalogGauge
            value={status?.motorCurrent || 0}
            min={0}
            max={10}
            label="Current"
            unit="A"
            warningThreshold={6}
            alarmThreshold={8}
            decimals={2}
            size={140}
          />
        </div>

        {/* Digital displays */}
        <div className="grid grid-cols-3 gap-2">
          <NumericDisplay
            label="CMD"
            value={status?.commandHz || 0}
            unit="Hz"
          />
          <NumericDisplay
            label="ACT"
            value={status?.actualHz || 0}
            unit="Hz"
            warning={!!(status && Math.abs(status.commandHz - status.actualHz) > 5)}
          />
          <NumericDisplay
            label="AMPS"
            value={status?.motorCurrent || 0}
            unit="A"
            decimals={2}
            alarm={!!(status && status.motorCurrent > 8)}
            warning={!!(status && status.motorCurrent > 6)}
          />
        </div>

        {/* Direction buttons */}
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-3">
          <div className="text-xs text-hmi-text-label uppercase mb-2">DIRECTION</div>
          <div className="flex gap-2">
            <HMIButton
              onClick={() => setDirection('reverse')}
              disabled={isCommandPending || isRunning}
              active={status?.direction === 'reverse'}
              className="flex-1"
            >
              <ArrowLeft className="w-4 h-4" />
              REV
            </HMIButton>
            <HMIButton
              onClick={() => setDirection('forward')}
              disabled={isCommandPending || isRunning}
              active={status?.direction === 'forward'}
              className="flex-1"
            >
              FWD
              <ArrowRight className="w-4 h-4" />
            </HMIButton>
          </div>
        </div>

        {/* Speed slider */}
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-3">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-hmi-text-label uppercase">SPEED SETPOINT</span>
            <span className="font-mono text-hmi-text-active text-lg">{localSpeed.toFixed(0)} Hz</span>
          </div>
          <input
            type="range"
            min="5"
            max="60"
            step="1"
            value={localSpeed}
            onChange={handleSpeedChange}
            onMouseUp={handleSpeedRelease}
            onTouchEnd={handleSpeedRelease}
            disabled={isCommandPending}
            className="hmi-slider w-full"
          />
          <div className="flex justify-between text-xs text-hmi-text-muted mt-1">
            <span>5</span>
            <span>60</span>
          </div>
        </div>

        {/* Mini trend chart */}
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-3">
          <div className="text-xs text-hmi-text-label uppercase mb-2">TELEMETRY TREND</div>
          <TrendChart data={telemetryBuffer} height={120} />
        </div>

        {/* Divider */}
        <div className="h-px bg-gradient-to-r from-transparent via-hmi-border to-transparent" />

        {/* PTT Voice Interface */}
        <div className="bg-hmi-panel border border-hmi-border rounded-lg p-4">
          <div className="text-xs text-hmi-text-label uppercase text-center mb-3">
            TALK TO MACHINE
          </div>
          <PTTButton
            onTranscript={handleVoiceCommand}
            disabled={isCommandPending}
          />
        </div>

        {/* Active run banner */}
        {activeRun && (
          <Link
            to={`/runs/${activeRun.id}`}
            className="block bg-hmi-running/20 border border-hmi-running/50 rounded-lg p-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-hmi-running">Active Run</div>
                <div className="text-xs text-hmi-text-muted">{activeRun.config.name}</div>
              </div>
              <StatusLamp state="on" size="md" />
            </div>
          </Link>
        )}
      </div>
    </div>
  );
}
