/**
 * Main Status Page - VFD control and live telemetry
 */

import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus, History, Wifi, WifiOff } from 'lucide-react';
import { StatusCard } from '../components/StatusCard';
import { SpeedControl } from '../components/SpeedControl';
import { TrendChart } from '../components/TrendChart';
import { useStatus } from '../hooks/useStatus';
import { useWebSocket } from '../hooks/useWebSocket';
import { useConveyorStore } from '../store';
import { initTelegramWebApp, configureMainButton } from '../utils/telegram';

export function StatusPage() {
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

  // Initialize Telegram WebApp
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  // Configure main button for new run
  useEffect(() => {
    configureMainButton({
      text: 'New Run',
      visible: !activeRun,
      onClick: () => {
        window.location.href = '/new-run';
      },
    });

    return () => {
      configureMainButton({ visible: false });
    };
  }, [activeRun]);

  if (isLoading && !status) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-tg-link border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 pb-20 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Conveyor Lab</h1>
        <div className="flex items-center gap-3">
          {isConnected ? (
            <Wifi className="w-5 h-5 text-green-500" />
          ) : (
            <WifiOff className="w-5 h-5 text-tg-hint" />
          )}
          <Link
            to="/runs"
            className="flex items-center gap-1 text-tg-link text-sm"
          >
            <History className="w-4 h-4" />
            History
          </Link>
        </div>
      </div>

      {/* Active run banner */}
      {activeRun && (
        <Link
          to={`/runs/${activeRun.id}`}
          className="block bg-green-100 text-green-800 rounded-xl p-3"
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Active Run</div>
              <div className="text-xs opacity-75">{activeRun.config.name}</div>
            </div>
            <div className="text-xs bg-green-500 text-white px-2 py-1 rounded-full">
              Live
            </div>
          </div>
        </Link>
      )}

      {/* Status card */}
      {status && <StatusCard status={status} />}

      {/* Speed control */}
      {status && (
        <SpeedControl
          status={status}
          onStart={start}
          onStop={stop}
          onSetSpeed={setSpeed}
          onSetDirection={setDirection}
          onClearFault={clearFault}
          disabled={isCommandPending}
        />
      )}

      {/* Telemetry chart */}
      <TrendChart data={telemetryBuffer} />

      {/* Quick action */}
      {!activeRun && (
        <Link
          to="/new-run"
          className="fixed bottom-6 right-6 w-14 h-14 bg-tg-button text-tg-button rounded-full shadow-lg flex items-center justify-center"
        >
          <Plus className="w-6 h-6" />
        </Link>
      )}
    </div>
  );
}
