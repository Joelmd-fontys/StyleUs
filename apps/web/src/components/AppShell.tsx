import { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import Button from './Button';
import { cn } from '../lib/utils';

interface NavItem {
  label: string;
  to: string;
  isActive?: (pathname: string) => boolean;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/', isActive: (path) => path === '/' },
  {
    label: 'Wardrobe',
    to: '/wardrobe',
    isActive: (path) => path.startsWith('/wardrobe') || path.startsWith('/items')
  },
  { label: 'Outfits', to: '/outfits' },
  { label: 'Settings', to: '/settings' }
];

const AppShell = () => {
  const location = useLocation();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  const renderNavItems = (variant: 'desktop' | 'mobile' = 'desktop') => (
    <ul className={cn('flex gap-1', variant === 'mobile' ? 'flex-col p-4' : 'flex-col')}>
      {navItems.map((item) => {
        const isActive = item.isActive ? item.isActive(location.pathname) : location.pathname === item.to;
        return (
          <li key={item.to}>
            <Link
              to={item.to}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => setIsMobileNavOpen(false)}
              className={cn(
                'flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600',
                isActive
                  ? 'bg-neutral-200 text-neutral-900'
                  : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900'
              )}
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );

  return (
    <div className="flex min-h-screen bg-neutral-50">
      <aside className="hidden w-64 flex-shrink-0 border-r border-neutral-200 bg-white/90 p-6 backdrop-blur md:block">
        <Link to="/" className="block text-lg font-semibold text-neutral-900">
          StyleUs
        </Link>
        <p className="mt-1 text-sm text-neutral-500">Your AI fashion companion</p>
        <nav aria-label="Primary navigation" className="mt-8">
          {renderNavItems()}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/80 backdrop-blur">
          <div className="flex items-center justify-between px-4 py-3 md:px-6">
            <div className="md:hidden">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsMobileNavOpen((open) => !open)}
                aria-expanded={isMobileNavOpen}
                aria-controls="mobile-nav"
              >
                Menu
              </Button>
            </div>
            <div className="text-base font-semibold text-neutral-900 md:hidden">
              <Link to="/">StyleUs</Link>
            </div>
            <div className="flex items-center gap-3 text-sm text-neutral-500">
              <span>Signed in as</span>
              <span className="font-medium text-neutral-900">Guest</span>
            </div>
          </div>
          {isMobileNavOpen ? (
            <nav
              id="mobile-nav"
              aria-label="Primary navigation"
              className="border-t border-neutral-200 bg-white md:hidden"
            >
              {renderNavItems('mobile')}
            </nav>
          ) : null}
        </header>

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppShell;
