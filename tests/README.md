# Tests

This directory holds the IranRobot dev-loop test suites. They were originally drafted in `/tmp/` while Phases 3–7D were being implemented; this layout is the closeout move so the tests survive `/tmp` cleanup and can be diffed/reviewed in git.

There is **no test framework** here. Each suite is a self-contained script:

- E2E suites are puppeteer-core ESM modules — run with `node tests/e2e/<name>.mjs`.
- Backend HTTP smokes are bare-Python `http.client` scripts — run with `python3 tests/backend/<name>.py`.
- Staff-side bench smokes live in `backend/frappe-bench/apps/iranrobot_backend/iranrobot_backend/commands/_phase*_smoke.py` and are invoked with `bench --site iranrobot.localhost execute iranrobot_backend.commands._phaseXX_smoke.run_all`.

## Prerequisites

- bench/Frappe running at `http://iranrobot.localhost:8000`.
- Vite running at `http://localhost:5173` (from `frontend/iranrobot`, `npm run dev`).
- Google Chrome installed at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` — every E2E hard-codes this path.
- `customer1@example.com` / `ChangeMe-123` exists as a Website User on the site.

All commands below assume the working directory is the repo root (`/Users/pouyanshams/Desktop/iran-robota/`).

## First-time setup

Install `puppeteer-core` once for the E2E suites:

```bash
cd tests
npm install
cd ..
```

`tests/node_modules/` is gitignored; node's module resolution walks up from each `.mjs` and finds it automatically.

## Phase 7A E2E fixture (required before phase7a / phase7a1 E2E)

The Phase 7A puppeteer suite reads a deterministic fixture so it doesn't pick a quote that Phase 7B/7C/7D smokes may have mutated. Seed it once per dev session (or any time you want a fresh QR for that suite):

```bash
cd backend/frappe-bench
bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7_e2e_fixtures.seed_phase7a_e2e_fixture
```

The seeder:
- Submits a fresh quote as `customer1@example.com` (1 item: `aimoga-mornine`).
- Converts to a Quotation as Administrator.
- Sets `quotation_status="Sent"` on the Robot Quote Request so the customer-respond flow is unlocked.
- Writes `tests/artifacts/phase7a_e2e_fixture.json` with `qr_name`, `quotation_id`, `quotation_status`, `customer_email`.
- Refuses to run unless the active site is `iranrobot.localhost`.

The Phase 7A1 E2E reuses this same fixture (with an API-probe fallback if the file is missing).

> **Important — the fixture is single-use across a sweep.** The Phase 7B E2E picker accepts any `customer1` QR whose `quotation_status == "Sent"` and has no `customer_response` yet — which means it will consume the Phase 7A fixture if it runs after Phase 7A. Reseed before Phase 7A every time you intend to re-run it. The seeder always creates a brand-new QR; nothing to clean up.

## Running the suites

### E2E (puppeteer-core)

```bash
node tests/e2e/phase3_catalog.mjs          # Phase 3 catalog
node tests/e2e/phase4_auth.mjs             # Phase 4 auth (8/8)
node tests/e2e/phase45_signup.mjs          # Phase 4.5 signup (9/9)
node tests/e2e/phase5_intake.mjs           # Phase 5 intake (3/3)
node tests/e2e/phase6_dashboard.mjs        # Phase 6 dashboard (12/12)
node tests/e2e/phase7a_quotation.mjs       # Phase 7A — REQUIRES seeded fixture (10/10)
node tests/e2e/phase7a1_addresses.mjs      # Phase 7A.1 (13/13)
node tests/e2e/phase7b_respond.mjs         # Phase 7B respond (20/20)
node tests/e2e/phase7c_orders.mjs          # Phase 7C orders (17/17)
node tests/e2e/phase7d_invoices.mjs        # Phase 7D invoices (21/21)
```

Each suite writes screenshots to `tests/artifacts/<suite>/` (gitignored) and exits 0 on green, 1 on any failure.

### Backend HTTP smokes (Python http.client)

```bash
python3 tests/backend/phase45_smoke.py     # 15/15
python3 tests/backend/phase5_smoke.py      # 19/19
python3 tests/backend/phase7a_smoke.py     # 12/12
python3 tests/backend/phase7a1_smoke.py    # 12/12
python3 tests/backend/phase7c_smoke.py     # 10/10
python3 tests/backend/phase7d_smoke.py     # 8/8 bench + 12/12 HTTP
```

### Staff-side bench smokes (not in this tree)

These live in `backend/frappe-bench/apps/iranrobot_backend/iranrobot_backend/commands/`:

```bash
cd backend/frappe-bench
bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7a_smoke.run_all
bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7b_smoke.run_all
bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7c_smoke.run_all
bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7d_smoke.run_all
```

## Known limitations (out of scope for this closeout pass)

- Chrome executable path is hard-coded in every `.mjs` (`/Applications/Google Chrome.app/...`). Folding to an env var is a follow-up.
- Shared helpers (`dismissOnboarding`, `reactSet`, `snap`, `check`, the Python `Jar`/`request`/`check`) are duplicated across files. Consolidating them into `tests/lib/` is a follow-up.
- No test runner — suites are executed manually one at a time. Adding npm scripts (`test:e2e`, `test:backend`) is a follow-up.
- Suites mutate `customer1@example.com`'s data on the live `iranrobot.localhost` site. They are NOT isolated per run; reseed the fixture if assertions start looking off.
