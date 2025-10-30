import { setupWorker, type SetupWorker } from 'msw/browser';
import { handlers, resetMockState } from './handlers';

export const worker: SetupWorker = setupWorker(...handlers);

export const startWorker = async (): Promise<SetupWorker> => {
  resetMockState();
  await worker.start({
    onUnhandledRequest: 'bypass'
  });
  return worker;
};
