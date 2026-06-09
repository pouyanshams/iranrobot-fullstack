# iranrobot_backend / scripts

Tooling that doesn't ship with the Frappe app at runtime — used to maintain seed data.

## `export_catalog.mts`

Re-generates `iranrobot_backend/data/catalog_snapshot.json` from the frontend's TypeScript source of truth (`iranrobot/src/data/robots.ts` + `categories.ts`).

Run from the `iranrobot_backend` repo root:

```bash
npx --yes tsx scripts/export_catalog.mts
```

Requires Node 18+ and (one-time) network access for `npx` to fetch `tsx`. Subsequent runs use the npm cache.

Re-run whenever `robots.ts` changes. The Python seed (`iranrobot_backend.commands.seed_catalog.run`) reads the snapshot, not the TS file, so the snapshot is the contract between frontend data and Frappe import.
