import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Button, { buttonClasses } from '../components/Button';
import Card from '../components/Card';
import Field from '../components/Field';
import { wardrobeItemEditSchema } from '../lib/validation';
import { useWardrobeStore } from '../store/wardrobe';
import { WardrobeCategory } from '../domain/types';
import { resolveMediaUrl } from '../lib/media';
import ConfirmDialog from '../components/ConfirmDialog';

type FormErrors = Partial<Record<'category' | 'color' | 'brand' | 'tags', string>>;

const formatSize = (value?: number | null) =>
  typeof value === 'number' && !Number.isNaN(value) ? `${(value / 1024).toFixed(1)} kB` : '—';

const ItemDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const items = useWardrobeStore((state) => state.items);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const selectItem = useWardrobeStore((state) => state.selectItem);
  const saveItem = useWardrobeStore((state) => state.saveItem);
  const refreshItem = useWardrobeStore((state) => state.refreshItem);
  const deleteItem = useWardrobeStore((state) => state.deleteItem);

  const item = useMemo(() => items.find((entry) => entry.id === id), [id, items]);

  const [category, setCategory] = useState<WardrobeCategory>('unknown');
  const [color, setColor] = useState('');
  const [brand, setBrand] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});
  const [status, setStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | undefined>();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  useEffect(() => {
    if (!items.length) {
      void loadItems();
    }
  }, [items.length, loadItems]);

  useEffect(() => {
    if (id) {
      selectItem(id);
    }
  }, [id, selectItem]);

  useEffect(() => {
    if (!item && id) {
      void refreshItem(id);
    }
  }, [id, item, refreshItem]);

  useEffect(() => {
    if (!item) {
      return;
    }
    setCategory(item.category);
    setColor(item.color);
    setBrand(item.brand ?? '');
    setTagsInput(item.tags.join(', '));
  }, [item]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!id) {
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);

    const parsed = wardrobeItemEditSchema.safeParse({
      category,
      color,
      brand,
      tags
    });

    if (!parsed.success) {
      const fieldErrors: FormErrors = {};
      parsed.error.issues.forEach((issue) => {
        const path = issue.path[0];
        if (path) {
          fieldErrors[path as keyof FormErrors] = issue.message;
        }
      });
      setErrors(fieldErrors);
      setStatus('error');
      setMessage('Please correct the highlighted fields.');
      return;
    }

    setErrors({});
    setStatus('saving');
    setMessage(undefined);

    const payload = parsed.data;
    const result = await saveItem(id, payload);

    if (result) {
      setStatus('success');
      setMessage('Item updated.');
      setTimeout(() => {
        setStatus('idle');
        setMessage(undefined);
      }, 2000);
    } else {
      setStatus('error');
      setMessage('There was a problem saving this item.');
    }
  };

  const handleDelete = async () => {
    if (!id) {
      return;
    }
    setDeleteBusy(true);
    const success = await deleteItem(id);
    setDeleteBusy(false);
    setDeleteDialogOpen(false);

    if (success) {
      selectItem(undefined);
      navigate('/wardrobe', { replace: true, state: { deleted: true } });
    } else {
      setStatus('error');
      setMessage('Unable to delete item. Please try again.');
    }
  };

  if (!id) {
    return (
      <Card>
        <p className="text-sm text-neutral-500">No item selected.</p>
      </Card>
    );
  }

  if (!item) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          Back
        </Button>
        <Card>
          <p className="text-sm text-neutral-500">Loading item details...</p>
        </Card>
      </div>
    );
  }

  const createdAt = new Date(item.createdAt).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  });
  const imageSrc = resolveMediaUrl(item.mediumUrl, item.imageUrl);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">
            {item.brand ?? 'Wardrobe item'}
          </h1>
          <p className="text-sm text-neutral-500">Added on {createdAt}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/wardrobe" className={buttonClasses('ghost', 'sm')}>
            Back to Wardrobe
          </Link>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteDialogOpen(true)}
            disabled={deleteBusy}
          >
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-[1.5fr,1fr]">
        <Card className="md:row-span-2">
          <div className="flex flex-col gap-4">
            <div className="overflow-hidden rounded-lg bg-neutral-100">
              <img
                src={imageSrc}
                alt={item.brand ?? 'Wardrobe item'}
                className="w-full object-cover"
                loading="lazy"
                decoding="async"
              />
            </div>

            <dl className="grid grid-cols-2 gap-3 text-sm text-neutral-600">
              <div>
                <dt className="font-medium text-neutral-900">Category</dt>
                <dd className="capitalize">{item.category}</dd>
              </div>
              <div>
                <dt className="font-medium text-neutral-900">Color</dt>
                <dd className="capitalize">{item.color}</dd>
              </div>
              <div>
                <dt className="font-medium text-neutral-900">Brand</dt>
                <dd>{item.brand ?? 'Unbranded'}</dd>
              </div>
              <div>
                <dt className="font-medium text-neutral-900">Tags</dt>
                <dd>{item.tags.length > 0 ? item.tags.join(', ') : 'No tags yet'}</dd>
              </div>
              {item.imageMetadata ? (
                <div className="col-span-2">
                  <dt className="font-medium text-neutral-900">Image details</dt>
                  <dd>
                    <span>{item.imageMetadata.width ?? '—'} × {item.imageMetadata.height ?? '—'} px</span>
                    <span className="ml-2 text-neutral-500">{formatSize(item.imageMetadata.bytes)}</span>
                  </dd>
                </div>
              ) : null}
            </dl>
          </div>
        </Card>

        <Card title="Edit details" description="Updates are saved through the wardrobe API.">
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <Field label="Category" htmlFor="category" required error={errors.category}>
              <select
                id="category"
                name="category"
                value={category}
                onChange={(event) => setCategory(event.target.value as WardrobeCategory)}
                className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20"
              >
                <option value="top">Top</option>
                <option value="bottom">Bottom</option>
                <option value="outerwear">Outerwear</option>
                <option value="shoes">Shoes</option>
                <option value="accessory">Accessory</option>
                <option value="unknown">Unknown</option>
                <option value="uncategorized">Uncategorized</option>
              </select>
            </Field>

            <Field label="Color" htmlFor="color" required error={errors.color}>
              <input
                id="color"
                name="color"
                value={color}
                onChange={(event) => setColor(event.target.value)}
                className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20"
              />
            </Field>

            <Field
              label="Brand"
              htmlFor="brand"
              description="Optional, max 60 characters."
              error={errors.brand}
            >
              <input
                id="brand"
                name="brand"
                value={brand}
                onChange={(event) => setBrand(event.target.value)}
                maxLength={60}
                className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20"
              />
            </Field>

            <Field
              label="Tags"
              htmlFor="tags"
              description="Comma separated"
              error={errors.tags}
            >
              <input
                id="tags"
                name="tags"
                value={tagsInput}
                onChange={(event) => setTagsInput(event.target.value)}
                className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20"
                placeholder="e.g. spring, workwear"
              />
            </Field>

            {message ? (
              <p
                className={`text-sm ${
                  status === 'success' ? 'text-success-500' : status === 'error' ? 'text-danger-500' : 'text-neutral-500'
                }`}
              >
                {message}
              </p>
            ) : null}

            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setCategory(item.category);
                  setColor(item.color);
                  setBrand(item.brand ?? '');
                  setTagsInput(item.tags.join(', '));
                  setErrors({});
                  setStatus('idle');
                  setMessage(undefined);
                }}
              >
                Reset
              </Button>
              <Button type="submit" disabled={status === 'saving'}>
                {status === 'saving' ? 'Saving...' : 'Save changes'}
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete wardrobe item"
        description="Delete this item? This can't be undone."
        confirmLabel="Delete"
        tone="danger"
        busy={deleteBusy}
        onCancel={() => {
          if (!deleteBusy) {
            setDeleteDialogOpen(false);
          }
        }}
        onConfirm={() => {
          void handleDelete();
        }}
      />
    </div>
  );
};

export default ItemDetail;
