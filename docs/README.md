# Documentation

This directory contains supporting product and technical notes for the StyleUs repository.

## How to use this folder

- Start with the root [README.md](../README.md) for the current product and local setup.
- Use [docs/tech-stack.md](./tech-stack.md) for the stack decisions currently in effect.
- Use [docs/config/environments.md](./config/environments.md) for environment tiers, variable ownership, and startup rules.
- Use [docs/architecture/deployment.md](./architecture/deployment.md) for the target Vercel + Render + Supabase platform split.
- Use [recap.md](../recap.md) for the latest repository cleanup and status summary.

Many implementation details now live closest to the code:

- frontend runtime and flow details: [apps/web/README.md](../apps/web/README.md)
- backend runtime, routes, upload pipeline, and AI flow: [services/api/README.md](../services/api/README.md)
