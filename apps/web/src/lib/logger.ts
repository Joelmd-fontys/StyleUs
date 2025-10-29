type EventName = 'upload_started' | 'upload_succeeded' | 'item_edited' | 'item_deleted';

type EventPayload = Record<string, unknown> | undefined;

const log = (event: EventName, payload: EventPayload) => {
  const timestamp = new Date().toISOString();
  // eslint-disable-next-line no-console
  console.info(`[styleus:${event}]`, { timestamp, ...payload });
};

export const logger = {
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
