import { forwardRef } from 'react';
import { cn } from '../lib/utils';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'md' | 'sm';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-accent-600 text-white shadow-sm hover:bg-accent-700 focus-visible:outline-accent-600',
  secondary:
    'bg-neutral-100 text-neutral-900 shadow-sm hover:bg-neutral-200 focus-visible:outline-neutral-400',
  ghost:
    'text-neutral-700 hover:bg-neutral-100 focus-visible:outline-neutral-400',
  danger:
    'bg-danger-500 text-white shadow-sm hover:bg-danger-600 focus-visible:outline-danger-500'
};

const sizeStyles: Record<ButtonSize, string> = {
  md: 'px-4 py-2 text-sm font-medium',
  sm: 'px-3 py-1.5 text-xs font-medium'
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex items-center justify-center rounded-xl transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    />
  )
);

Button.displayName = 'Button';

export const buttonClasses = (
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className?: string
): string =>
  cn(
    'inline-flex items-center justify-center rounded-xl transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
    variantStyles[variant],
    sizeStyles[size],
    className
  );

export default Button;
