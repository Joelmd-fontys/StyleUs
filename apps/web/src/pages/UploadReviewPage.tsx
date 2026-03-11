import { type ReactElement, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Button from '../components/Button';
import { useWardrobeStore } from '../store/wardrobe';
import { cn } from '../lib/utils';
import { WardrobeCategory, WardrobeSubcategory } from '../domain/types';
import { getSubcategories, toDisplayLabel, UPLOAD_REVIEW_CATEGORY_OPTIONS } from '../domain/labels';
import { type AIPreviewResponse } from '../domain/contracts';
import { resolveMediaUrl } from '../lib/media';

interface UploadReviewForm {
  category: WardrobeCategory;
  subcategory: WardrobeSubcategory | '';
  brand: string;
  primaryColor: string;
  secondaryColor: string;
  tagsInput: string;
}

const toDisplayTags = (input: string): string[] =>
  input
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean);

const LONG_RUNNING_PENDING_MS = 20_000;
const AI_LOADING_STEPS = [
  'Reading image features',
  'Estimating garment shape',
  'Detecting color signals',
  'Ranking category matches',
  'Preparing suggestions'
] as const;

const toTopAITags = (ai?: AIPreviewResponse | null): string[] => {
  if (!ai) {
    return [];
  }
  if (ai.tags && ai.tags.length > 0) {
    return ai.tags.slice(0, 3);
  }
  const combined = [...(ai.materials ?? []), ...(ai.styleTags ?? [])];
  const seen = new Set<string>();
  const unique: string[] = [];
  combined.forEach((tag) => {
    if (!seen.has(tag)) {
      seen.add(tag);
      unique.push(tag);
    }
  });
  return unique.slice(0, 3);
};

