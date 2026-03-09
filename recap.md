# Recap

## What was cleaned up

- Rewrote the main repository READMEs so they match the code that actually exists today.
- Replaced several placeholder-style docs with concrete pointers to the frontend and backend runtime docs.
- Centralized frontend category option lists and shared display-label formatting to reduce duplication across wardrobe and upload-review screens.
- Refactored backend item serialization and AI preview shaping into smaller helper functions for readability.

## What was simplified

- Shared frontend category configuration now lives in `apps/web/src/domain/labels.ts`.
- The upload review and item detail pages now rely on the same label formatting helper instead of duplicating local string utilities.
- Backend `to_item_detail` and `to_ai_preview` logic is broken into explicit helper steps so media metadata, AI attributes, and pipeline overlays are easier to follow.

## What was removed

- Unused frontend label exports that were no longer referenced anywhere in the web app.
- Dead backend helpers that were not used by the runtime path:
  - `build_local_media_url`
  - `get_session`
  - the top-level `is_s3_enabled()` wrapper function

## What remains potentially fragile

- The AI preview endpoint still mixes persisted AI fields with a fresh on-demand pipeline pass. That is intentional today, but it remains a conceptual edge in the design.
- The prototype still uses a fixed stub user ID rather than a real auth/user model.
- The frontend supports both live and mock API modes, which is useful for development but adds branching complexity to shared flows.
- The backend test setup still depends on a reachable Postgres instance rather than a lighter isolated test database.
