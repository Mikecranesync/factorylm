/**
 * VFD Status Card component
 */

import type { VFDStatus } from '../types';
import { Activity, AlertTriangle, Gauge, Zap, ArrowRight, ArrowLeft } from 'lucide-react';

interface StatusCardProps {
  status: VFDStatus;
}

export function StatusCard({ status }: StatusCardProps) {
  const stateColors: Record<string, string> = {
    stopped: 'bg-gray-500',
    running: 'bg-green-500',
    fault: 'bg-red-500',
    offline: 'bg-yellow-500',
  };

  const stateLabels: Record<string, string> = {
    stopped: 'Stopped',
    running: 'Running',
    fault: 'Fault',
    offline: 'Offline',
  };

  return (
    <div className="bg-tg-secondary rounded-xl p-4 space-y-4">
      {/* Header with state indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${stateColors[status.runState]} animate-pulse`} />
          <span className="font-semibold text-lg">{stateLabels[status.runState]}</span>
        </div>
        <div className="flex items-center gap-1 text-tg-hint text-sm">
          {status.direction === 'forward' ? (
            <ArrowRight className="w-4 h-4" />
          ) : (
            <ArrowLeft className="w-4 h-4" />
          )}
          <span className="capitalize">{status.direction}</span>
        </div>
      </div>

      {/* Fault alert */}
      {status.faultCode > 0 && (
        <div className="flex items-center gap-2 bg-red-100 text-red-700 rounded-lg p-3">
          <AlertTriangle className="w-5 h-5" />
          <span className="text-sm font-medium">
            Fault {status.faultCode}: {status.faultText || 'Unknown error'}
          </span>
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-3">
        <MetricBox
          icon={<Gauge className="w-5 h-5" />}
          label="Command"
          value={`${status.commandHz.toFixed(1)} Hz`}
        />
        <MetricBox
          icon={<Activity className="w-5 h-5" />}
          label="Actual"
          value={`${status.actualHz.toFixed(1)} Hz`}
        />
        <MetricBox
          icon={<Zap className="w-5 h-5" />}
          label="Current"
          value={`${status.motorCurrent.toFixed(2)} A`}
          className="col-span-2"
        />
      </div>
    </div>
  );
}

interface MetricBoxProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  className?: string;
}

function MetricBox({ icon, label, value, className = '' }: MetricBoxProps) {
  return (
    <div className={`bg-tg-bg rounded-lg p-3 ${className}`}>
      <div className="flex items-center gap-2 text-tg-hint mb-1">
        {icon}
        <span className="text-xs uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-xl font-mono font-semibold">{value}</div>
    </div>
  );
}
