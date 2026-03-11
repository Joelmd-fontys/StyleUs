import { forwardRef } from 'react';
import { cn } from '../lib/utils';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, title, description, actions, children, ...props }, ref) => (
    <section
      ref={ref}
      className={cn('rounded-xl border border-neutral-200 bg-white/90 shadow-sm backdrop-blur-sm', className)}
      {...props}
    >
      {(title || description || actions) && (
        <header className="flex flex-col gap-2 border-b border-neutral-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            {title ? <h2 className="text-base font-semibold text-neutral-900">{title}</h2> : null}
            {description ? <p className="text-sm text-neutral-500">{description}</p> : null}
          </div>
          {actions ? <div className="flex-shrink-0">{actions}</div> : null}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  )
);

Card.displayName = 'Card';

export default Card;
