import { ChangeEvent, DragEvent, useRef, useState } from 'react';
import Button from './Button';
import { logger } from '../lib/logger';
import { completeUpload, createPresign, uploadFile } from '../lib/api';
import { useWardrobeStore } from '../store/wardrobe';
import { cn } from '../lib/utils';
import { USE_LIVE_API_UPLOAD } from '../lib/config';
import { CompleteUploadRequest } from '../domain/contracts';

interface UploadState {
  status: 'idle' | 'uploading' | 'success' | 'error';
  message?: string;
}

const MAX_FILE_SIZE_MB = 15;
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;

const UploadPanel = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [state, setState] = useState<UploadState>({ status: 'idle' });
  const loadItems = useWardrobeStore((store) => store.loadItems);

  const resetMessage = () => {
    window.setTimeout(() => {
      setState((current) => (current.status === 'success' ? { status: 'idle' } : current));
      setProgress(0);
    }, 2500);
  };

  const simulateProgress = () => {
    setProgress(10);
    const interval = window.setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          window.clearInterval(interval);
          return prev;
        }
        return prev + 10;
      });
    }, 150);
    return () => window.clearInterval(interval);
  };

  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setState({ status: 'error', message: 'Only image files are supported.' });
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setState({ status: 'error', message: `File must be smaller than ${MAX_FILE_SIZE_MB}MB.` });
      return;
    }

    setState({ status: 'uploading', message: `Preparing ${file.name}...` });
    logger.uploadStarted({ name: file.name, size: file.size });
    const stopProgress = simulateProgress();

    try {
      setState({ status: 'uploading', message: 'Requesting upload slot...' });
      const { uploadUrl, itemId, objectKey } = await createPresign({
        contentType: file.type,
        fileName: file.name
      });
      const isLocalUpload = Boolean(!objectKey || uploadUrl.startsWith('/items/uploads/'));

      const uuidPattern = /^[0-9a-fA-F-]{36}$/;
      let resolvedItemId = itemId;
      if (!uuidPattern.test(resolvedItemId)) {
        const fromUrl = uploadUrl.split('/').pop() ?? '';
        if (uuidPattern.test(fromUrl)) {
          resolvedItemId = fromUrl;
        }
      }
      if (!uuidPattern.test(resolvedItemId)) {
        throw new Error('Upload failed to return a valid item identifier. Please retry.');
      }
      setState({ status: 'uploading', message: 'Uploading image...' });
      setProgress((prev) => Math.max(prev, 40));
      await uploadFile(uploadUrl, file, { isLocal: isLocalUpload, fileName: file.name });
      setState({ status: 'uploading', message: 'Finalizing upload...' });
      const completePayload: CompleteUploadRequest = { fileName: file.name };
      if (!isLocalUpload && objectKey) {
        completePayload.objectKey = objectKey;
      }
      await completeUpload(resolvedItemId, completePayload);
      stopProgress();
      setProgress(100);
      setState({ status: 'success', message: `${file.name} uploaded.` });
      logger.uploadSucceeded({ itemId, mode: isLocalUpload ? 'local' : 's3' });
      await loadItems();
      resetMessage();
    } catch (error) {
      stopProgress();
      const message = error instanceof Error ? error.message : 'Upload failed.';
      setState({ status: 'error', message });
    }
  };

  const onInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await handleFile(file);
    event.target.value = '';
  };

  const onDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (!file) {
      return;
    }
    await handleFile(file);
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  };

  const onDragLeave = () => setIsDragging(false);

  const isUploading = state.status === 'uploading';

  return (
    <section
      id="upload-panel"
      className="rounded-2xl border border-dashed border-neutral-300 bg-white/80 p-6 text-center shadow-sm backdrop-blur"
      aria-live="polite"
    >
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-neutral-300 p-6 transition',
          isDragging ? 'border-accent-600 bg-accent-600/10' : 'bg-neutral-50'
        )}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            fileInputRef.current?.click();
          }
        }}
        aria-label="Upload wardrobe item"
      >
        <p className="text-sm font-semibold text-neutral-900">Upload a new item</p>
        <p className="max-w-sm text-xs text-neutral-500">
          Drag and drop an image or select a file. Supported formats: JPG, PNG, WEBP. Maximum size: {MAX_FILE_SIZE_MB}
          MB.
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          Choose File
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={onInputChange}
          disabled={isUploading}
        />
      </div>

      {isUploading ? (
        <div className="mt-4 w-full">
          <div className="h-2 overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full bg-accent-600 transition-all"
              style={{ width: `${progress}%` }}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              role="progressbar"
            />
          </div>
        </div>
      ) : null}

      {state.message ? (
        <p
          className={`mt-3 text-sm ${
            state.status === 'error' ? 'text-danger-500' : 'text-success-500'
          }`}
        >
          {state.message}
        </p>
      ) : (
        <p className="mt-3 text-xs text-neutral-400">
          {USE_LIVE_API_UPLOAD
            ? 'Uploads are sent to the live API.'
            : 'Uploads are mocked locally.'}
        </p>
      )}
    </section>
  );
};

export default UploadPanel;
