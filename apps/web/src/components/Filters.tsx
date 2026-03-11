import { type FormEvent, type ReactElement, useEffect, useState } from 'react';
import Button from './Button';
import { WardrobeCategory } from '../domain/types';
import { FILTER_CATEGORY_OPTIONS } from '../domain/labels';
import { cn } from '../lib/utils';

interface FiltersProps {
  category?: WardrobeCategory;
  q?: string;
  onChange: (filters: { category?: WardrobeCategory; q?: string }) => void;
  onReset?: () => void;
  className?: string;
}

const Filters = ({ category, q, onChange, onReset, className }: FiltersProps): ReactElement => {
  const [searchValue, setSearchValue] = useState(q ?? '');

  useEffect(() => {
    setSearchValue(q ?? '');
  }, [q]);

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onChange({ category, q: searchValue.trim() || undefined });
  };

  const reset = () => {
    setSearchValue('');
    onChange({ category: undefined, q: undefined });
    onReset?.();
  };

  return (
    <div
      className={cn(
        'flex flex-col justify-between gap-3 rounded-xl border border-neutral-200 bg-white/90 p-4 backdrop-blur md:flex-row md:items-center',
        className
      )}
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <label htmlFor="category-filter" className="text-sm font-medium text-neutral-700">
          Category
        </label>
        <select
          id="category-filter"
          name="category"
          value={category ?? ''}
          onChange={(event) => {
            const value = event.target.value as WardrobeCategory | '';
            onChange({
              category: value ? (value as WardrobeCategory) : undefined,
              q: searchValue.trim() || undefined
            });
          }}
          className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20 md:w-48"
        >
          {FILTER_CATEGORY_OPTIONS.map((option) => (
            <option key={option.label} value={option.value ?? ''}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <form onSubmit={submitSearch} className="flex w-full flex-col gap-2 md:max-w-md md:flex-row">
        <label className="sr-only" htmlFor="wardrobe-search">
          Search wardrobe
        </label>
        <input
          id="wardrobe-search"
          name="q"
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
          placeholder="Search by brand or tag"
          className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 placeholder:text-neutral-400 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20"
        />
        <div className="flex gap-2">
          <Button type="submit" variant="primary" size="sm">
            Apply
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={reset}>
            Reset
          </Button>
        </div>
      </form>
    </div>
  );
};

export default Filters;
