# Web App

Vite + React + TypeScript client for StyleUs. The UI uses Tailwind for styling, React Router for navigation, Zustand for state, and MSW for optional local mocks.

## Requirements
- Node.js 20+

## Getting started
```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev          # http://127.0.0.1:5173
```

## Environment
- `VITE_API_BASE_URL` – API origin (default `http://127.0.0.1:8000`)
- `VITE_USE_LIVE_API_ITEMS` – when `true`, wardrobe list/detail/edit calls hit the API
- `VITE_USE_LIVE_API_UPLOAD` – when `true`, upload/presign calls hit the API

The MSW worker only starts when either live flag is `false`; otherwise it stays disabled.

## Available scripts
- `npm run dev` – Vite dev server with HMR
- `npm run build` / `npm run preview` – production build + preview
- `npm run typecheck` – TypeScript in `--noEmit` mode
- `npm run lint` – Prettier formatting check
- `npm run format` – Prettier write
- `npm test` – `vitest run`
- `npm run test:watch` – watch mode for tests
- `npm run msw:gen` – install the MSW service worker

## Upload review flow
After upload completion the app routes to **Upload Review**, showing AI suggestions (category, colors, tags) next to the preview image. Users can accept everything or edit before confirming. Confirmation saves the item into the wardrobe and shows a flash message; canceling discards the placeholder item and returns to the grid.

## Feature flags & API usage
- `resolveApiUrl` normalizes API URLs based on `VITE_API_BASE_URL`.
- When live flags are `true`, API calls use `fetch` helpers and the MSW worker is idle.
- When mocks are enabled, handlers live in `src/mocks/handlers.ts` and fixtures in `src/mocks/fixtures.ts`.
