type EventName = 'upload_started' | 'upload_succeeded' | 'item_edited' | 'item_deleted';

type EventPayload = Record<string, unknown> | undefined;

const log = (event: EventName, payload: EventPayload): void => {
  const timestamp = new Date().toISOString();
  console.info(`[styleus:${event}]`, { timestamp, ...payload });
};

export type Logger = {
  uploadStarted: (payload?: EventPayload) => void;
  uploadSucceeded: (payload?: EventPayload) => void;
  itemEdited: (payload?: EventPayload) => void;
  itemDeleted: (payload?: EventPayload) => void;
};

export const logger: Logger = {
  uploadStarted(payload?: EventPayload) {
    log('upload_started', payload);
  },
  uploadSucceeded(payload?: EventPayload) {
    log('upload_succeeded', payload);
  },
  itemEdited(payload?: EventPayload) {
    log('item_edited', payload);
  },
  itemDeleted(payload?: EventPayload) {
    log('item_deleted', payload);
  }
};
