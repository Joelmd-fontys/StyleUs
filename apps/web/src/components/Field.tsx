import type { ReactElement, ReactNode } from 'react';
import { cn } from '../lib/utils';

interface FieldProps {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

const Field = ({
  label,
  htmlFor,
  description,
  error,
  required,
  children,
  className
}: FieldProps): ReactElement => (
  <div className={cn('flex flex-col gap-1', className)}>
    <label htmlFor={htmlFor} className="text-sm font-medium text-neutral-700">
      {label}
      {required ? <span className="ml-1 text-danger-500">*</span> : null}
    </label>
    {description ? <p className="text-xs text-neutral-500">{description}</p> : null}
    {children}
    {error ? (
      <p role="alert" className="text-xs font-medium text-danger-500">
        {error}
      </p>
    ) : null}
  </div>
);

export default Field;
