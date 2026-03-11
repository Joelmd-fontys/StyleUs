# Web App

The web client handles wardrobe browsing, upload initiation, AI review, and item editing. It talks to the API through `src/lib/api.ts` and uses Supabase only for browser auth and direct signed uploads.

## Structure

- `src/pages` - route-level screens
- `src/components` - shared UI building blocks
- `src/store/wardrobe.ts` - app state and async actions
- `src/lib` - API client, config, media helpers, validation, and logging
- `src/auth` - Supabase session handling and the auth gate
- `src/mocks` - MSW handlers for local mock mode

## Routes

- `/` - dashboard
- `/wardrobe` - wardrobe list, filters, and upload entry point
- `/items/:id` - item detail and edit flow
- `/upload/review/:id` - AI review flow
- `/outfits` - placeholder
- `/settings` - local preferences and placeholder settings

## Local development

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Default dev URL: `http://127.0.0.1:5173`

## Environment variables

- `VITE_APP_ENV` - `local`, `staging`, or `production`
- `VITE_API_BASE_URL` - API origin; defaults to localhost only in `local`
- `VITE_SUPABASE_URL` - public Supabase project URL
- `VITE_SUPABASE_PUBLISHABLE_KEY` - preferred public browser key
- `VITE_SUPABASE_ANON_KEY` - legacy alias still accepted
- `VITE_USE_LIVE_API_ITEMS` - use the real wardrobe API instead of MSW
- `VITE_USE_LIVE_API_UPLOAD` - use the real upload flow instead of MSW

If the Supabase variables are omitted, the app stays in local guest mode and depends on the API's `LOCAL_AUTH_BYPASS=true` path. Hosted environments should always set the public Supabase variables.

## Upload and review flow

1. `UploadPanel` validates the file and requests `POST /items/presign`.
2. The browser uploads directly to the signed Supabase Storage target.
3. The browser calls `POST /items/{id}/complete-upload`.
4. The app navigates to `/upload/review/:id`.
5. The review page polls `GET /items/{id}/ai-preview`.
6. The user accepts or edits the AI result, then saves through `PATCH /items/{id}`.

## Scripts

- `npm run dev`
- `npm run build`
- `npm run preview`
- `npm run typecheck`
- `npm run lint`
- `npm run format`
- `npm test`
- `npm run test:watch`
- `npm run msw:gen`

See also:

- [../../docs/config/environments.md](../../docs/config/environments.md)
- [../../docs/architecture/deployment.md](../../docs/architecture/deployment.md)
