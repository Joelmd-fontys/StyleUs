# Web App

The web client is a Vite + React + TypeScript application for browsing a wardrobe, uploading new items, reviewing AI suggestions, and editing saved garments.

## Stack

- React 18
- React Router
- Zustand
- Tailwind CSS
- MSW for optional mock-mode API handling
- Vitest + Testing Library

## Routes

- `/` - dashboard with counts and recent uploads
- `/wardrobe` - wardrobe grid, filters, and upload panel
- `/items/:id` - item detail/edit page
- `/upload/review/:id` - AI review flow after upload completion
- `/outfits` - placeholder page
- `/settings` - local-only preferences plus placeholder settings

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

- item listing, detail, update, delete, and AI preview use JSON `fetch` calls
- uploads use `POST /items/presign`, a binary `PUT`, then `POST /items/{id}/complete-upload`

### Mock vs live mode

Environment flags decide whether the app uses the live API or MSW mocks:

- `VITE_USE_LIVE_API_ITEMS`
- `VITE_USE_LIVE_API_UPLOAD`

If either flag is `false`, the MSW worker starts from `src/mocks/browser.ts`.

## Environment model

The frontend now has an explicit app environment:

- `VITE_APP_ENV=local`
- `VITE_APP_ENV=staging`
- `VITE_APP_ENV=production`

Local development reads from `apps/web/.env.local`.

Hosted environments are intended to read from Vercel-managed environment variables. Only public, browser-safe variables should be exposed here.

### Current variables

- `VITE_APP_ENV` - frontend runtime environment
- `VITE_API_BASE_URL` - API origin; defaults to `http://127.0.0.1:8000` only in local development
- `VITE_USE_LIVE_API_ITEMS` - use the live API for wardrobe CRUD
- `VITE_USE_LIVE_API_UPLOAD` - use the live API for upload/presign flow

### Reserved for later phases

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Those Supabase variables are documented now so the platform boundary is explicit, but the current app does not use them yet.

## Local development

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Default dev URL: `http://127.0.0.1:5173`

## Upload and review flow

1. `UploadPanel` validates the file client-side.
2. The client asks the API for an upload slot.
3. The file is uploaded to either:
   - a local API upload endpoint, or
   - an S3 presigned URL.
4. The client completes the upload and stores the returned item in the review state.
5. The app navigates to `/upload/review/:id`.
6. The review page fetches AI preview data, lets the user accept or edit it, then saves through `PATCH /items/:id`.

## Platform boundary

### Local today

- The web app runs from Vite on the developer machine.
- It talks to the FastAPI API directly.
- It can switch between live API calls and MSW mocks for development.

### Target hosted shape

- Vercel hosts the built SPA.
- The SPA talks to the FastAPI API on Render.
- Supabase client configuration will later be exposed through public Vercel env vars for authentication only.

The frontend should know:

- public API base URL
- public auth/session configuration
- local-only mock flags when developing

The frontend should not know:

- database credentials
- storage secrets
- service-role keys
- backend-only infrastructure secrets

## Scripts

- `npm run dev` - start Vite with HMR
- `npm run build` - production build
- `npm run preview` - preview production build
- `npm run typecheck` - TypeScript in `--noEmit` mode
- `npm run lint` - Prettier formatting check
- `npm run format` - Prettier write
- `npm test` - run Vitest once
- `npm run test:watch` - watch mode
- `npm run msw:gen` - generate the MSW service worker file

## What remains for later phases

Not implemented yet:

- Supabase Auth in the browser
- production storage integration
- Vercel deployment rollout
- any major frontend architecture rewrite

See also:

- [../../docs/config/environments.md](../../docs/config/environments.md)
- [../../docs/architecture/deployment.md](../../docs/architecture/deployment.md)
