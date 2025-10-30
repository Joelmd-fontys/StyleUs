# Web App

Vite + React + TypeScript client for StyleUs. The UI uses Tailwind for styling, React Router for navigation, Zustand for state, and MSW for local mocks that can be toggled off when hitting the live API.

## Requirements

- Node.js 20+

## Getting Started

```bash
cd apps/web
npm install
cp .env.example .env.local  # adjust API base or feature flags as needed
npm run dev
```

The app expects the API on `http://127.0.0.1:8000` by default. Update `VITE_API_BASE_URL` in `.env.local` if the backend runs elsewhere.

## Available Scripts

- `npm run dev` – launch the Vite dev server with hot module reload.
- `npm run build` – produce a production build in `dist/`.
- `npm run preview` – preview the production build locally.
- `npm run typecheck` – run the TypeScript compiler in `--noEmit` mode.
- `npm run msw:gen` – install the service worker used for local API mocks.

## Feature Flags & API Usage

Environment variables (see `.env.example`):

- `VITE_API_BASE_URL` – base URL for all API calls. `resolveApiUrl` normalizes paths so local relative URLs work.
- `VITE_USE_LIVE_API_ITEMS` – when `true`, wardrobe list/detail/edit requests consult the FastAPI service; otherwise MSW serves fixtures.
- `VITE_USE_LIVE_API_UPLOAD` – when `true`, the upload flow calls the real `/items/presign` + upload endpoints; otherwise it stays in mock mode.

When live flags are `true`, the MSW worker stays idle and built-in fetch helpers talk to the backend using the contracts in `src/domain/contracts.ts`.

## Project Structure Highlights

- `src/pages` – route-level screens (dashboard, wardrobe list, detail view).
- `src/components` – shared UI building blocks (cards, filters, upload panel, dialogs).
- `src/store` – Zustand store coordinating wardrobe data and feature flows.
- `src/lib` – API client, config helpers, and utility modules.
- `src/mocks` – MSW handlers and fixtures used when feature flags disable live endpoints.

## Testing & Quality

Type safety is enforced via `npm run typecheck`. The project relies on the backend test suite; no frontend tests ship yet.
