/**
 * StatusLamp - Industrial LED indicator
 *
 * ISA-101 compliant status lamp with glow effects.
 * States: OFF (gray), ON (green), FAULT (red pulsing), WARNING (yellow)
 */

interface StatusLampProps {
  state: 'off' | 'on' | 'fault' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  className?: string;
}

const sizeClasses = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
};

export function StatusLamp({ state, size = 'md', label, className = '' }: StatusLampProps) {
  const baseClasses = `
    rounded-full border-2 border-hmi-border
    transition-all duration-200
    ${sizeClasses[size]}
  `;

  const stateClasses = {
    off: 'bg-gradient-radial from-gray-500 via-hmi-off to-gray-900',
    on: 'bg-gradient-to-br from-green-300 via-hmi-running to-green-900 shadow-hmi-lamp-on',
    fault: 'bg-gradient-to-br from-red-400 via-hmi-fault to-red-900 shadow-hmi-lamp-fault animate-lamp-pulse',
    warning: 'bg-gradient-to-br from-yellow-200 via-hmi-warning to-yellow-700',
  };

  return (
    <div className={`flex flex-col items-center gap-1 ${className}`}>
      <div
        className={`${baseClasses} ${stateClasses[state]}`}
        style={{
          background: state === 'off'
            ? 'radial-gradient(circle at 30% 30%, #666 0%, #4a4a4a 60%, #222 100%)'
            : state === 'on'
            ? 'radial-gradient(circle at 30% 30%, #7fff7f 0%, #2d862d 50%, #1a5a1a 100%)'
            : state === 'fault'
            ? 'radial-gradient(circle at 30% 30%, #ff6666 0%, #ff0000 50%, #990000 100%)'
            : 'radial-gradient(circle at 30% 30%, #ffff99 0%, #ffd700 50%, #cc9900 100%)',
          boxShadow: state === 'on'
            ? '0 0 15px rgba(45,134,45,0.6), 0 0 30px rgba(45,134,45,0.6), inset 1px 1px 3px rgba(255,255,255,0.3)'
            : state === 'fault'
            ? '0 0 15px rgba(255,0,0,0.6), 0 0 30px rgba(255,0,0,0.6), inset 1px 1px 3px rgba(255,255,255,0.3)'
            : state === 'warning'
            ? '0 0 15px rgba(255,215,0,0.5), inset 1px 1px 3px rgba(255,255,255,0.3)'
            : 'inset 1px 1px 3px rgba(255,255,255,0.1), inset -1px -1px 3px rgba(0,0,0,0.3)',
        }}
      />
      {label && (
        <span className="text-[10px] font-semibold uppercase tracking-wider text-hmi-text-label">
          {label}
        </span>
      )}
    </div>
  );
}
