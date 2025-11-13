import { type ReactElement, useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { buttonClasses } from '../components/Button';
import Card from '../components/Card';
import { useWardrobeStore } from '../store/wardrobe';
import { resolveMediaUrl } from '../lib/media';
import { useStatsPreference } from '../hooks/useStatsPreference';
import { formatUtcDate } from '../lib/datetime';
import { getItems } from '../lib/api';
import type { WardrobeItem } from '../domain/types';

const Dashboard = (): ReactElement => {
  const items = useWardrobeStore((state) => state.items);
  const loading = useWardrobeStore((state) => state.loading);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const [statsForNerds] = useStatsPreference();
  const [clearedSince, setClearedSince] = useState<string | null>(() => {
    if (typeof window === 'undefined') {
      return null;
    }
    return window.localStorage.getItem('styleus:recent-cleared-since');
  });
  const [showClearWarning, setShowClearWarning] = useState(false);
  const [skipClearWarning, setSkipClearWarning] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.localStorage.getItem('styleus:recent-skip-warning') === 'true';
  });
  const [recentItems, setRecentItems] = useState<WardrobeItem[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    if (!items.length && !loading) {
      void loadItems();
    }
  }, [items.length, loading, loadItems]);

  const counts = useMemo(() => {
    const total = items.length;
    const byCategory = items.reduce<Record<string, number>>((accumulator, item) => {
      accumulator[item.category] = (accumulator[item.category] ?? 0) + 1;
      return accumulator;
    }, {});

    return {
      total,
      favorites: items.filter((item) => item.tags.includes('favorite')).length,
      tops: byCategory.top ?? 0,
      shoes: byCategory.shoes ?? 0
    };
  }, [items]);

  const fetchRecentItems = useCallback(async () => {
    setRecentLoading(true);
    setRecentError(null);
    try {
      const data = await getItems({
        limit: 4,
        createdSince: clearedSince || undefined
      });
      setRecentItems(data.slice(0, 4));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load recent items';
      setRecentError(message);
    } finally {
      setRecentLoading(false);
    }
  }, [clearedSince]);

  useEffect(() => {
    void fetchRecentItems();
  }, [fetchRecentItems]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    if (clearedSince) {
      window.localStorage.setItem('styleus:recent-cleared-since', clearedSince);
    } else {
      window.localStorage.removeItem('styleus:recent-cleared-since');
    }
  }, [clearedSince]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem('styleus:recent-skip-warning', skipClearWarning ? 'true' : 'false');
  }, [skipClearWarning]);

  const showClearedMessage = clearedSince !== null && recentItems.length === 0 && !recentLoading;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Welcome back</h1>
          <p className="text-sm text-neutral-500">Track your wardrobe activity at a glance.</p>
        </div>
        <Link to="/wardrobe" className={buttonClasses('primary', 'md')}>
          Go to Wardrobe
        </Link>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Total items" description="Everything you have cataloged">
          <p className="text-3xl font-semibold text-neutral-900">{counts.total}</p>
        </Card>
        <Card title="Tops" description="Ready to style">
          <p className="text-3xl font-semibold text-neutral-900">{counts.tops}</p>
        </Card>
        <Card title="Shoes" description="Pairs on rotation">
          <p className="text-3xl font-semibold text-neutral-900">{counts.shoes}</p>
        </Card>
        <Card title="Favorites" description="Tagged with favorite">
          <p className="text-3xl font-semibold text-neutral-900">{counts.favorites}</p>
        </Card>
      </section>

      <Card
        title="Recent items"
        description="Latest additions to your collection"
        actions={
          <button
            type="button"
            onClick={() => {
              if (skipClearWarning) {
                const timestamp = new Date().toISOString();
                setClearedSince(timestamp);
                setRecentItems([]);
                return;
              }
              setShowClearWarning(true);
            }}
            disabled={recentItems.length === 0 && !clearedSince}
            className="text-xs font-semibold text-neutral-500 transition hover:text-neutral-900 disabled:opacity-40"
          >
            Clear
          </button>
        }
      >
        {showClearedMessage ? (
          <p className="text-sm text-neutral-500">
            Recent items cleared for this session. New uploads will appear here.
          </p>
        ) : recentLoading ? (
          <p className="text-sm text-neutral-500">Loading recent items...</p>
        ) : recentError ? (
          <p className="text-sm text-danger-500">{recentError}</p>
        ) : recentItems.length ? (
          <ul className="space-y-3">
            {recentItems.map((item) => {
              const imageSrc = resolveMediaUrl(item.mediumUrl, item.imageUrl, item.thumbUrl);
              return (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-4 text-sm text-neutral-700"
                >
                  <div className="flex items-center gap-3">
                    <img
                      src={imageSrc}
                      alt=""
                      className="h-12 w-12 rounded-lg border border-neutral-200 object-cover"
                      aria-hidden="true"
                      loading="lazy"
                      decoding="async"
                    />
                    <div>
                      <p className="font-medium text-neutral-900">{item.brand ?? 'Unbranded'}</p>
                      {statsForNerds ? (
                        <p className="text-xs text-neutral-500">{formatUtcDate(item.createdAt)}</p>
                      ) : null}
                    </div>
                  </div>
                  <Link to={`/items/${item.id}`} className={buttonClasses('ghost', 'sm')}>
                    View
                  </Link>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-neutral-500">No recent uploads yet. Add something new!</p>
        )}
      </Card>
      {showClearWarning
        ? createPortal(
            <div
              className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-neutral-950/70 px-4"
              role="dialog"
              aria-modal="true"
            >
              <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
                <div className="space-y-2 text-sm text-neutral-600">
                  <p className="text-lg font-semibold text-neutral-900">Hide recent items?</p>
                  <p>Clearing removes the list until you refresh the dashboard.</p>
                </div>
                <div className="mt-6 flex flex-col gap-3">
                  <div className="flex justify-between gap-3">
                    <button
                      type="button"
                      className="rounded-md bg-accent-600 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-700"
                      onClick={() => {
                        const timestamp = new Date().toISOString();
                        setClearedSince(timestamp);
                        setRecentItems([]);
                        setShowClearWarning(false);
                      }}
                    >
                      OK
                    </button>
                    <button
                      type="button"
                      className="text-sm font-medium text-neutral-500 hover:text-neutral-900"
                      onClick={() => setShowClearWarning(false)}
                    >
                      Cancel
                    </button>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-neutral-600">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-neutral-300 text-accent-600 focus:ring-accent-500"
                      checked={skipClearWarning}
                      onChange={(event) => setSkipClearWarning(event.target.checked)}
                    />
                    Don&apos;t show this again
                  </label>
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </div>
  );
};

export default Dashboard;
