import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import Card from '../components/Card';
import Filters from '../components/Filters';
import ItemCard from '../components/ItemCard';
import ConfirmDialog from '../components/ConfirmDialog';
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
  const deleteItem = useWardrobeStore((state) => state.deleteItem);
  const navigate = useNavigate();
  const location = useLocation();

  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [feedback, setFeedback] = useState<
    { message: string; tone: 'success' | 'danger' } | null
  >(null);

  useEffect(() => {
    if (location.state && (location.state as { deleted?: boolean }).deleted) {
      setFeedback({ message: 'Wardrobe item deleted.', tone: 'success' });
      navigate(location.pathname, { replace: true });
    }
  }, [location, navigate]);

  useEffect(() => {
    if (!feedback) {
      return;
    }
    const timeout = window.setTimeout(() => setFeedback(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [feedback]);

  useEffect(() => {
    if (!items.length) {
      void loadItems();
    }
  }, [items.length, loadItems]);

  const onSelectItem = (id: string) => {
    selectItem(id);
    navigate(`/items/${id}`);
  };

  const openDeleteConfirm = (id: string) => {
    setPendingDeleteId(id);
  };

  const pendingItem = useMemo(
    () => items.find((entry) => entry.id === pendingDeleteId),
    [items, pendingDeleteId]
  );

  const confirmDelete = async () => {
    if (!pendingDeleteId) {
      return;
    }
    setIsDeleting(true);
    const success = await deleteItem(pendingDeleteId);
    setIsDeleting(false);
    setPendingDeleteId(null);

    if (success) {
      setFeedback({ message: 'Wardrobe item deleted.', tone: 'success' });
    } else {
      setFeedback({ message: 'Unable to delete item. Please try again.', tone: 'danger' });
    }
  };

  const scrollToUploads = () => {
    const element = document.getElementById('upload-panel');
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">Wardrobe</h1>
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

      {feedback ? (
        <div
          className={`rounded-xl border px-4 py-3 text-sm shadow-sm ${
            feedback.tone === 'success'
              ? 'border-success-200 bg-success-50 text-success-600'
              : 'border-danger-200 bg-danger-50 text-danger-600'
          }`}
          role="status"
        >
          {feedback.message}
        </div>
      ) : null}

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
                  onEdit={onSelectItem}
                  onDelete={openDeleteConfirm}
                  isSelected={item.id === selectedItemId}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-300 bg-white/80 px-6 py-16 text-center shadow-sm backdrop-blur">
              <h2 className="text-lg font-semibold text-neutral-900">Your wardrobe is empty</h2>
              <p className="mt-2 max-w-sm text-sm text-neutral-500">
                Upload your first item to start building a personalized closet. You can always add more later.
              </p>
              <Button className="mt-6" variant="secondary" onClick={scrollToUploads}>
                Upload an item
              </Button>
            </div>
          )}
        </div>

        <UploadPanel />
      </div>

      <ConfirmDialog
        open={Boolean(pendingDeleteId)}
        title="Delete wardrobe item"
        description={
          pendingItem?.brand
            ? `Delete "${pendingItem.brand}"? This can't be undone.`
            : "Delete this item? This can't be undone."
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        tone="danger"
        busy={isDeleting}
        onCancel={() => {
          if (!isDeleting) {
            setPendingDeleteId(null);
          }
        }}
        onConfirm={() => {
          void confirmDelete();
        }}
      />
    </div>
  );
};

export default Wardrobe;
