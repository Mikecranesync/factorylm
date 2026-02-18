/**
 * AnalogGauge - SVG analog gauge with needle
 *
 * Industrial-style gauge with:
 * - Configurable min/max range
 * - Alarm zones (red/yellow)
 * - Smooth needle animation
 * - Digital value overlay
 */

import { useMemo } from 'react';

interface AnalogGaugeProps {
  value: number;
  min?: number;
  max?: number;
  label: string;
  unit: string;
  warningThreshold?: number;
  alarmThreshold?: number;
  decimals?: number;
  size?: number;
  className?: string;
}

export function AnalogGauge({
  value,
  min = 0,
  max = 60,
  label,
  unit,
  warningThreshold,
  alarmThreshold,
  decimals = 1,
  size = 160,
  className = '',
}: AnalogGaugeProps) {
  // Calculate needle angle (-135° to 135°, 270° sweep)
  const clampedValue = Math.max(min, Math.min(max, value));
  const percentage = (clampedValue - min) / (max - min);
  const needleAngle = -135 + percentage * 270;

  // Determine value color based on thresholds
  const isAlarm = alarmThreshold !== undefined && value >= alarmThreshold;
  const isWarning = !isAlarm && warningThreshold !== undefined && value >= warningThreshold;
  const valueColor = isAlarm ? '#ff0000' : isWarning ? '#ffd700' : '#ffffff';

  // Generate tick marks
  const ticks = useMemo(() => {
    const tickCount = 7; // Major ticks
    const result = [];
    for (let i = 0; i <= tickCount - 1; i++) {
      const tickValue = min + (i / (tickCount - 1)) * (max - min);
      const tickAngle = -135 + (i / (tickCount - 1)) * 270;
      result.push({ value: tickValue, angle: tickAngle });
    }
    return result;
  }, [min, max]);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.38;

  return (
    <div
      className={`
        bg-hmi-panel border-2 border-hmi-border rounded-lg p-3
        shadow-hmi-panel flex flex-col items-center
        ${className}
      `}
    >
      <svg width={size} height={size * 0.75} viewBox={`0 0 ${size} ${size * 0.75}`}>
        {/* Gauge background arc */}
        <path
          d={describeArc(cx, cy, radius, -135, 135)}
          fill="none"
          stroke="#2a2a2a"
          strokeWidth={size * 0.1}
          strokeLinecap="round"
        />

        {/* Warning zone */}
        {warningThreshold !== undefined && (
          <path
            d={describeArc(
              cx,
              cy,
              radius,
              -135 + ((warningThreshold - min) / (max - min)) * 270,
              alarmThreshold !== undefined
                ? -135 + ((alarmThreshold - min) / (max - min)) * 270
                : 135
            )}
            fill="none"
            stroke="#ffd70044"
            strokeWidth={size * 0.1}
            strokeLinecap="round"
          />
        )}

        {/* Alarm zone */}
        {alarmThreshold !== undefined && (
          <path
            d={describeArc(
              cx,
              cy,
              radius,
              -135 + ((alarmThreshold - min) / (max - min)) * 270,
              135
            )}
            fill="none"
            stroke="#ff000044"
            strokeWidth={size * 0.1}
            strokeLinecap="round"
          />
        )}

        {/* Active value arc */}
        <path
          d={describeArc(cx, cy, radius, -135, needleAngle)}
          fill="none"
          stroke={valueColor}
          strokeWidth={size * 0.06}
          strokeLinecap="round"
          style={{
            filter: `drop-shadow(0 0 4px ${valueColor}66)`,
            transition: 'all 0.3s ease-out',
          }}
        />

        {/* Tick marks */}
        {ticks.map((tick, i) => {
          const innerRadius = radius - size * 0.08;
          const outerRadius = radius + size * 0.08;
          const rad = (tick.angle * Math.PI) / 180;
          const x1 = cx + innerRadius * Math.cos(rad);
          const y1 = cy + innerRadius * Math.sin(rad);
          const x2 = cx + outerRadius * Math.cos(rad);
          const y2 = cy + outerRadius * Math.sin(rad);
          const labelRadius = radius + size * 0.18;
          const lx = cx + labelRadius * Math.cos(rad);
          const ly = cy + labelRadius * Math.sin(rad);

          return (
            <g key={i}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="#666"
                strokeWidth={2}
              />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="#808080"
                fontSize={size * 0.07}
                fontFamily="Consolas, monospace"
              >
                {Math.round(tick.value)}
              </text>
            </g>
          );
        })}

        {/* Center pivot */}
        <circle
          cx={cx}
          cy={cy}
          r={size * 0.06}
          fill="#333"
          stroke="#555"
          strokeWidth={2}
        />

        {/* Needle */}
        <g
          style={{
            transform: `rotate(${needleAngle}deg)`,
            transformOrigin: `${cx}px ${cy}px`,
            transition: 'transform 0.3s ease-out',
          }}
        >
          <polygon
            points={`
              ${cx},${cy - radius + size * 0.05}
              ${cx - size * 0.02},${cy}
              ${cx + size * 0.02},${cy}
            `}
            fill={valueColor}
            style={{ filter: `drop-shadow(0 0 3px ${valueColor}88)` }}
          />
        </g>

        {/* Center cap */}
        <circle
          cx={cx}
          cy={cy}
          r={size * 0.04}
          fill="#444"
          stroke="#666"
          strokeWidth={1}
        />
      </svg>

      {/* Digital value display */}
      <div className="text-center -mt-2">
        <div
          className="font-mono text-2xl font-bold"
          style={{
            color: valueColor,
            textShadow: `0 0 10px ${valueColor}66`,
          }}
        >
          {value.toFixed(decimals)}
        </div>
        <div className="text-hmi-text-label text-xs uppercase tracking-wider">
          {label} ({unit})
        </div>
      </div>
    </div>
  );
}

// Helper to create SVG arc path
function describeArc(cx: number, cy: number, radius: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';

  return [
    'M', start.x, start.y,
    'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y,
  ].join(' ');
}

function polarToCartesian(cx: number, cy: number, radius: number, angleDeg: number) {
  const angleRad = (angleDeg * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRad),
    y: cy + radius * Math.sin(angleRad),
  };
}
