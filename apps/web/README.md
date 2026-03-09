# Web App

The web client is a Vite + React + TypeScript application for browsing a wardrobe, uploading new items, reviewing AI suggestions, and editing saved garments.

## Stack

- React 18
- React Router
- Zustand
- Tailwind CSS
- MSW for optional mock-mode API handling
- Vitest + Testing Library

## Local development

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Default dev URL: `http://127.0.0.1:5173`

## Routes

- `/` – dashboard with counts and recent uploads
- `/wardrobe` – wardrobe grid, filters, and upload panel
- `/items/:id` – item detail/edit page
- `/upload/review/:id` – AI review flow after upload completion
- `/outfits` – placeholder page
- `/settings` – local-only preferences plus placeholder settings

## Architecture

### State

The main app state lives in `src/store/wardrobe.ts`. It owns:

- wardrobe items
- loading and error states
- filters
- selected item
- upload review state
- flash messages

### API integration

The app talks to the backend through `src/lib/api.ts`.

- item listing, detail, update, delete, and AI preview all use JSON `fetch` calls
- uploads use `POST /items/presign`, a binary `PUT`, then `POST /items/{id}/complete-upload`

### Mock vs live mode

Environment flags decide whether the app uses the live API or MSW mocks:

- `VITE_USE_LIVE_API_ITEMS`
- `VITE_USE_LIVE_API_UPLOAD`

If either flag is `false`, the MSW worker starts from `src/mocks/browser.ts`.

## Upload and review flow

1. `UploadPanel` validates the file client-side.
2. The client asks the API for an upload slot.
3. The file is uploaded to either:
   - a local API upload endpoint, or
   - an S3 presigned URL.
4. The client completes the upload and stores the returned item in the review state.
5. The app navigates to `/upload/review/:id`.
6. The review page fetches AI preview data, lets the user accept or edit it, then saves through `PATCH /items/:id`.

## File guide

- `src/App.tsx` – route tree
- `src/components/UploadPanel.tsx` – upload entrypoint
- `src/pages/UploadReviewPage.tsx` – upload review flow
- `src/pages/Wardrobe.tsx` – wardrobe grid and upload sidebar
- `src/pages/ItemDetail.tsx` – item edit/delete view
- `src/store/wardrobe.ts` – shared application state
- `src/mocks/handlers.ts` – MSW mock API behavior

## Environment

- `VITE_API_BASE_URL` – API origin, default `http://127.0.0.1:8000`
- `VITE_USE_LIVE_API_ITEMS` – use the live API for wardrobe CRUD
- `VITE_USE_LIVE_API_UPLOAD` – use the live API for upload/presign flow

## Scripts

- `npm run dev` – start Vite with HMR
- `npm run build` – production build
- `npm run preview` – preview production build
- `npm run typecheck` – TypeScript in `--noEmit` mode
- `npm run lint` – Prettier formatting check
- `npm run format` – Prettier write
- `npm test` – run Vitest once
- `npm run test:watch` – watch mode
- `npm run msw:gen` – generate the MSW service worker file

## Notes

- The upload review screen is fully wired to the backend flow.
- The dashboard and wardrobe flows are live when the item API flag is enabled.
- `Outfits` and most settings remain intentionally incomplete product surfaces.
