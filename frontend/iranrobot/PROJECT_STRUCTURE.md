# IranRobot — Project Structure

A persistent snapshot of the codebase so a fresh session can pick up exactly where we left off.

---

## 1. Project goal

**IranRobot** is a Persian-first ecommerce frontend for **direct sales, custom procurement, and rental of physical robots** (industrial cobots, service bots, humanoids, AGVs/AMRs, drones, educational kits). It is *not* a marketplace — the company sells, sources, and rents from a single direct catalog.

Audience: enterprise buyers in Iran (Persian/RTL primary) and English-speaking sourcing teams (LTR). Design direction: premium light/dark hybrid (Apple/Tesla/B2B SaaS), brand red `#7F1810`, no neon.

---

## 2. Tech stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Framework | **React 19** | function components, hooks |
| Language | **TypeScript ~6.0.2** | `verbatimModuleSyntax`, `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly` |
| Bundler | **Vite 8** | `@vitejs/plugin-react` |
| Styling | **Tailwind CSS v4** (`@tailwindcss/vite`) | tokens in `@theme`, logical props (`start`/`end`, `ps`/`pe`) |
| Animation | **Framer Motion 12** | use sparingly, transform/opacity only |
| Icons | **lucide-react 1.16.0** | tree-shakable per-icon imports |
| Routing | **Custom hash router** | inside `AppContext`, no react-router |
| Persistence | **localStorage** via `lib/storage.ts` | prefix `iranrobot.v1.` |
| Tests | None yet | `npm run lint`, `npm run build` are the gates |

Single-file dev server: `npm run dev` (port 5173). Stale Vite processes can pile up on this port — `lsof -ti :5173` should return one PID.

---

## 3. Folder structure

```
iranrobot/
├── index.html                  ← <html lang="fa" dir="rtl">, Vazirmatn + Inter fonts
├── vite.config.ts              ← react() + tailwindcss()
├── tsconfig.app.json           ← strict TS
├── package.json
└── src/
    ├── main.tsx                ← createRoot + StrictMode + <App />
    ├── App.tsx                 ← <LanguageProvider><AppProvider><Shell /></AppProvider></LanguageProvider>
    ├── index.css               ← Tailwind + @theme tokens + utilities
    ├── types.ts                ← Lang, Robot, RobotCategory, CartLine, WalletTx, ProcurementRequest, RouteName
    ├── i18n.tsx                ← LanguageProvider, useI18n() — t/n/usd/toman/tomanRange/date/dateTime
    │
    ├── context/
    │   └── AppContext.tsx      ← AppProvider, useApp() — route, cart, wallet, onboarding, procurement
    │
    ├── data/
    │   ├── robots.ts           ← ROBOTS (8 mock products, fa+en) + CATEGORIES
    │   ├── categories.ts       ← PLP_CATEGORIES (10 categories with match predicates for the catalog filter)
    │   └── categoryCarousel.ts ← bento mosaic data + Solutions drill-down subs
    │
    ├── lib/
    │   ├── numerals.ts         ← toFa, toEn, localizeDigits, parseLocalizedNumber
    │   ├── format.ts           ← formatUsd/Toman/TomanRange/Number/Date/DateTime (all take Lang)
    │   └── storage.ts          ← loadJSON, saveJSON, removeKey, uid (all namespaced)
    │
    ├── components/             ← see §4
    └── views/                  ← see §5

public/
└── assets/
    ├── hero-robots-lineup.webp  ← homepage hero (RGBA cutout, already alpha-trimmed)
    └── categories/<id>.webp     ← bento mosaic per-category images
```

---

## 4. Important files — what each does

### Shell
- **`App.tsx`** — composes providers, renders `<Header/> <main><RouteSwitch/></main> <Footer/> <QuoteDrawer/> <OnboardingModal/>`. The shell has `overflow-x-hidden` so the wide hero image never causes horizontal scroll.
- **`main.tsx`** — boilerplate React 19 root.
- **`index.css`** — Tailwind v4. Defines the design tokens in `@theme`: brand ramp (`#7F1810` family — see §7), tech-blue/cyan, slate ink ramp, navy panel colors, soft shadows. Custom utilities: `glass-card`, `glass`, `glass-strong`, `glass-dark`, `surface-navy`, `surface-soft`, `text-gradient`, `text-gradient-light`, `text-gradient-brand`, `grid-floor`, `grid-faint`, animations (`float-slow`, `beam`, `pulse-glow`). Per-language font: `html[lang="en"]` switches to Inter.

