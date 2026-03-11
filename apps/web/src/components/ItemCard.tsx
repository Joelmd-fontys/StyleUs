import { memo } from 'react';
import type { KeyboardEvent } from 'react';
import { WardrobeItem } from '../domain/types';
import { cn } from '../lib/utils';
import { resolveMediaUrl } from '../lib/media';
import { useStatsPreference } from '../hooks/useStatsPreference';
import { formatUtcDate } from '../lib/datetime';

interface ItemCardProps {
  item: WardrobeItem;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
}

const ItemCardComponent = ({ item, isSelected = false, onSelect }: ItemCardProps) => {
  const [statsForNerds] = useStatsPreference();
  const imageSrc = resolveMediaUrl(item.mediumUrl, item.imageUrl, item.thumbUrl);
  const primaryColor = item.primaryColor?.trim() || item.color?.trim() || '';
  const secondaryColor = item.secondaryColor?.trim() || '';
  const hasPrimaryColor = primaryColor.length > 0;
  const hasSecondaryColor = secondaryColor.length > 0;
  const subcategory = item.subcategory ?? item.ai?.subcategory ?? null;
  const subcategoryLabel = subcategory ? subcategory.replace(/\b\w/g, (char) => char.toUpperCase()) : null;

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
        isSelected ? 'border-accent-600/80 ring-2 ring-accent-600/30' : 'border-neutral-200/80'
      )}
      aria-current={isSelected ? 'page' : undefined}
    >
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
          {statsForNerds ? <span>{formatUtcDate(item.createdAt)}</span> : null}
        </div>
        <p className="text-[11px] uppercase tracking-wide text-neutral-400">{subcategoryLabel ?? '—'}</p>
        <p className="text-sm font-semibold text-neutral-900">{item.brand ?? 'Unbranded'}</p>
        <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-neutral-500">
          <div className="flex items-center gap-2">
            <span
              className="h-5 w-5 rounded-full border border-neutral-200 shadow-sm"
              style={{ backgroundColor: hasPrimaryColor ? primaryColor : '#f5f5f5' }}
              aria-label={hasPrimaryColor ? `Primary color ${primaryColor}` : 'Primary color not set'}
            />
            <span>{hasPrimaryColor ? primaryColor : '—'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-5 w-5 rounded-full border border-neutral-200 shadow-sm"
              style={{ backgroundColor: hasSecondaryColor ? secondaryColor : '#f5f5f5' }}
              aria-label={hasSecondaryColor ? `Secondary color ${secondaryColor}` : 'Secondary color not set'}
            />
            <span>{hasSecondaryColor ? secondaryColor : '—'}</span>
          </div>
        </div>
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