const UploadReviewPage = (): ReactElement | null => {
  const { id: itemId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const uploadReview = useWardrobeStore((state) => state.uploadReview);
  const fetchAIPreview = useWardrobeStore((state) => state.fetchUploadReviewAI);
  const hydrateUploadReview = useWardrobeStore((state) => state.hydrateUploadReview);
  const saveItem = useWardrobeStore((state) => state.saveItem);
  const deleteItem = useWardrobeStore((state) => state.deleteItem);
  const clearUploadReview = useWardrobeStore((state) => state.clearUploadReview);
  const loadItems = useWardrobeStore((state) => state.loadItems);
  const showFlashMessage = useWardrobeStore((state) => state.showFlashMessage);
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const [form, setForm] = useState<UploadReviewForm>({
    category: 'uncategorized',
    subcategory: '',
    brand: '',
    primaryColor: '',
    secondaryColor: '',
    tagsInput: ''
  });
  const [isPolling, setIsPolling] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);

  const item = uploadReview?.item;
  const ai = uploadReview?.ai;
  const aiPending = Boolean(ai?.pending ?? item?.aiJob?.pending);
  const aiFailed = ai?.job?.status === 'failed';
  const pendingStartedAt =
    ai?.job?.startedAt ?? ai?.job?.createdAt ?? item?.aiJob?.startedAt ?? item?.aiJob?.createdAt;
  const pendingDurationMs = pendingStartedAt ? Date.now() - Date.parse(pendingStartedAt) : 0;
  const aiPendingLongerThanExpected =
    aiPending && Number.isFinite(pendingDurationMs) && pendingDurationMs >= LONG_RUNNING_PENDING_MS;
  const aiTagSuggestions = useMemo(() => toTopAITags(ai), [ai]);
  const resolvedSubcategory =
    (ai?.subcategory as WardrobeSubcategory | undefined) ??
    (item?.subcategory as WardrobeSubcategory | undefined) ??
    null;
  const availableSubcategories = useMemo(() => getSubcategories(form.category), [form.category]);
  useEffect(() => {
    if (form.subcategory && !availableSubcategories.includes(form.subcategory as WardrobeSubcategory)) {
      setForm((prev) => ({ ...prev, subcategory: '' }));
    }
  }, [availableSubcategories, form.subcategory]);
  const confidenceMetrics = useMemo(() => {
    const format = (value?: number | null) =>
      typeof value === 'number' && !Number.isNaN(value) ? Math.round(value * 100) : null;
    return [
      {
        label: 'Category',
        value: format(ai?.categoryConfidence ?? ai?.confidence ?? item?.aiConfidence ?? null)
      },
      { label: 'Subcategory', value: format(ai?.subcategoryConfidence ?? null) },
      { label: 'Primary color', value: format(ai?.primaryColorConfidence) },
      { label: 'Secondary color', value: format(ai?.secondaryColorConfidence) }
    ];
  }, [
    ai?.categoryConfidence,
    ai?.confidence,
    ai?.primaryColorConfidence,
    ai?.secondaryColorConfidence,
    ai?.subcategoryConfidence,
    item?.aiConfidence
  ]);

  useEffect(() => {
    if (!itemId) {
      return;
    }
    if (!uploadReview || uploadReview.item?.id !== itemId) {
      void hydrateUploadReview(itemId).then(() => fetchAIPreview(itemId));
      return;
    }
    if (!uploadReview.ai && !uploadReview.loading) {
      void fetchAIPreview(itemId);
    }
  }, [fetchAIPreview, hydrateUploadReview, itemId, uploadReview]);

  useEffect(() => {
    if (!item) {
      return;
    }
    const baseCategory =
      (ai?.category as WardrobeCategory | undefined) ??
      (item.category as WardrobeCategory) ??
      'uncategorized';
    const baseSubcategory = ((ai?.subcategory as WardrobeSubcategory | undefined) ??
      (item.subcategory as WardrobeSubcategory | undefined) ??
      '') as WardrobeSubcategory | '';
    const basePrimary = ai?.primaryColor ?? item.primaryColor ?? item.color ?? '';
    const baseSecondary = ai?.secondaryColor ?? item.secondaryColor ?? '';
    const baseBrand = item.brand ?? '';
    const baseTags = aiTagSuggestions.length ? aiTagSuggestions : (item.tags ?? []);

    setForm({
      category: baseCategory,
      subcategory: baseSubcategory,
      brand: baseBrand,
      primaryColor: basePrimary ?? '',
      secondaryColor: baseSecondary ?? '',
      tagsInput: baseTags.join(', ')
    });
  }, [ai?.category, ai?.primaryColor, ai?.secondaryColor, ai?.subcategory, aiTagSuggestions, item]);

  useEffect(() => {
    if (!uploadReview || uploadReview.error) {
      setIsPolling(false);
      return;
    }
    const awaitingPrediction =
      Boolean(uploadReview.ai?.pending ?? uploadReview.item?.aiJob?.pending) ||
      (!uploadReview.ai && !uploadReview.loading);
    if (awaitingPrediction && !isPolling) {
      setIsPolling(true);
      return;
    }
    if (!awaitingPrediction && isPolling) {
      setIsPolling(false);
    }
  }, [uploadReview, isPolling]);

  useEffect(() => {
    if (!isPolling || !itemId) {
      return;
    }
    let cancelled = false;
    const refresh = () => {
      if (!cancelled) {
        void fetchAIPreview(itemId);
      }
    };
    refresh();
    const interval = window.setInterval(refresh, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [isPolling, itemId, fetchAIPreview]);

  const handleAccept = async () => {
    if (!item || !itemId) {
      return;
    }
    if (!ai || aiPending) {
      showFlashMessage('AI predictions are still processing. Please retry shortly.', 'error');
      return;
    }
    const normalizedBrand = form.brand.trim();
    const payload = {
      category: (ai.category as WardrobeCategory) ?? item.category,
      subcategory: (ai.subcategory as WardrobeSubcategory | undefined) ?? item.subcategory ?? null,
      color: ai.primaryColor ?? item.primaryColor ?? item.color,
      primaryColor: ai.primaryColor ?? null,
      secondaryColor: ai.secondaryColor ?? null,
      brand: normalizedBrand.length ? normalizedBrand : null,
      tags: aiTagSuggestions.length ? aiTagSuggestions : item.tags
    };
    const updated = await saveItem(itemId, payload);
    if (updated) {
      await loadItems();
      showFlashMessage('Item added successfully');
      clearUploadReview();
      navigate('/wardrobe');
    } else {
      showFlashMessage('Unable to save item. Please try again.', 'error');
    }
  };

  const handleConfirmEdits = async () => {
    if (!item || !itemId) {
      return;
    }
    const tags = toDisplayTags(form.tagsInput);
    const normalizedBrand = form.brand.trim();
    const payload = {
      category: form.category,
      subcategory: form.subcategory || item.subcategory || null,
      color: form.primaryColor || item.color,
      primaryColor: form.primaryColor || null,
      secondaryColor: form.secondaryColor || null,
      brand: normalizedBrand.length ? normalizedBrand : null,
      tags
    };
    const updated = await saveItem(itemId, payload);
    if (updated) {
      await loadItems();
      showFlashMessage('Item added successfully');
      clearUploadReview();
      navigate('/wardrobe');
    } else {
      showFlashMessage('Unable to save item. Please try again.', 'error');
    }
  };

  const handleCancel = async () => {
    if (!itemId) {
      navigate('/wardrobe');
      return;
    }
    const removed = await deleteItem(itemId);
    clearUploadReview();
    showFlashMessage(removed ? 'Upload discarded' : 'Unable to discard upload', 'error');
    navigate('/wardrobe');
  };

  const isInitialAnalyzing =
    uploadReview !== undefined &&
    (Boolean(uploadReview.loading && !uploadReview.ai) || (!uploadReview.ai && !uploadReview.error));
  const isAwaitingPredictions = aiPending || isInitialAnalyzing;
  const showBlockingOverlay =
    uploadReview !== undefined && !uploadReview?.error && isAwaitingPredictions;
  const loadingProgress =
    18 + (loadingStepIndex / Math.max(AI_LOADING_STEPS.length - 1, 1)) * 64;
  const loadingStage = AI_LOADING_STEPS[loadingStepIndex];

  useEffect(() => {
    if (!showBlockingOverlay) {
      setLoadingStepIndex(0);
      return;
    }
    const interval = window.setInterval(() => {
      setLoadingStepIndex((current) => (current + 1) % AI_LOADING_STEPS.length);
    }, 1400);
    return () => window.clearInterval(interval);
  }, [showBlockingOverlay]);

  const renderImagePreview = () => {
    const hasImage = Boolean(item?.imageUrl ?? item?.mediumUrl ?? item?.thumbUrl);
    if (!hasImage) {
      return (
        <div className="flex h-72 w-full items-center justify-center rounded-xl bg-neutral-100 text-sm text-neutral-500">
          No image available
        </div>
      );
    }
    const source = resolveMediaUrl(item?.imageUrl, item?.mediumUrl, item?.thumbUrl);
    return <img src={source} alt="Uploaded item" className="h-72 w-full rounded-xl object-cover shadow-sm" />;
  };

  const renderColorSwatch = (label: string, value: string, fallbackText: string) => {
    const key = label.toLowerCase().includes('primary') ? 'primaryColor' : 'secondaryColor';
    const inputId = `${key}-input`;
    const isValidColor = value && value.trim().length > 0;
    return (
      <div>
        <label
          className="text-sm font-medium text-neutral-700"
          htmlFor={mode === 'edit' ? inputId : undefined}
        >
          {label}
        </label>
        <div className="mt-2 flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-full border border-neutral-300 shadow-sm"
            style={{ backgroundColor: isValidColor ? value : '#f5f5f5' }}
            aria-label={isValidColor ? value : 'No color'}
          />
          {mode === 'edit' ? (
            <input
              type="text"
              id={inputId}
              value={value}
              onChange={(event) =>
                setForm((prev) => ({
                  ...prev,
                  [key]: event.target.value
                }))
              }
              placeholder={fallbackText}
              className="flex-1 rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-accent-500 focus:outline-none"
            />
          ) : (
            <span className="text-sm text-neutral-700">{isValidColor ? value : fallbackText}</span>
          )}
        </div>
      </div>
    );
  };

  const renderTagList = () => {
    const tags =
      mode === 'edit'
        ? toDisplayTags(form.tagsInput)
        : aiTagSuggestions.length
          ? aiTagSuggestions
          : (item?.tags ?? []);
    if (mode === 'edit') {
      return (
        <div>
          <label className="text-sm font-medium text-neutral-700" htmlFor="review-tags">
            Tags
          </label>
          <input
            id="review-tags"
            type="text"
            value={form.tagsInput}
            onChange={(event) => setForm((prev) => ({ ...prev, tagsInput: event.target.value }))}
            placeholder="cotton, streetwear"
            className="mt-2 w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-accent-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-neutral-500">Separate tags with commas.</p>
        </div>
      );
    }
    if (!tags.length) {
      return <p className="text-sm text-neutral-500">No AI tags predicted yet.</p>;
    }
    return (
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-neutral-200/80 px-3 py-1 text-xs font-medium text-neutral-700"
          >
            {tag}
          </span>
        ))}
      </div>
    );
  };

  const brandNeedsAttention = form.brand.trim().length === 0;
  const brandInputClasses = cn(
    'mt-2 w-full rounded-md border bg-white px-3 py-2 text-sm shadow-sm focus:outline-none md:w-56',
    brandNeedsAttention
      ? 'border-danger-300 focus:border-danger-500 focus:ring-2 focus:ring-danger-200/70'
      : 'border-neutral-200 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/10'
  );

  if (!itemId) {
    return null;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <button
          type="button"
          className="text-sm text-neutral-500 transition hover:text-neutral-900"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <h1 className="mt-2 text-2xl font-semibold text-neutral-900">Review AI suggestions</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Double-check the predictions below, make any tweaks, and confirm to add this item to your wardrobe.
        </p>
      </div>

      <div className="grid gap-8 rounded-2xl bg-white/90 p-6 shadow-sm backdrop-blur md:grid-cols-[320px,1fr]">
        <div>{renderImagePreview()}</div>
        <div className="relative space-y-6" aria-busy={showBlockingOverlay}>
          {showBlockingOverlay ? (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-xl bg-white/92 px-8 text-center backdrop-blur-sm">
              <div
                className="w-full max-w-sm rounded-2xl border border-neutral-200 bg-white px-6 py-7 shadow-sm"
                role="status"
                aria-live="polite"
              >
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-neutral-200 bg-neutral-50 shadow-sm">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-neutral-200 border-t-accent-500" />
                </div>
                <p className="mt-4 text-sm font-semibold text-neutral-900">Analyzing your item</p>
                <p className="mt-1 text-xs uppercase tracking-[0.18em] text-neutral-500">
                  {loadingStage}
                </p>
                <div className="mt-5 h-2 overflow-hidden rounded-full bg-neutral-200">
                  <div
                    className="h-full rounded-full bg-accent-500 transition-all duration-700 ease-out"
                    style={{ width: `${loadingProgress}%` }}
                  />
                </div>
                <p className="mt-3 text-xs text-neutral-500">
                  {aiPendingLongerThanExpected
                    ? 'Still running the AI pipeline.'
                    : 'This usually takes a few seconds.'}
                </p>
              </div>
            </div>
          ) : null}

          <div className={cn('space-y-4', showBlockingOverlay ? 'pointer-events-none opacity-40' : '')}>
            {uploadReview?.error ? (
              <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-600">
                {uploadReview.error}
              </div>
            ) : aiFailed ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
                AI suggestions could not be completed automatically. You can continue by editing the
                item manually.
              </div>
            ) : null}

            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                {mode === 'edit' ? (
                  <label className="text-sm font-medium text-neutral-700" htmlFor="review-category">
                    Category
                  </label>
                ) : (
                  <p className="text-sm font-medium text-neutral-700">Category</p>
                )}
                {mode === 'edit' ? (
                  <select
                    id="review-category"
                    value={form.category}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        category: event.target.value as WardrobeCategory
                      }))
                    }
                    className="mt-2 rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-accent-500 focus:outline-none"
                  >
                    {UPLOAD_REVIEW_CATEGORY_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {toDisplayLabel(option)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="mt-1 text-lg font-semibold text-neutral-900">
                    {(ai?.category ?? item?.category ?? 'uncategorized').toUpperCase()}
                  </p>
                )}
              </div>
              <div>
                {mode === 'edit' ? (
                  <label className="text-sm font-medium text-neutral-700" htmlFor="review-subcategory">
                    Subcategory
                  </label>
                ) : (
                  <p className="text-sm font-medium text-neutral-700">Subcategory</p>
                )}
                {mode === 'edit' ? (
                  <select
                    id="review-subcategory"
                    value={form.subcategory}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        subcategory: event.target.value as WardrobeSubcategory | ''
                      }))
                    }
                    disabled={!availableSubcategories.length}
                    className="mt-2 w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-accent-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-neutral-50 md:w-56"
                  >
                    <option value="">Select a subcategory</option>
                    {availableSubcategories.map((option) => (
                      <option key={option} value={option}>
                        {toDisplayLabel(option)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="mt-1 text-sm text-neutral-700">
                    {resolvedSubcategory ? toDisplayLabel(resolvedSubcategory) : 'Not set'}
                  </p>
                )}
              </div>
              <div>
                <label className="text-sm font-medium text-neutral-700" htmlFor="review-brand">
                  Brand
                </label>
                <input
                  id="review-brand"
                  type="text"
                  value={form.brand}
                  onChange={(event) => setForm((prev) => ({ ...prev, brand: event.target.value }))}
                  placeholder="e.g. Nike"
                  className={brandInputClasses}
                  aria-invalid={brandNeedsAttention}
                />
                {brandNeedsAttention ? (
                  <p className="mt-1 text-xs font-medium text-danger-600">Please add a brand</p>
                ) : null}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {renderColorSwatch('Primary color', form.primaryColor, 'Not detected')}
              {renderColorSwatch('Secondary color', form.secondaryColor, 'Not detected')}
            </div>

            <div>
              <p className="text-sm font-medium text-neutral-700">Tags</p>
              <div className="mt-2">{renderTagList()}</div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-neutral-500">
                <span>AI confidence</span>
                <button
                  type="button"
                  className="text-xs font-medium text-neutral-500 transition hover:text-neutral-900"
                  onClick={() => itemId && fetchAIPreview(itemId)}
                >
                  Refresh
                </button>
              </div>
              <div className="space-y-2">
                {confidenceMetrics.map(({ label, value }) => (
                  <div key={label} className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-500">
                      <span>{label}</span>
                      <span>{value !== null ? `${value}%` : '—'}</span>
                    </div>
                    <div className="h-2 rounded-full bg-neutral-200">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          value === null
                            ? 'bg-neutral-300'
                            : value >= 70
                              ? 'bg-emerald-500'
                              : value >= 40
                                ? 'bg-amber-500'
                                : 'bg-neutral-400'
                        )}
                        style={{ width: value !== null ? `${value}%` : '10%' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="primary"
              onClick={handleAccept}
              disabled={!ai || aiPending || uploadReview?.isConfirming}
            >
              Accept predictions
            </Button>
            {mode === 'edit' ? (
              <Button
                type="button"
                variant="secondary"
                onClick={handleConfirmEdits}
                disabled={isAwaitingPredictions || uploadReview?.isConfirming}
              >
                Confirm changes
              </Button>
            ) : (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setMode('edit')}
                disabled={isAwaitingPredictions || Boolean(uploadReview?.loading && !uploadReview?.ai)}
              >
                Edit & Confirm
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              onClick={handleCancel}
              disabled={isAwaitingPredictions}
            >
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadReviewPage;
