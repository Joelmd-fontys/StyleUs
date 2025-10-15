import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import Card from '../components/Card';
import Filters from '../components/Filters';
import ItemCard from '../components/ItemCard';
import UploadPanel from '../components/UploadPanel';
import { useWardrobeStore } from '../store/wardrobe';

const Wardrobe = () => {
  const items = useWardrobeStore((state) => state.items);
  const loading = useWardrobeStore((state) => state.loading);
  const error = useWardrobeStore((state) => state.error);
  const filters = useWardrobeStore((state) => state.filters);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const setFilters = useWardrobeStore((state) => state.setFilters);
  const selectItem = useWardrobeStore((state) => state.selectItem);
  const selectedItemId = useWardrobeStore((state) => state.selectedItemId);
  const navigate = useNavigate();

  useEffect(() => {
    if (!items.length) {
      void loadItems();
    }
  }, [items.length, loadItems]);

  const onSelectItem = (id: string) => {
    selectItem(id);
    navigate(`/items/${id}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-neutral-900">Wardrobe</h1>
        <p className="text-sm text-neutral-500">
          Browse your collection, edit details, and add new pieces.
        </p>
      </div>

      <Filters
        category={filters.category}
        q={filters.q}
        onChange={(next) => {
          void setFilters(next);
        }}
      />

      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div className="space-y-4">
          {error ? (
            <div className="flex items-center justify-between rounded-md border border-danger-500 bg-danger-500/10 px-4 py-3 text-sm text-danger-500">
              <span>{error}</span>
              <Button variant="ghost" size="sm" onClick={() => void loadItems()}>
                Retry
              </Button>
            </div>
          ) : null}

          {loading && !items.length ? (
            <Card>
              <p className="text-sm text-neutral-500">Loading wardrobe...</p>
            </Card>
          ) : items.length ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  onSelect={onSelectItem}
                  isSelected={item.id === selectedItemId}
                />
              ))}
            </div>
          ) : (
            <Card>
              <p className="text-sm text-neutral-500">
                No items match these filters. Try adjusting your search or upload something new.
              </p>
            </Card>
          )}
        </div>

        <UploadPanel />
      </div>
    </div>
  );
};

export default Wardrobe;
