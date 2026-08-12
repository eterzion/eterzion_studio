# Research & Audit: Interface Design System

Phase 0 output for `/speckit.plan`. All findings below come from a real code audit (not assumed),
performed against the repository at the time of writing. File:line citations are preserved so
`/speckit.tasks` and `/speckit.implement` can verify them independently.

## Audit (a) — UI duplication

**Confirmed, real, cross-file duplication** (the only categories that justify creating a
consolidated component per constitution Principle X v2.4.0):

| Pattern | Evidence | Verdict |
|---|---|---|
| Buttons | ~20 distinct button class names across 15+ files (`.primary-btn`, `.icon-btn`, `.btn-outline`, `.btn-primary`/`.btn-secondary`, `.secondary-btn`, `.danger-btn`, `.copy-btn`, etc.), several independently styled with different sizing/colors for the same visual role | **Consolidate** → `AppButton.vue` atom |
| Loading spinner | Identical `.spin`/`@keyframes spin` block copy-pasted in 13 files (App.vue, 8 views, 4 components) + 1 variant | **Consolidate** → `AppSpinner.vue` atom |
| Badges/pills | 7 independent implementations, several sharing `border-radius: 999px` but each with its own padding/color rule | **Consolidate** → `AppBadge.vue` atom |
| Job card | `.job-card`/`.job-list` CSS block is **byte-identical** in `VideoView.vue`, `CompressConvertView.vue`, `ConverterView.vue`, `AudioView.vue` | **Consolidate** → `JobCard.vue` molecule |
| Empty state | `.empty-state` CSS block byte-identical in the same 4 files; markup near-identical (only noun/icon differ) | **Consolidate** → `EmptyState.vue` molecule |

**Found NOT to be real duplication** (left alone — no structure created for these):

- **Cards/panels** other than job-card: `SummaryCards.vue`, `CollapsiblePanel.vue`, `HomeView.vue`'s
  home-tile cards, `ImageInfoPanel.vue` are each a genuinely separate, single-use visual system —
  no shared markup/CSS between them. Not consolidated.
- **Modals**: only one true fixed-overlay modal exists (`BatchExportModal.vue`). `ImageEditorView.vue`'s
  mobile drawer backdrop is structurally similar but has different z-index/opacity and only one
  other consumer — two data points is not the 3+-file bar this audit uses, and forcing them together
  would touch a working, self-contained editor screen for a cosmetic-only gain. Not consolidated.
- **Form fields**: 5 separate patterns (`SettingRow.vue`, `AppSelect.vue`, `RangeSlider.vue`,
  `ResolutionStepper.vue`, inline native inputs) with no confirmed markup/CSS overlap beyond
  "labeled input" as a concept. Not consolidated — each already has a distinct, working
  implementation and the audit found no bug or real duplication to fix.
- **Upload/drop zone**: `UploadZone.vue` is used only by `ImageEditorView.vue` — not duplicated.
  The other 4 job-queue views use a plain button pair instead (already deduplicated at the *logic*
  level by `usePickFiles.ts`, per audit (e)) — their *visual* choice not to use a drop zone is a
  legitimate UX difference, not unaddressed duplication.
- **Error states**: each surface's error presentation differs enough in content (API-unreachable
  vs. license error vs. per-field validation vs. per-job failure) that no shared component is
  justified beyond what `AppButton`/`AppBadge` already cover for their retry/status affordances.

