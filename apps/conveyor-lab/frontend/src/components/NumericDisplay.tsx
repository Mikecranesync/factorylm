/**
 * NumericDisplay - LCD-style numeric readout
 *
 * Industrial seven-segment style display for values.
 * Shows label, value, and optional unit.
 */

interface NumericDisplayProps {
  label: string;
  value: number;
  unit?: string;
  decimals?: number;
  size?: 'sm' | 'md' | 'lg';
  alarm?: boolean;
  warning?: boolean;
  className?: string;
}

const sizeConfig = {
  sm: { value: 'text-lg', label: 'text-[9px]', unit: 'text-[10px]' },
  md: { value: 'text-2xl', label: 'text-[10px]', unit: 'text-xs' },
  lg: { value: 'text-3xl', label: 'text-xs', unit: 'text-sm' },
};

export function NumericDisplay({
  label,
  value,
  unit,
  decimals = 1,
  size = 'md',
  alarm = false,
  warning = false,
  className = '',
}: NumericDisplayProps) {
  const sizes = sizeConfig[size];

  const valueColor = alarm
    ? 'text-hmi-fault'
    : warning
    ? 'text-hmi-warning'
    : 'text-hmi-text-active';

  const glowColor = alarm
    ? 'drop-shadow-[0_0_8px_rgba(255,0,0,0.5)]'
    : warning
    ? 'drop-shadow-[0_0_8px_rgba(255,215,0,0.4)]'
    : 'drop-shadow-[0_0_6px_rgba(255,255,255,0.2)]';

  return (
    <div
      className={`
        bg-[#0a0a0a] border-2 border-hmi-border rounded
        p-2 min-w-[80px]
        shadow-hmi-inset
        ${className}
      `}
    >
      {/* Label */}
      <div className={`${sizes.label} font-semibold uppercase tracking-widest text-hmi-text-label mb-1`}>
        {label}
      </div>

      {/* Value + Unit */}
      <div className="flex items-baseline gap-1">
        <span
          className={`
            ${sizes.value} font-mono font-bold leading-none
            ${valueColor} ${glowColor}
          `}
        >
          {value.toFixed(decimals)}
        </span>
        {unit && (
          <span className={`${sizes.unit} text-hmi-text-muted`}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}
