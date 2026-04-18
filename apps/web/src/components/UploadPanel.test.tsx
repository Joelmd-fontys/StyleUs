import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WardrobeItem } from '../domain/types';
import UploadPanel from './UploadPanel';
import { useWardrobeStore } from '../store/wardrobe';

const { navigateMock, createPresignMock, uploadFileMock, completeUploadMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  createPresignMock: vi.fn(),
  uploadFileMock: vi.fn(),
  completeUploadMock: vi.fn()
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock
  };
});

vi.mock('../lib/config', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/config')>();
  return {
    ...actual,
    USE_LIVE_API_UPLOAD: false
  };
});

vi.mock('../lib/api', () => ({
  createPresign: createPresignMock,
  uploadFile: uploadFileMock,
  completeUpload: completeUploadMock
}));

const baseState = useWardrobeStore.getState();

const uploadedItem: WardrobeItem = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  imageUrl: '/image.jpg',
  thumbUrl: '/thumb.jpg',
  mediumUrl: '/medium.jpg',
  category: 'top',
  subcategory: 't-shirt',
  color: 'blue',
  brand: 'Mock Brand',
  createdAt: new Date().toISOString(),
  tags: []
};

describe('UploadPanel', () => {
  beforeEach(() => {
    navigateMock.mockReset();
    createPresignMock.mockReset();
    uploadFileMock.mockReset();
    completeUploadMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    useWardrobeStore.setState(baseState, true);
  });

  it('prepares review after mock upload finalization completes', async () => {
    const prepareUploadReviewMock = vi.fn();
    const fetchUploadReviewAIMock = vi.fn().mockResolvedValue(undefined);
    const clearUploadReviewMock = vi.fn();

    useWardrobeStore.setState((state) => ({
      ...state,
      prepareUploadReview: prepareUploadReviewMock,
      fetchUploadReviewAI: fetchUploadReviewAIMock,
      clearUploadReview: clearUploadReviewMock,
      showFlashMessage: vi.fn()
    }));

    createPresignMock.mockResolvedValue({
      uploadUrl: '/_uploads/123e4567-e89b-12d3-a456-426614174000',
      itemId: uploadedItem.id
    });
    uploadFileMock.mockResolvedValue(undefined);
    completeUploadMock.mockResolvedValue(uploadedItem);

    const { container } = render(
      <MemoryRouter>
        <UploadPanel />
      </MemoryRouter>
    );

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    const file = new File(['image-bytes'], 'look.png', { type: 'image/png' });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() => expect(createPresignMock).toHaveBeenCalledTimes(1));
    expect(createPresignMock).toHaveBeenCalledWith({
      contentType: 'image/png',
      fileName: 'look.png',
      fileSize: file.size
    });
    expect(uploadFileMock).toHaveBeenCalledWith('/_uploads/123e4567-e89b-12d3-a456-426614174000', file, {
      isLocal: true,
      fileName: 'look.png',
      objectKey: undefined,
      uploadToken: undefined,
      bucket: undefined
    });
    expect(completeUploadMock).toHaveBeenCalledWith(uploadedItem.id, { fileName: 'look.png' });
    expect(clearUploadReviewMock).toHaveBeenCalledTimes(1);
    expect(prepareUploadReviewMock).toHaveBeenCalledWith(uploadedItem);
    expect(fetchUploadReviewAIMock).toHaveBeenCalledWith(uploadedItem.id);
    expect(navigateMock).toHaveBeenCalledWith(`/upload/review/${uploadedItem.id}`);
  });

  it('rejects non-image files without leaving the wardrobe route', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      prepareUploadReview: vi.fn(),
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      clearUploadReview: vi.fn(),
      showFlashMessage: vi.fn()
    }));

    const { container } = render(
      <MemoryRouter>
        <UploadPanel />
      </MemoryRouter>
    );

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    const file = new File(['not-an-image'], 'README.md', { type: 'text/markdown' });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    expect(await screen.findByText('Only image files are supported.')).toBeInTheDocument();
    expect(createPresignMock).not.toHaveBeenCalled();
    expect(uploadFileMock).not.toHaveBeenCalled();
    expect(completeUploadMock).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