### State / i18n
- **`i18n.tsx`** — `LanguageProvider` + `useI18n()`. Exposes `{ lang, dir, setLang, toggle, t(fa, en), n(num), usd, toman, tomanRange, date, dateTime }`. Persists `lang` to localStorage; sets `<html lang dir>` via effect. **Translation pattern: `t(faString, enString)` inline — no key dictionary.**
- **`context/AppContext.tsx`** — `AppProvider` + `useApp()`. Owns: hash-based `route`, `cart[]`, `cartOpen`, `walletBalanceUsd`, `walletTxs[]`, `procurementRequests[]`, `onboarding{Seen,Open}`. All slices persist to localStorage. Hash routes: `home`, `catalog`, `procurement`, `rent`, `finder`, `wallet`, `support`, `robot/<slug>`. Route param is passed via `go(name, param?)`. The robot detail uses `param` for the slug; the catalog uses `param` for a pre-selected PLP category id.

### Lib
- **`lib/numerals.ts`** — Persian ↔ western digit conversion; `parseLocalizedNumber` accepts either set; `localizeDigits(value, lang)` is the localizer.
- **`lib/format.ts`** — locale-aware money/date helpers. `USD_TO_TOMAN = 95_000`; `tomanRange` returns ±6 % band rounded to 100 000.
- **`lib/storage.ts`** — namespaced (`iranrobot.v1.`) JSON store. Also exports `uid(prefix?)` for ids.

### Data
- **`data/robots.ts`** — array of 8 mock `Robot`s. Each has fa + en versions of name, tagline, description, origin, specs, highlights. Also: `modes` (`buy`/`rent`/`procure`), `rentPerDayUsd`, `leadTimeDays`, `inStock`, `tags` (links robots to PLP categories), `accent` (legacy gradient string, currently unused), `rating`. `CATEGORIES` is the **6-id RobotCategory enum** used for `Robot.category` (industrial/service/humanoid/mobile/educational/drone).
- **`data/categories.ts`** — `PLP_CATEGORIES`: 10 storefront categories (solutions, humanoids, quadrupeds, amrs, cobots, drones, ugvs, accessories, regional, new) each with `match(robot)` predicate against `robot.tags`. **Used by the Catalog page (`CategoryGrid`).**
- **`data/categoryCarousel.ts`** — `categories[]` array used by the **homepage bento mosaic**. The `solutions` entry has a `subcategories` array (Agricultural / Commercial / Consumer / Educational / Government / Health Care / Industrial / Sports Robots) for the homepage drill-down. **Regional has been removed from this dataset.**

### Components
- **`Header.tsx`** — white sticky navbar, brand red logo, nav (`Home/Shop/Procurement/Rent/Finder/Support`), language toggle, wallet pill, cart pill, mobile drawer. **The Shop item is a pure-CSS group-hover/focus dropdown** that opens a single unified 860 px panel:
  - Left column (`280 px`): the 9 main categories + "View all categories" footer link.
  - Right column (`1fr`): always the **2-column subcategory grid** for the *active* category.
  - `activeCategoryId` state (default `'solutions'`); `onMouseEnter`/`onFocus` only update it when the hovered row has `subs` (Solutions/Humanoids/Quadrupeds/Accessories). Hovering AMRs/Cobots/Drones/UGVs/New Arrivals does *not* change the panel.
  - Mobile drawer: Shop expands to a flat list (no nested expansion).
