# Seed Module

The seed module hydrates a local StyleUs instance with a deterministic set of
wardrobe items. Sources live in `seed_sources.yaml` and reference images bundled
under `sample_images/` so no scraping or external downloads are required.

## Environment Flags

- `RUN_SEED_ON_START` – defaults to `true` in `APP_ENV=local`, otherwise `false`.
  When enabled, the API seeds exactly once on startup.
- `SEED_LIMIT` – maximum number of seed items to apply (default `25`).
- `SEED_KEY` – logical identifier stored in the `seeds` table to ensure
  idempotency (default `local-seed-v1`). Change the key to run a new dataset.

`SEED_ON_START` is still accepted as a legacy alias for local compatibility, but
`RUN_SEED_ON_START` is the canonical name going forward.

## Commands

```bash
make seed         # run the seeding pipeline immediately
make reset-seed   # delete seeded items and the marker for a clean reseed
```

Both commands reuse the configured environment variables. `make reset-seed`
removes local media generated for the seeded wardrobe entries so subsequent
runs produce fresh variants.

## Notes

- The dataset is curated and deterministic; no runtime scraping occurs.
- All images are bundled assets licensed for unrestricted local development
  usage.
- Idempotency is tracked via the `seeds` table—repeat runs skip once the key is
  recorded. Set `RUN_SEED_ON_START=false` to suppress auto-seeding.
