import { setupServer, type SetupServer } from 'msw/node';
import { handlers, resetMockState } from './handlers';

export const server: SetupServer = setupServer(...handlers);

export const resetMockServerState = (): void => {
  server.resetHandlers();
  resetMockState();
};