- **`Footer.tsx`** — dark `bg-darksec` (`#111827`) grounding band with brand-red top hairline.
- **`Hero.tsx`** — homepage hero. White background, dark headline + brand-red accent, two CTAs. Robot lineup image (`<picture>`-less plain `<img>`) anchored bottom, `max-h` capped per breakpoint; perspective grid floor + soft glows + light beams as background layers.
- **`Section.tsx`** — reusable header (eyebrow + title + description + action) + wrapped content in `max-w-7xl mx-auto px-4 sm:px-6`.
- **`Button.tsx`** — 5 variants × 3 sizes. `rounded-lg`/`rounded-xl` only (no full-pill). Primary = brand-600.
- **`Badge.tsx`** — tones: `brand | tech | rent | neutral | success | warning | glass`.
- **`Input.tsx`** — `Input`, `Textarea`, `Select`, `NumberInput`. NumberInput uses `useI18n().lang` to render digits in the active language; `parseLocalizedNumber` accepts fa or en input.
- **`Drawer.tsx`** + **`Modal.tsx`** — white panels, scroll-lock, Escape-to-close, soft shadows.
- **`QuoteDrawer.tsx`** — the cart drawer. Shows lines, stepper, total in USD + Toman estimate, "Pay with wallet" path.
- **`OnboardingModal.tsx`** — 3-step intro, fires on first visit; dismissed flag persisted.
- **`RobotCard.tsx`** — premium product card; badges (موجود/پیش‌فروش + category + خرید/اجاره/تأمین), brand-red price, USD + Toman estimate, "Details" + "Add" CTAs.
- **`RobotIllustration.tsx`** — per-category SVG portrait (no stock photos). Pale gradient stage + slate strokes + brand/cyan accents.
- **`CategoryBentoSection.tsx`** — homepage editorial mosaic. **Full viewport width**, 12-col layout: row 1 `3/6/3` (Solutions / Humanoids featured / Quadrupeds), row 2 `6/6` (AMRs / Cobots), row 3 `3/3/3/3` (Drones / UGVs / Accessories / New Arrivals). `bg-slate-200` grid container with `gap-[3px]` produces hairline mosaic dividers. Drill-down state: clicking Solutions swaps the layout for its 8 subcategory tiles + a back button.
- **`CategoryBentoCard.tsx`** — flat tile: no border-radius, no shadow, image `object-cover` with hover-scale, dark gradient overlay, white title bottom-start, square arrow button bottom-end.
- **`CategoryCard.tsx`** + **`CategoryGrid.tsx`** — used **only by the Catalog page** (PLP). 5/2-3/1 col rounded white cards with active state. Filters the products list by `PLP_CATEGORIES[id].match(robot)`.

### Views
- **`Home.tsx`** — Hero → CategoryBentoSection → trust strip → value pillars → featured robots → CATEGORIES tiles → 3 engagement modes → Robot Finder CTA.
- **`Catalog.tsx`** — `CategoryGrid` PLP + search + mode segment (buy/rent/procure) + in-stock toggle + sort. Reads `route.param` to preselect `plpCategory` via state-from-prop pattern (no `useEffect`).
- **`Rent.tsx`** — robot picker, day/qty inputs, operator add-on, tiered discounts (4%/8%/15%), live USD + Toman total, navy summary card.
- **`Procurement.tsx`** — 3-step B2B quote wizard (product → commercial → contact). Submits a `ProcurementRequest` to AppContext (persisted). Side panel: recent requests + brand info card.
- **`Finder.tsx`** — 4-question wizard (use case / budget / mode / urgency) → top-3 scored recommendations via `scoreRobot`.
- **`Wallet.tsx`** — navy gradient balance card, presets, `NumberInput` for top-up, transaction history.
- **`Support.tsx`** — 3 contact channels, animated FAQ accordion, ticket form.
- **`RobotDetail.tsx`** — breadcrumbs, spec grid (bilingual `specs`/`specsEn`), highlights, sticky purchase panel with mode tabs + qty/days + total.

---

## 5. Routes / pages / components

Hash router. URL → view:

| Hash | View | Notes |
| --- | --- | --- |
| `#/` or `#/home` | `HomeView` | — |
| `#/catalog` | `CatalogView` | `route.param` optionally preselects PLP category |
| `#/procurement` | `ProcurementView` | — |
| `#/rent` | `RentView` | — |
| `#/finder` | `FinderView` | — |
| `#/wallet` | `WalletView` | — |
| `#/support` | `SupportView` | — |
| `#/robot/<slug>` | `RobotDetailView` | uses `route.param` for slug |

Navigation API: `useApp().go(name, param?)`.

---

## 6. State management / data / "API"

There is **no backend**. All "API" is in-memory data + localStorage.

| Slice | Where | Persistence key |
| --- | --- | --- |
| Language | `i18n.tsx` (`LanguageProvider`) | `iranrobot.v1.lang` |
| Route | `AppContext` (`hashchange`) | URL hash only |
| Cart | `AppContext.cart` | `iranrobot.v1.cart` |
| Wallet balance | `AppContext.walletBalanceUsd` | `iranrobot.v1.wallet.balance` |
| Wallet transactions | `AppContext.walletTxs` | `iranrobot.v1.wallet.txs` |
| Onboarding seen | `AppContext.onboardingSeen` | `iranrobot.v1.onboarding.seen` |
| Procurement requests | `AppContext.procurementRequests` | `iranrobot.v1.procurement` |
| Catalog filters | local `useState` in `CatalogView` | — (transient) |

