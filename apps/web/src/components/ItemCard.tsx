import { memo, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { WardrobeItem } from '../domain/types';
import { cn } from '../lib/utils';
import { resolveMediaUrl } from '../lib/media';

interface ItemCardProps {
  item: WardrobeItem;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
}

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });

const ItemCardComponent = ({
  item,
  isSelected = false,
  onSelect,
  onEdit,
  onDelete
}: ItemCardProps) => {
  const imageSrc = resolveMediaUrl(item.thumbUrl, item.imageUrl);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', handleClick);
    window.addEventListener('keydown', handleKey);
    return () => {
      window.removeEventListener('mousedown', handleClick);
      window.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  const formatActionsLabel = useMemo(() => {
    return item.brand ? `Actions for ${item.brand}` : 'Item actions';
  }, [item.brand]);

  const handleActivate = () => {
    onSelect?.(item.id);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleActivate();
    }
  };

  return (
    <div
      role="link"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={handleKeyDown}
      className={cn(
        'group relative flex h-full w-full cursor-pointer flex-col overflow-hidden rounded-2xl border bg-white text-left shadow-sm transition-all hover:-translate-y-1 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600',
        isSelected
          ? 'border-accent-600/80 ring-2 ring-accent-600/30'
          : 'border-neutral-200/80'
      )}
      aria-current={isSelected ? 'page' : undefined}
    >
      <div className="absolute right-3 top-3" ref={menuRef} onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="rounded-full bg-white/90 p-1.5 text-neutral-500 shadow-sm transition hover:text-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={formatActionsLabel}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="sr-only">Open item actions</span>
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="text-current"
          >
            <circle cx="12" cy="5" r="1.5" fill="currentColor" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
            <circle cx="12" cy="19" r="1.5" fill="currentColor" />
          </svg>
        </button>
        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-12 z-10 w-40 rounded-xl border border-neutral-200 bg-white p-1.5 text-sm text-neutral-700 shadow-lg"
          >
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onSelect?.(item.id);
              }}
            >
              View
              <span aria-hidden>&rarr;</span>
            </button>
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                if (onEdit) {
                  onEdit(item.id);
                } else {
                  onSelect?.(item.id);
                }
              }}
            >
              Edit
              <span aria-hidden>✎</span>
            </button>
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-danger-600 transition hover:bg-danger-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger-500"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onDelete?.(item.id);
              }}
            >
              Delete
              <span aria-hidden>×</span>
            </button>
          </div>
        ) : null}
      </div>
      <div className="aspect-[4/5] w-full overflow-hidden bg-neutral-100">
        <img
          src={imageSrc}
          alt={`${item.brand ?? 'Wardrobe item'} in ${item.color}`}
          className="h-full w-full object-cover transition group-hover:scale-105"
          loading="lazy"
          decoding="async"
        />
      </div>
      <div className="flex flex-1 flex-col gap-1 px-4 py-3">
        <div className="flex items-center justify-between text-xs uppercase tracking-wide text-neutral-500">
          <span>{item.category}</span>
          <span>{formatDate(item.createdAt)}</span>
        </div>
        <p className="text-sm font-semibold text-neutral-900">{item.brand ?? 'Unbranded'}</p>
        <p className="text-xs text-neutral-500">{item.color}</p>
        {item.tags.length > 0 ? (
          <ul className="mt-auto flex flex-wrap gap-1 pt-2">
            {item.tags.slice(0, 3).map((tag) => (
              <li
                key={tag}
                className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-medium text-neutral-600"
              >
                #{tag}
              </li>
            ))}
          </ul>
        ) : (
          <span className="mt-auto text-[11px] text-neutral-400">No tags yet</span>
        )}
      </div>
    </div>
  );
};

const ItemCard = memo(ItemCardComponent);

export default ItemCard;
