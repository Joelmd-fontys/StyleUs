import { setupWorker } from 'msw/browser';
import { handlers, resetMockState } from './handlers';

export const worker = setupWorker(...handlers);

export const startWorker = async () => {
  resetMockState();
  await worker.start({
    onUnhandledRequest: 'bypass'
  });
  return worker;
};
