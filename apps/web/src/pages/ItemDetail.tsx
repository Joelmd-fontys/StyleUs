import { type FormEvent, type ReactElement, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Button, { buttonClasses } from '../components/Button';
import Card from '../components/Card';
import Field from '../components/Field';
import { wardrobeItemEditSchema } from '../lib/validation';
import type { PatchItemRequest } from '../domain/contracts';
import { useWardrobeStore } from '../store/wardrobe';
import { WardrobeCategory, WardrobeSubcategory } from '../domain/types';
import { resolveMediaUrl } from '../lib/media';
import ConfirmDialog from '../components/ConfirmDialog';
import { cn } from '../lib/utils';
import { formatUtcDate, formatUtcTime } from '../lib/datetime';
import { useStatsPreference } from '../hooks/useStatsPreference';
import { getSubcategories, ITEM_DETAIL_CATEGORY_OPTIONS, toDisplayLabel } from '../domain/labels';

type FormErrors = Partial<Record<'category' | 'color' | 'brand' | 'tags', string>>;

const formatSize = (value?: number | null): string =>
  typeof value === 'number' && !Number.isNaN(value) ? `${(value / 1024).toFixed(1)} kB` : '—';

const ItemDetail = (): ReactElement => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const items = useWardrobeStore((state) => state.items);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const selectItem = useWardrobeStore((state) => state.selectItem);
  const saveItem = useWardrobeStore((state) => state.saveItem);
  const refreshItem = useWardrobeStore((state) => state.refreshItem);
  const deleteItem = useWardrobeStore((state) => state.deleteItem);

  const [category, setCategory] = useState<WardrobeCategory>('unknown');
  const [subcategory, setSubcategory] = useState<WardrobeSubcategory | ''>('');
  const [color, setColor] = useState('');
  const [brand, setBrand] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});
  const [status, setStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | undefined>();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [statsForNerds] = useStatsPreference();

  const item = useMemo(() => items.find((entry) => entry.id === id), [id, items]);
  const subcategoryOptions = useMemo(() => getSubcategories(category), [category]);

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
    setSubcategory((item.subcategory as WardrobeSubcategory | undefined) ?? '');
    setColor(item.color);
    setBrand(item.brand ?? '');
    setTagsInput(item.tags.join(', '));
  }, [item]);

  useEffect(() => {
    if (subcategory && !subcategoryOptions.includes(subcategory as WardrobeSubcategory)) {
      setSubcategory('');
    }
  }, [subcategoryOptions, subcategory]);

  const brandNeedsAttention = brand.trim().length === 0;
  const brandFieldError = errors.brand ?? (brandNeedsAttention ? 'Please add a brand' : undefined);
  const brandInputClasses = cn(
    'w-full rounded-md border bg-white px-3 py-2 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-accent-600/20',
    brandFieldError
      ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-200/70'
      : 'border-neutral-200 focus:border-accent-600'
  );

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
      subcategory: subcategory || null,
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

    const payload: PatchItemRequest = {
      ...parsed.data,
      subcategory: (parsed.data.subcategory as WardrobeSubcategory | null | undefined) ?? null
    };
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

  const createdDate = formatUtcDate(item.createdAt);
  const createdTime = formatUtcTime(item.createdAt);
  const imageSrc = resolveMediaUrl(item.mediumUrl, item.imageUrl);

  const renderColorDetail = (label: string, value?: string | null) => {
    const normalized = value?.trim() ?? '';
    const hasColor = normalized.length > 0;
    return (
      <div>
        <dt className="font-medium text-neutral-900">{label}</dt>
        <dd className="flex items-center gap-2 capitalize">
          <span
            className="h-5 w-5 rounded-full border border-neutral-200 shadow-sm"
            style={{ backgroundColor: hasColor ? normalized : '#f5f5f5' }}
            aria-label={hasColor ? normalized : 'Color not set'}
          />
          <span>{hasColor ? normalized : '—'}</span>
        </dd>
      </div>
    );
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">
            {item.brand ?? 'Wardrobe item'}
          </h1>
          {statsForNerds ? (
            <p className="text-sm text-neutral-500">
              Added on {createdDate}
              {createdTime ? `, ${createdTime}` : ''}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/wardrobe" className={buttonClasses('ghost', 'sm')}>
            Back to Wardrobe
          </Link>
          <Button variant="danger" size="sm" onClick={() => setDeleteDialogOpen(true)} disabled={deleteBusy}>
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
                <dt className="font-medium text-neutral-900">Subcategory</dt>
                <dd className="capitalize">{item.subcategory ? toDisplayLabel(item.subcategory) : '—'}</dd>
              </div>
              {renderColorDetail('Primary color', item.primaryColor)}
              {renderColorDetail('Secondary color', item.secondaryColor)}
              <div>
                <dt className="font-medium text-neutral-900">Brand</dt>
                <dd>{item.brand ?? 'Unbranded'}</dd>
              </div>
              <div>
                <dt className="font-medium text-neutral-900">Tags</dt>
                <dd>{item.tags.length > 0 ? item.tags.join(', ') : 'No tags yet'}</dd>
              </div>
              {statsForNerds && item.imageMetadata ? (
                <div className="col-span-2">
                  <dt className="font-medium text-neutral-900">Image details</dt>
                  <dd>
                    <span>
                      {item.imageMetadata.width ?? '—'} × {item.imageMetadata.height ?? '—'} px
                    </span>
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
                {ITEM_DETAIL_CATEGORY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {toDisplayLabel(option)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Subcategory" htmlFor="subcategory">
              <select
                id="subcategory"
                name="subcategory"
                value={subcategory}
                onChange={(event) => setSubcategory(event.target.value as WardrobeSubcategory | '')}
                disabled={!subcategoryOptions.length}
                className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/20 disabled:cursor-not-allowed disabled:bg-neutral-50"
              >
                <option value="">Select a subcategory</option>
                {subcategoryOptions.map((option) => (
                  <option key={option} value={option}>
                    {toDisplayLabel(option)}
                  </option>
                ))}
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
              error={brandFieldError}
            >
              <input
                id="brand"
                name="brand"
                value={brand}
                onChange={(event) => setBrand(event.target.value)}
                maxLength={60}
                className={brandInputClasses}
                aria-invalid={Boolean(brandFieldError)}
              />
            </Field>

            <Field label="Tags" htmlFor="tags" description="Comma separated" error={errors.tags}>
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
                  status === 'success'
                    ? 'text-success-500'
                    : status === 'error'
                      ? 'text-danger-500'
                      : 'text-neutral-500'
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
                  setSubcategory((item.subcategory as WardrobeSubcategory | undefined) ?? '');
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