The catalog "filter by category" wiring works in two directions: PLP card clicks set local state, AND `route.param` (set by the Header's Shop mega menu) syncs into local state via a state-from-prop check (no `useEffect`).

---

## 7. Naming conventions & coding rules

### Tokens (in `index.css`)
- `--color-brand-{50..950}` ramp around `#7F1810` (600 = primary, 700 = `#64120c` hover, 500 = `#a63a2e` light, 100 = `#fbe5e1` soft bg).
- Tech accents: `tech-blue` `#2563EB`, `tech-cyan` `#38BDF8`, `blue-soft` `#DBEAFE`.
- Page surfaces: `base` `#F8FAFC`, `base-2` `#EEF2F7`, `surface` `#FFFFFF`, `soft` `#F1F5F9`.
- Dark areas: `navy` `#08111F`, `navy-2` `#0F172A`, `darksec` `#111827`.
- Text: `fg` `#0F172A`, `muted` `#475569`, `faint` `#64748B`.
- Borders: `line` `#E2E8F0`, `line-strong` `#CBD5E1`.
- Shadows: `--shadow-soft`, `--shadow-soft-lg`, `--shadow-red`, `--shadow-blue`.

### Files
- Components & views: `PascalCase.tsx`, default export off the named function (`export function Header() {...}`).
- Views export `<Name>View`.
- Hooks: `use<Name>` from a single provider file.
- Data files: `camelCase.ts` exporting `UPPER_SNAKE_CASE` constants.

### Strings / numbers
- **Never inline literal Persian/English strings in a component where the other language is needed.** Always wrap with `t('fa…', 'en…')` from `useI18n()`.
- Numbers shown to users always go through `n(value)`, `usd(value)`, `toman(value)`, `tomanRange(value)`, `date(ts)`, `dateTime(ts)` from `useI18n()`. Do **not** call `lib/format` functions directly in components — always go through the context wrappers so digits localize.
- Persian digits look right with the `.num-fa` utility (font-feature-settings: ss01).

### Layout / RTL
- Prefer **logical Tailwind classes**: `ps-*`, `pe-*`, `ms-*`, `me-*`, `start-*`, `end-*`, `text-start`, `text-end`, `border-s`, `border-e`. They auto-mirror via `<html dir>`.
- Mirror icons with `rtl:-scale-x-100` or `rtl:rotate-180` instead of separate icons.
- Don't ship a `direction: ltr` override inside an RTL container without a real reason.

### React patterns
- TS strict mode is on; remove unused imports immediately.
- For "state derived from prop/route" sync, **do not** call `setState` inside `useEffect` (ESLint `react-hooks/set-state-in-effect` blocks this). Use the in-render pattern:
  ```ts
  const [tracked, setTracked] = useState(desired)
  if (desired !== tracked) {
    setTracked(desired)
    setLocalState(desired)
  }
  ```
- Use `motion.button` / `motion.div` from Framer Motion; cast props through `HTMLMotionProps<'…'>` when you also accept `onClick`/etc.
- Provider + hook colocation is intentional and uses `// eslint-disable-next-line react-refresh/only-export-components` where needed.

### Styling rules
- Buttons: `rounded-lg` or `rounded-xl` (never `rounded-full` on CTAs).
- Primary CTA: `bg-brand-600 hover:bg-brand-700 text-white`.
- Cards: `bg-white border border-line rounded-2xl shadow-soft`.
- Avoid heavy neon glows. Reserve red for CTAs / prices / brand highlights. Blue/cyan for tech accents only.
- The homepage **category mosaic** is intentionally **full viewport width**; all other sections are `max-w-7xl mx-auto px-6 lg:px-8`.

### Build hygiene
- Run `npm run build && npm run lint` before committing or saying "done".
- Multiple dev servers love to pile up on 5173 — kill duplicates if the page looks stale: `lsof -ti :5173 | xargs -r kill -9 && rm -rf node_modules/.vite && npm run dev`.

---

## 8. Current progress

### Done
1. Bilingual i18n (fa/en) — toggle in header, `<html dir lang>` syncs, fonts switch (Vazirmatn ↔ Inter), all 8 views translated, robot data fully bilingual.
2. Hero — white background, transparent robot lineup PNG/WebP cutout anchored bottom, capped `max-h` per breakpoint, controlled `min-h` (no `vw`-based padding that previously caused runaway height).
3. Light/dark hybrid design system — light page, dark navy header band, dark `darksec` footer, navy gradient accent cards (Wallet balance, Rent summary).
4. Homepage **bento mosaic** — full viewport width, 3-row 12-col bento, hairline dividers via `bg-slate-200 gap-[3px]`, flat tiles, dark overlay + bottom-left title + bottom-right square arrow, Solutions drill-down to 8 subcategories with a back button.
5. Catalog PLP — `CategoryGrid` (10 cards) + filter bar (search/mode/in-stock/sort). Pre-selection via `route.param`.
6. Rent calculator with tiered discounts; Procurement 3-step B2B wizard; Robot Finder 4-question scoring; Wallet with localStorage; Support FAQ + ticket; RobotDetail with mode tabs.
7. Persian numerals everywhere via i18n `n`/`usd`/`toman` helpers.
8. Brand color migrated to `#7F1810` (rose ramp replaced; all hex and Tailwind `rose-*` references removed; `rgba(225,29,72,*)` → `rgba(127,24,16,*)`).
9. White navbar with `rounded-lg` formal pills; mega-menu Shop dropdown landed on a **single unified 860 px panel**: 280 px main list + 1fr 2-column subcategory grid. Active state = brand-50 highlight; hover only updates the right panel when the row has subs.
10. Categories with subs in the Shop dropdown: **Solutions, Humanoids, Quadrupeds, Accessories**. The other 5 navigate but don't change the panel.

### Recent fix (last turn)
- Hover/focus on AMRs/Cobots/Drones/UGVs/New Arrivals previously overwrote the active subcategory panel with a "View category" CTA card. The handler is now gated by `if (hasSubs)`, and the unreachable CTA fallback was removed. The right pane is always the 2-column subs grid for the current active category (defaults to `solutions`).

---

## 9. Known bugs / quirks

- **Subcategory clicks navigate only to the parent category.** The PLP currently supports one filter level (`route.param` → `plpCategory`). Clicking *Education & Research* under Solutions goes to `/catalog?…=solutions`, not deeper. Plumbing a second-level filter (`?solution=education`) requires updates to `Catalog.tsx` and the route schema.
- **`Robot.accent`** field is dead data (legacy gradient string, no consumer). Safe to delete during a cleanup.
- **Translation has no dictionary** — every call site repeats both strings. Easy to mistype. There is no fa-en parity check.
- **Mobile drawer Shop section is flat** — no nested accordion. Acceptable for now per the latest user direction.
- **Stale Vite servers** can persist on 5173 across sessions; the running PID changes each restart. If a change "doesn't show", run the kill-and-restart command from §7.
- **Hero PNG fallback was discarded** when the user switched to the cropped WebP. Only `hero-robots-lineup.webp` is in `public/assets/`; the `<picture>`/PNG fallback was removed.
- **`useEffect → setState` is banned by lint.** Use the state-from-prop pattern instead (see §7).
- **Mega-menu submenu** went through many positioning iterations (`start-full`, `right-full`, translate, `w-fit` wrappers). The final answer was **scrap floating submenus entirely** and render subs inside the same dropdown panel. Don't revert to floating.

---

## 10. Next tasks (suggestions in priority order)

1. **Real subcategory filtering.** Extend the catalog route to accept a second key (e.g. `route.param = 'solutions:education'` or add a `route.query` field) and update PLP filtering to honor it. Updates to: `AppContext.RouteState`, `CatalogView` (state-from-prop), Header sub click handlers.
2. **Real product photography** to replace `RobotIllustration.tsx`. The component exposes a clean prop boundary; swap SVG → `<img>` per robot.
3. **Per-category images for the homepage bento** are already wired (`/assets/categories/<id>.webp` is referenced) — make sure all 10 files are present in `public/assets/categories/`. Currently confirmed: accessories, amrs, cobots, drones, humanoids, new-arrivals, quadrupeds, solutions, ugvs. Missing if you want it: none (Regional was deleted from the dataset).
4. **Solutions drill-down images** — `/assets/solutions/<id>.webp` paths are declared in `data/categoryCarousel.ts` for the 8 subcategories. Add the files when ready.
5. **Tests.** No test framework is set up. Add Vitest + React Testing Library if going beyond a demo.
6. **Mobile mega-menu parity.** The current mobile Shop is a flat accordion of all 9 categories. If users want nested subs on mobile, add a second-level expand for Solutions/Humanoids/Quadrupeds/Accessories.
7. **Accessibility audit pass.** Most overlays have `aria-modal`/`role="dialog"`; the mega menu uses `role="menu"`/`role="menuitem"`. Keyboard navigation (arrow keys inside the menu) is not implemented.
8. **Magic MCP + ui-ux-pro-max skill** are installed but require a Claude Code restart to activate. After restart, they can audit/improve specific premium components (mega menu, product gallery, pricing).
9. **Optional: split provider + hook** out of `i18n.tsx` and `AppContext.tsx` into separate files to remove the `eslint-disable react-refresh/only-export-components` comments. Cosmetic, not functional.

---

*Generated as a session hand-off. Do not edit this file's "Done" list directly — re-generate on demand.*
