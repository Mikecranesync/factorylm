/**
 * Real-time telemetry trend chart
 */

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { TelemetryPoint } from '../types';

interface TrendChartProps {
  data: TelemetryPoint[];
  height?: number;
}

export function TrendChart({ data, height = 200 }: TrendChartProps) {
  const chartData = useMemo(() => {
    return data.map((point, index) => ({
      index,
      time: new Date(point.timestamp).toLocaleTimeString(),
      commandHz: point.commandHz,
      actualHz: point.actualHz,
      current: point.motorCurrent,
    }));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div
        className="bg-tg-secondary rounded-xl p-4 flex items-center justify-center text-tg-hint"
        style={{ height }}
      >
        No telemetry data yet
      </div>
    );
  }

  return (
    <div className="bg-tg-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold mb-3">Live Telemetry</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--tg-theme-hint-color)" opacity={0.3} />
          <XAxis
            dataKey="index"
            tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            yAxisId="hz"
            domain={[0, 70]}
            tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }}
            tickLine={false}
            axisLine={false}
            width={30}
          />
          <YAxis
            yAxisId="current"
            orientation="right"
            domain={[0, 10]}
            tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }}
            tickLine={false}
            axisLine={false}
            width={30}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--tg-theme-bg-color)',
              border: '1px solid var(--tg-theme-hint-color)',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelFormatter={(index) => chartData[index]?.time || ''}
          />
          <Legend
            wrapperStyle={{ fontSize: '10px' }}
            iconSize={8}
          />
          <Line
            yAxisId="hz"
            type="monotone"
            dataKey="commandHz"
            name="Command Hz"
            stroke="#2481cc"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="hz"
            type="monotone"
            dataKey="actualHz"
            name="Actual Hz"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="current"
            type="monotone"
            dataKey="current"
            name="Current (A)"
            stroke="#f59e0b"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
