/**
 * HMIButton - Physical pushbutton style
 *
 * Industrial 3D button with:
 * - Beveled appearance
 * - Press/release animation
 * - Optional integrated status lamp
 * - Multiple variants (default, danger, success)
 */

import { StatusLamp } from './StatusLamp';

interface HMIButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  variant?: 'default' | 'danger' | 'success';
  showLamp?: boolean;
  lampState?: 'off' | 'on' | 'fault' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'min-w-[60px] min-h-[40px] px-3 py-2 text-xs',
  md: 'min-w-[80px] min-h-[50px] px-4 py-3 text-sm',
  lg: 'min-w-[100px] min-h-[60px] px-6 py-4 text-base',
};

export function HMIButton({
  children,
  onClick,
  disabled = false,
  active = false,
  variant = 'default',
  showLamp = false,
  lampState = 'off',
  size = 'md',
  className = '',
}: HMIButtonProps) {
  const baseStyles = `
    relative
    font-semibold uppercase tracking-wider
    border-2 rounded-md
    cursor-pointer
    transition-all duration-100
    select-none
    flex items-center justify-center gap-2
    ${sizeClasses[size]}
  `;

  const variantStyles = {
    default: active
      ? `
          bg-gradient-to-b from-hmi-running via-[#246624] to-[#1d5a1d]
          border-[#3a9a3a]
          text-white
          shadow-[inset_1px_1px_0_rgba(255,255,255,0.2),inset_-1px_-1px_0_rgba(0,0,0,0.2),0_4px_0_#1a1a1a,0_6px_8px_rgba(0,0,0,0.4),0_0_20px_rgba(45,134,45,0.4)]
        `
      : `
          bg-gradient-to-b from-[#4a4a4a] via-[#3a3a3a] to-[#2a2a2a]
          border-[#555]
          text-hmi-text-normal
          shadow-[inset_1px_1px_0_rgba(255,255,255,0.1),inset_-1px_-1px_0_rgba(0,0,0,0.2),0_4px_0_#1a1a1a,0_6px_8px_rgba(0,0,0,0.4)]
          hover:bg-gradient-to-b hover:from-[#555] hover:via-[#454545] hover:to-[#353535]
        `,
    danger: `
      bg-gradient-to-b from-[#cc3333] via-[#aa2222] to-[#882222]
      border-[#ff4444]
      text-white
      shadow-[inset_1px_1px_0_rgba(255,255,255,0.2),inset_-1px_-1px_0_rgba(0,0,0,0.2),0_4px_0_#1a1a1a,0_6px_8px_rgba(0,0,0,0.4)]
      hover:bg-gradient-to-b hover:from-[#dd4444] hover:via-[#bb3333] hover:to-[#993333]
    `,
    success: `
      bg-gradient-to-b from-hmi-running via-[#246624] to-[#1d5a1d]
      border-[#3a9a3a]
      text-white
      shadow-[inset_1px_1px_0_rgba(255,255,255,0.2),inset_-1px_-1px_0_rgba(0,0,0,0.2),0_4px_0_#1a1a1a,0_6px_8px_rgba(0,0,0,0.4),0_0_15px_rgba(45,134,45,0.3)]
    `,
  };

  const pressedStyles = `
    translate-y-[3px]
    shadow-[inset_1px_1px_0_rgba(0,0,0,0.2),inset_-1px_-1px_0_rgba(255,255,255,0.05),0_1px_0_#1a1a1a,0_2px_4px_rgba(0,0,0,0.3)]
  `;

  const disabledStyles = disabled ? 'opacity-50 cursor-not-allowed !shadow-none' : '';

  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`
        ${baseStyles}
        ${variantStyles[variant]}
        ${disabledStyles}
        active:${pressedStyles}
        ${className}
      `}
      style={{
        // Ensure 3D effect on press
        ...(disabled ? {} : {}),
      }}
    >
      {showLamp && <StatusLamp state={lampState} size="sm" />}
      {children}
    </button>
  );
}
