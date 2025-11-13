import { type ReactElement, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { buttonClasses } from '../components/Button';
import Card from '../components/Card';
import { useWardrobeStore } from '../store/wardrobe';
import { resolveMediaUrl } from '../lib/media';
import { useStatsPreference } from '../hooks/useStatsPreference';
import { formatUtcDate } from '../lib/datetime';

const Dashboard = (): ReactElement => {
  const items = useWardrobeStore((state) => state.items);
  const loading = useWardrobeStore((state) => state.loading);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const [statsForNerds] = useStatsPreference();

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

  const recent = useMemo(
    () =>
      [...items]
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .slice(0, 4),
    [items]
  );

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

      <Card title="Recent items" description="Latest additions to your collection">
        {loading && !items.length ? (
          <p className="text-sm text-neutral-500">Loading wardrobe...</p>
        ) : recent.length ? (
          <ul className="space-y-3">
            {recent.map((item) => {
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
                      <p className="font-medium text-neutral-900">
                        {item.brand ?? 'Unbranded'}
                      </p>
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
          <p className="text-sm text-neutral-500">No items yet. Upload your first piece to get started.</p>
        )}
      </Card>
    </div>
  );
};

export default Dashboard;