**Two real bugs found alongside the duplication** (fixed as part of this refactor, not treated as
new scope — they're defects the consolidation directly resolves):

- `.primary-btn` is used in `VideoView.vue`, `CompressConvertView.vue`, `AudioView.vue` (6 button
  instances total) without ever being defined in those files' own `<style scoped>` blocks or in
  any global stylesheet — these buttons render unstyled today. `AppButton.vue` fixes this by
  construction (there is no more per-file class to forget).
- `--border-1` is referenced 8 times (`ComponentsView.vue`, `AudioView.vue`, `VideoView.vue`,
  `LicenseActivationView.vue`, `ConverterView.vue`, `SettingsView.vue`, `CompressConvertView.vue`
  ×2) but never defined in `theme.css`/`base.css`/`main.css` — an invalid custom property, so those
  `border` declarations are silently dropped. Resolved by routing all 8 sites to the real existing
  token, `--surface-border` (see Audit (b)), removing the phantom variable.

## Audit (b) — CSS token audit

`theme.css` **already implements a working token system** (`--surface-0..3`, `--surface-border`,
`--text-primary/secondary/tertiary`, `--color-success/warning/danger`, 8 accent palettes,
`--space-1..5`, `--radius-sm/md/lg`, `--fs-*`/`--fw-*`, `--shadow-sm/md`). The audit finding is not
"no design system exists" — it does — but that dozens of components bypass it with literal values.

**Confirmed token gaps** (repeated 3+ files, not already covered by an existing token):

- `#fff` used ~20+ times for "text/icon on a colored background" — a real, missing semantic token.
  → add `--on-primary: #fff`.
- `border-radius: 999px` (pill shape) used ~20 times as a literal, with no equivalent tier in the
  existing `sm/md/lg` (6/10/14px) scale. → add `--radius-full: 999px`.
- `gap: 6px` used 15+ times — sits between the existing `--space-1` (4px) and `--space-2` (8px),
  not equal to either, so it is a genuinely distinct, undertokenized value. → add
  `--space-1-5: 6px`, following the existing numeric naming convention.
- `rgba(11, 14, 20, 0.72)` identical in `CompareSlider.vue` and `ImageEditorView.vue` (2 files) —
  weak candidate (below the 3-file bar) but cited for completeness; not tokenized in this pass.

**Explicitly NOT tokenized** (below the 3-file duplication bar, or single-use decorative values):
`HomeView.vue`'s bespoke home-tile gradient/tint palette (10+ one-off hex values, each used once),
`SettingsView.vue`/`ComponentsView.vue`'s accent-swatch hex literals that happen to numerically
match existing per-accent tokens (`theme.css:73-147`) — routing these specific two files to
reference the existing accent tokens directly is in scope as a targeted fix (it removes literal
duplication of an *existing* token, not a new token), but the swatch *values themselves* are not
new tokens.

## Audit (c) — Service-bypass audit

**Zero violations found.** `fetch(` and `window.api` do not appear anywhere in `components/` or
`views/` outside `apiClient.ts`/`nativeBridge.ts` themselves. Every HTTP and native call already
flows through these two files. This changes the shape of FR-007: there is no bypass to fix, so the
`services/` layer requirement is satisfied by **relocating and renaming** the existing,
already-centralized files for discoverability and to match the constitution's naming rule — not by
fixing a scattered-call problem that does not exist.

**Decision**: `apiClient.ts` → `services/api.ts` (unchanged content, HTTP request/response
functions), plus a new `services/websocket.ts` extracted from `apiClient.ts`'s
`subscribeJobProgress()` (Audit (d) confirms this is real, load-bearing WS logic — its own file is
justified because socket lifecycle, i.e. open/onmessage/onerror/close, is a genuinely separable
responsibility from request/response HTTP functions, not because of line count). `nativeBridge.ts`
→ `services/native.ts` (unchanged content). No further fragmentation (no `jobs.service.ts`,
`license.service.ts`, etc.) — `apiClient.ts` is already internally grouped by domain via function
naming, and splitting a ~450-line file already reads coherently into many single-purpose files
would repeat the exact "one file per class" anti-pattern Principle XI already rejected for `api/`,
applied here to the frontend. This is a deliberate, audit-driven narrowing of the original request's
literal `services/api/{client,endpoints,jobs.service,...}.ts` structure — justified under
Principle X's "adapted, not templated" rule and the constitution's explicit requirement that
structure be earned by confirmed need, not assumed from a template.

## Audit (d) — WebSocket audit

**Confirmed real WebSocket usage**, correctly wired end-to-end already:

- `apiClient.ts` opens `new WebSocket(...)` at `/ws/jobs/{job_id}` for live job progress.
- Consumed by `store/jobs.ts` and directly by `VideoView.vue`, `ConverterView.vue`, `AudioView.vue`,
  `CompressConvertView.vue`.
- Backend route `api/astros_upscale_api/app/routes.py:588` (`@ws_router.websocket('/ws/jobs/{job_id}')`)
  matches 1:1 — no polling-instead-of-WS mismatch.
- CSP in `renderer/index.html` explicitly allowlists `ws://127.0.0.1:8765`.

**Decision**: `services/websocket.ts` IS created (see Audit (c) decision above) — this is the one
case where FR-007's conditional "only if the audit confirms real WebSocket traffic" clause is
satisfied.

## Audit (e) — Store/composable responsibility audit

All 5 stores and all 5 composables were read in full. **No store or composable bypasses
`apiClient.ts`/`nativeBridge.ts`** — every HTTP/native call already flows through them.

- `store/jobs.ts` (571 lines) mixes file-intake validation, scale-config defaults, backend job
  lifecycle, and WS-subscription bookkeeping in one file. This is a real scope/size concern (the
  largest store by far) but not a layering violation — no bug, no bypass. **Decision**: left as-is;
  splitting it is not justified by anything the audit found (no confirmed duplication or bypass to
  fix), and doing so anyway would be exactly the "split for line-count reasons alone" pattern
  Principle X forbids.
- `store/history.ts`, `store/apiStatus.ts` — clean, single responsibility, no change needed.
- `store/settings.ts` — legitimately mixes preference persistence with DOM/theme application; the
  file already documents why. No change needed.
- `store/license.ts` — thin wrapper over the `/license/*` API functions; its own comment documents
  a **past** bypass (calling the remote licensing service directly from the renderer) that was
  already fixed. No current violation; cited here only as precedent that this project has hit
  exactly this failure mode before.
- `composables/useDenoisePreview.ts`, `useExportPanel.ts`, `usePickFiles.ts`, `useTruncated.ts`,
  `useViewportPanZoom.ts` — each single-responsibility, none calling raw HTTP. `usePickFiles.ts`'s
  own comment confirms it was extracted specifically because the "pick files" logic (not the CSS)
  was already byte-identical across the same 4 job-queue views identified in Audit (a) — direct
  corroboration of that finding.

**Decision**: no store/composable restructuring in this feature. FR-006/FR-013 concerns (mixing
UI/HTTP/state) named in the original request as a hypothetical risk did not materialize on
inspection — recorded here so the plan doesn't invent work the audit didn't find.

## Audit (f) — Version audit

From `interface/package.json`: `vue ^3.5.25`, `vite ^7.2.6`, `electron-vite ^5.0.0`,
`typescript ^5.9.3`, `vue-tsc ^3.1.6`, `@vitejs/plugin-vue ^6.0.2`. No `postcss`/`autoprefixer`
currently installed.

**Decision**: adopt **Tailwind CSS v4** via its official Vite plugin (`@tailwindcss/vite`), not the
v3 PostCSS-plugin approach. Rationale:

- Tailwind v4's Vite plugin needs no separate `postcss`/`autoprefixer` dependency and no
  `tailwind.config.js` — satisfying FR-015 ("no dependency beyond Tailwind and its direct build
  tooling requirements") with the smallest possible dependency footprint (one package).
- Tailwind v4 configures its theme in CSS via an `@theme` block, which reads existing CSS custom
  properties directly — this maps almost exactly onto the token system `theme.css` already has
  (Audit (b)), minimizing churn: existing `--surface-1`, `--space-1..5`, `--radius-sm/md/lg` etc.
  become Tailwind theme values with the same names and values, not a parallel JS-config system.
- Compatible with Vite 7 and Vue 3.5 (both current at time of writing).
- The exact patch version MUST be verified against the currently published npm version at
  implementation time (`npm view tailwindcss version` / `npm view @tailwindcss/vite version`) —
  this research records the major-version decision and its rationale, not a pinned version number,
  per this constitution's explicit "verify, don't assume" requirement.

## Audit (g) — Main process audit

`src/main/index.ts` (248 lines) currently handles, confirmed by direct reading:

1. Custom protocol registration (`astros-media://`) + file-kind/MIME helpers used only by it.
2. Window creation (`createWindow()`).
3. 11 IPC channel handlers: `api:ensure`, `dialog:openFiles`, `dialog:openFolder`,
   `dialog:selectOutputFolder`, `fs:statPath`, `paste:saveImage`, `shell:showItemInFolder`,
   `shell:openPath`, `app:paths`, `app:version`, `debug:openDevTools`.
4. App lifecycle wiring (`whenReady`, `window-all-closed`, `activate`, `before-quit`) and API
   child-process lifecycle delegation to `apiProcess.ts` (unchanged — already single-responsibility).

**Decision**: these are genuinely separable responsibilities (protocol vs. window vs. IPC vs. app
lifecycle), each independently testable/reasoned-about, which meets Principle X's bar for
splitting a file. Split into:

- `main/protocols/mediaProtocol.ts` — protocol registration + its file-kind/MIME helpers.
- `main/windows/mainWindow.ts` — `createWindow()`.
- `main/ipc/dialog.ipc.ts` — the 5 dialog/filesystem-adjacent channels (`dialog:openFiles`,
  `dialog:openFolder`, `dialog:selectOutputFolder`, `fs:statPath`, `paste:saveImage`) plus the
  shared `describeFile()` helper they use.
- `main/ipc/app.ipc.ts` — the remaining 6 channels (`api:ensure`, `shell:showItemInFolder`,
  `shell:openPath`, `app:paths`, `app:version`, `debug:openDevTools`).
- `main/index.ts` — reduced to app-lifecycle wiring + bootstrapping the above modules. No
  `bootstrap/` wrapper folder is added — the modules above are already the bootstrap units; an
  extra layer of `bootstrap/createWindow.ts` re-exporting `windows/mainWindow.ts` would be exactly
  the "wrapper that only forwards a call" Principle X prohibits.
- `apiProcess.ts` is unchanged — already single-responsibility, no split justified.

## Tailwind configuration approach

Given theme.css already has the token values, the migration strategy is: **define an `@theme`
block in a new `renderer/src/styles/tailwind.css`** that maps Tailwind's theme keys to the existing
CSS custom properties (`--color-surface-1: var(--surface-1)`, etc. — Tailwind v4 requires the
`@theme` block's own custom properties, so existing app-level tokens in `theme.css` are kept as the
single source of truth and re-exposed to Tailwind's `@theme`, not duplicated by value). `base.css`'s
unused Vite-starter `--ev-c-*` variables (confirmed zero external references in Audit (b)) are
deleted as dead code per FR-013.
