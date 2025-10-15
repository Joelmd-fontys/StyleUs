import { memo } from 'react';
import { WardrobeItem } from '../domain/types';
import { cn } from '../lib/utils';

interface ItemCardProps {
  item: WardrobeItem;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
}

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });

const ItemCardComponent = ({ item, isSelected = false, onSelect }: ItemCardProps) => {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(item.id)}
      className={cn(
        'group flex h-full w-full flex-col overflow-hidden rounded-xl border border-transparent bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600',
        isSelected ? 'border-accent-600 ring-2 ring-accent-600/30' : 'border-neutral-200'
      )}
      aria-pressed={isSelected}
    >
      <div className="aspect-[4/5] w-full overflow-hidden bg-neutral-100">
        <img
          src={item.imageUrl}
          alt={`${item.brand ?? 'Wardrobe item'} in ${item.color}`}
          className="h-full w-full object-cover transition group-hover:scale-105"
          loading="lazy"
        />
      </div>
      <div className="flex flex-1 flex-col gap-1 px-4 py-3">
        <div className="flex items-center justify-between text-xs uppercase tracking-wide text-neutral-500">
          <span>{item.category}</span>
          <span>{formatDate(item.createdAt)}</span>
        </div>
        <p className="text-sm font-semibold text-neutral-900">{item.brand ?? 'Unbranded'}</p>
        <p className="text-xs text-neutral-500">{item.color}</p>
        {item.tags && item.tags.length > 0 ? (
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
    </button>
  );
};

const ItemCard = memo(ItemCardComponent);

export default ItemCard;
