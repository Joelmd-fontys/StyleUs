import '@testing-library/jest-dom';
import { afterAll, afterEach, beforeAll } from 'vitest';

interface StorageLike {
  clear(): void;
  getItem(key: string): string | null;
  key(index: number): string | null;
  removeItem(key: string): void;
  setItem(key: string, value: string): void;
  readonly length: number;
}

const createStorageMock = (): StorageLike => {
  const values = new Map<string, string>();
  return {
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
    get length() {
      return values.size;
    }
  };
};

const ensureStorage = (): void => {
  if (typeof globalThis.localStorage?.getItem === 'function') {
    return;
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: createStorageMock(),
    configurable: true
  });
};

let resetMockServerState = (): void => {};
let server: { close(): void; listen(options: { onUnhandledRequest: 'error' }): void } | null = null;

beforeAll(async () => {
  ensureStorage();
  const mockServer = await import('../mocks/server');
  resetMockServerState = mockServer.resetMockServerState;
  server = mockServer.server;
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  resetMockServerState();
});

afterAll(() => {
  server?.close();
});
