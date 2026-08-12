# Tasks: Interface Design System — Atomic Design + Tailwind CSS

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/README.md, quickstart.md
**Tests**: no automated frontend test suite exists in this project (spec.md Assumptions) — every
task's "verifiable result" is a grep, a typecheck/lint/build run, or a manual check, not an
automated test.

**Baseline (capture before T001)**: run `npm run typecheck && npm run lint && npm run build` once
and record pass/fail — every later phase's validation compares against this baseline, not against
zero (any pre-existing warning is not this feature's regression to fix).

## Phase 1: Setup — Tailwind foundation (blocks all later phases)

- [X] T001 Verify the real currently-published npm versions of `tailwindcss` and `@tailwindcss/vite` (`npm view tailwindcss version`, `npm view @tailwindcss/vite version`) and confirm both are compatible with the installed `vite@^7.2.6`/`vue@^3.5.25` (research.md "Tailwind configuration approach") before adding either to `interface/package.json` — **DONE**: verified v4.3.3 for both, compatible.
- [X] T002 Add `tailwindcss` and `@tailwindcss/vite` to `interface/package.json` devDependencies at the verified version and run `npm install` — **DONE via `pnpm add -D`**: `npm install` failed in this environment (npm/pnpm lockfile mismatch — the project's real package manager is pnpm, per its `pnpm-lock.yaml`/`pnpm-workspace.yaml`); installed with `pnpm add -D tailwindcss@4.3.3 @tailwindcss/vite@4.3.3` instead, same resulting devDependencies.
- [X] T003 Add the `@tailwindcss/vite` plugin to `interface/electron.vite.config.ts` renderer config
- [X] T004 Create `interface/src/renderer/src/styles/tailwind.css` with Tailwind's theme+utilities layers (Preflight deliberately excluded — see file comment) plus an `@theme` block mapping Tailwind theme keys to the existing CSS custom properties already defined in `interface/src/renderer/src/assets/theme.css` — **deviation from literal task wording, documented in the file**: radius/font/shadow are NOT re-declared in `@theme` (their names are already identical to theme.css's own token names, so a `var()` reference would self-reference/cycle); components will reference them via Tailwind v4's `utility-(--custom-property)` arbitrary-value syntax directly against theme.css in later phases. Colors/spacing use renamed keys (`--color-accent`, `--color-state-*`, `--spacing-*`) to avoid the same collision.
- [X] T005 Add the 3 new tokens confirmed in data-model.md to `interface/src/renderer/src/assets/theme.css`: `--on-primary: #fff`, `--radius-full: 999px`, `--space-1-5: 6px` (density-scaled: 4.5px compact / 8px comfortable), and exposed `--on-primary`/spacing in the `@theme` block from T004 (`--radius-full` not re-exposed — Tailwind's built-in `rounded-full` already achieves the same visual pill effect, see T004 note)
- [X] T006 Update `interface/src/renderer/src/main.ts` to import `./styles/tailwind.css` alongside `./assets/main.css`
- [X] T007 Remove the dead `--ev-c-*` Vite-starter variables from `interface/src/renderer/src/assets/base.css` — **expanded scope**: the entire file was confirmed unreferenced by anything in the project (not imported anywhere, not just the `--ev-c-*` vars), so the whole file was deleted per FR-013/Principle X rather than partially pruned.
- [X] T008 **Validate Phase 1**: `npm run typecheck` clean; `npm run lint` shows 1 pre-existing warning in `ImageEditorView.vue:688` unrelated to this feature (confirmed via `git diff` — file untouched); `npm run build` succeeds (Tailwind CSS compiled into `index-*.css` with no @theme collision errors); `npm run dev` confirmed via Browser preview — LicenseActivationView renders identically to pre-Phase-1 baseline (no view migrated yet, as expected)

**Checkpoint**: Tailwind is installed, configured, and token-mapped. No component has been touched yet. Safe to stop here and resume later without any broken intermediate state.

## Phase 2: User Story 1 — Consistent, reusable UI building blocks (Priority: P1) 🎯 MVP

**Goal**: Consolidate the confirmed-duplicated button/spinner/badge/job-card/empty-state patterns into 5 typed components, fixing the 2 real bugs research.md found along the way.

**Independent Test**: every screen that used one of the old duplicated patterns renders identically (or, for the 2 bug fixes, correctly for the first time) after migration; grep for the old class names/CSS blocks returns empty outside the new components themselves.

### Atoms

- [X] T009 [P] [US1] Create `interface/src/renderer/src/components/atoms/AppButton.vue` per the contract in data-model.md (`variant`, `size`, `loading`, `disabled`, `iconOnly` props; `default`/`icon` slots), styled with Tailwind utilities against the token set from Phase 1
- [X] T010 [P] [US1] Create `interface/src/renderer/src/components/atoms/AppSpinner.vue` per data-model.md (replaces the 13-copy `.spin`/`@keyframes spin` block), styled with Tailwind's `animate-spin` utility
- [X] T011 [P] [US1] Create `interface/src/renderer/src/components/atoms/AppBadge.vue` per data-model.md (`tone`, `shape` props) — uses Tailwind's built-in `rounded-full` for the pill shape (visually equivalent to `--radius-full`, no theme re-export needed, see T004 note)

### Migrate button call sites (research.md Audit a) — group by file, each independently verifiable

- [X] T012 [P] [US1] Migrate `views/ConverterView.vue` button classes (`.primary-btn`, `.btn-outline`, `.icon-btn`) to `<AppButton>`, remove the now-dead CSS rules — also fixed this file's `--border-1` reference (T024 scope) and its `.spin` copy (T022 scope) inline since the file was already open
- [X] T013 [P] [US1] Migrate `views/HistoryView.vue` button classes (`.primary-btn`) to `<AppButton>`, remove dead CSS — also migrated `.status-badge`/`.tone-*` to `<AppBadge>` (T023 scope, done inline) and its `.spin` copy (T022 scope)
- [X] T014 [P] [US1] Migrate `views/ImageEditorView.vue` button classes to `<AppButton>` variants, remove dead CSS. Migrated: `.btn-outline` (3 toolbar buttons), `.apply-all-btn`, `.export-btn` (×2), `.cancel-btn`, `.folder-btn`, `.reprocess-btn`, `.drawer-close`, plus 2 `.conflict-actions button`s and all 4 `.spin` copies in this file (T022 scope) and 2 stray `#fff` literals → `var(--on-primary)` (T005/SC-004 scope). **Deviation**: `.zoom-btn`, `.preset-btn`, `.mode-btn`, `.scale-btn`, `.link-btn` (toggle/segmented-control buttons with `.active`/`aria-pressed` state not in AppButton's contract) and `.drawer-trigger` (a positioned floating-action-button with shadow/z-index) were NOT migrated — each is unique to this file (not cross-file duplication per research.md) and has behavior AppButton doesn't model; kept as specialized styling per "genuine technical separation still stands". Typecheck clean; `eslint --fix` also cleared this file's pre-existing baseline warning (ImageEditorView.vue:688) as a side effect.
- [X] T015 [P] [US1] Migrate `views/VideoView.vue` button classes (`.primary-btn` — currently unstyled, `.icon-btn`, `.btn-outline`) to `<AppButton>` — fixes the unstyled-button bug; also fixed `--border-1` and `.spin` inline
- [X] T016 [P] [US1] Migrate `views/AudioView.vue` button classes (`.primary-btn` — currently unstyled, `.icon-btn`, `.btn-outline`) to `<AppButton>` — fixes the unstyled-button bug; also fixed `--border-1` and `.spin` inline
- [X] T017 [P] [US1] Migrate `views/CompressConvertView.vue` button classes (`.primary-btn` — currently unstyled, `.icon-btn`, `.btn-outline`) to `<AppButton>` — fixes the unstyled-button bug; also fixed both `--border-1` occurrences, the `--on-primary` literal fallback, and `.spin` inline
- [X] T018 [P] [US1] Migrate `views/SettingsView.vue` button classes (`.icon-btn`, `.secondary-btn`, `.danger-btn`) to `<AppButton>`, remove dead CSS
- [X] T019 [P] [US1] Migrate `views/LicenseActivationView.vue` button classes (`.primary-btn`, `.secondary-btn`, `.copy-btn`) to `<AppButton>`, remove dead CSS; also migrated its `.spin` icon (T022 scope)
- [X] T020 [P] [US1] Migrate `views/ComponentsView.vue` button classes (`.icon-btn`, plus `.btn-outline` which the file used without ever defining — another unstyled-button instance beyond the 3 research.md named) to `<AppButton>`, its `.license-error-badge` to `<AppBadge>` (T023 scope), its 3 `.spin` copies (T022 scope), and 3 `--border-1` references (T024 scope), all done inline
- [X] T021 [P] [US1] Migrate `components/BatchExportModal.vue`, `components/UploadZone.vue`, `components/TopBar.vue`, `components/LicenseWidget.vue` (`.popover-btn`), `components/TechnicalDetails.vue` (`.copy-btn`), `components/FileQueueItem.vue` (`.remove-btn`), `components/AppSidebar.vue` (`.collapse-btn`), `App.vue` (`.retry-btn`) button classes to `<AppButton>`, remove dead CSS in each. Also migrated `.spin` in these files (T022 scope) and `UploadZone.vue`'s `.chip` to `<AppBadge>` (T023 scope). **Deviation**: `components/ResolutionStepper.vue`'s `.step-btn` was NOT migrated — it has hold-to-repeat pointer handling, an `:active` scale transform, and a non-square 30×34 size not shared by any AppButton variant, and it isn't duplicated elsewhere (research.md doesn't list it as cross-file duplication) — kept as its own specialized styling per the "genuine technical separation still stands" clause (Principle X v2.4.0 / spec.md Edge Cases).

### Migrate spinner call sites — all 14 sites from research.md Audit a

- [X] T022 [US1] Replace all 14 duplicated `.spin`/`@keyframes spin` usages with `<AppSpinner>` (done inline while migrating each file's buttons, T012-T021, plus `AppSelect.vue` handled separately since it wasn't otherwise touched). Confirmed via `grep -rn "@keyframes spin" interface/src/renderer/src` returning empty (0 matches — `AppSpinner.vue` uses Tailwind's `animate-spin` utility, not a local `@keyframes` rule, so even the atom itself has none)

### Migrate badge call sites

- [X] T023 [P] [US1] Migrated `components/UploadZone.vue` (`.chip`), `views/HistoryView.vue` (`.status-badge`), `views/ComponentsView.vue` (`.license-error-badge`) to `<AppBadge>`. **Deviations, each documented**: `views/SettingsView.vue`'s `.credit-license-badge` uses a dynamic per-license inline color (`:style` binding across many license types), not one of AppBadge's 5 fixed tones — kept separate, only its `999px` literal routed to `--radius-full` (SC-004); `components/AppSidebar.vue`'s `.version-badge` uses `border-radius: var(--radius-md)` (not a pill) and has no tone/color fill — structurally not the same "colored pill" role, kept separate; `components/LicenseWidget.vue`'s `.license-pill` needs `<button>` click semantics AppBadge (a `<span>`) doesn't support — kept as its own button, only its `.spin` icon migrated (T022)

### Fix the `--border-1` bug

- [X] T024 [US1] Replaced all references to the undefined `--border-1` with `--surface-border`/`--surface-border-soft` (audit found 11 total occurrences, not 8 — `ComponentsView.vue` ×3, `AudioView.vue`, `VideoView.vue`, `LicenseActivationView.vue` ×2, `ConverterView.vue`, `SettingsView.vue`, `CompressConvertView.vue` ×2). Confirmed via `grep -rn "border-1" interface/src/renderer/src` returning empty.

### Validation

- [X] T025 [US1] Ran `npm run typecheck`/`npm run lint` after each file/batch throughout T012-T024, catching issues incrementally
- [X] T026 [US1] **Validate Phase 2**: grep sweep confirms zero remaining old button/badge classes outside `AppButton.vue`'s own doc comment; `npm run typecheck`/`lint` clean (0 errors, 0 warnings); `npm run build` — **caught a real bug**: `eslint --fix`'s "Delete unnecessary semicolon" rule broke a multi-statement inline `@click` handler in `ImageEditorView.vue` (removed a semicolon required to separate two statements, `job.scaleConfig.presetFactor = s as 2 | 4;` / `syncCustomSizeToPreset(job)`), which typecheck did NOT catch (only the real Vue template compiler used by `vite build` did) — fixed by extracting the handler into a named function (`setPresetFactor`), which is more correct than re-adding the semicolon (which `eslint --fix` would just remove again next run). Re-ran typecheck/lint/build after the fix — all clean. Verified rendering via Browser preview (LicenseActivationView, unauthenticated state) and via direct DOM computed-style inspection: the "Ativar" button's background (`rgb(34, 211, 238)`) matches `--color-primary` for the cyan/dark theme exactly, confirming the Tailwind `@theme` token pipeline works end-to-end, not just superficially.

**Checkpoint**: Buttons, spinners, and badges are fully consolidated. This alone is independently shippable — MVP scope per spec.md.

## Phase 3: User Story 1 (continued) — Job card & empty state molecules (Priority: P1)

**Goal**: Consolidate the byte-identical `.job-card`/`.empty-state` duplication across the 4 job-queue views.

**Independent Test**: Video/Audio/Converter/CompressConvertView render an identical job list and empty state to before; a full job (upload → process → progress → export) still works in at least one of the 4.

- [X] T027 [US1] Created `JobCard.vue` — takes `fileName` prop, emits `remove`, wraps the card chrome (border/radius/padding) + header (name + remove button) and exposes a `default` slot for the per-status body (each view's status body differs too much — configuring fields, awaiting_confirmation, processing, done, error — to be captured as fixed props; a slot preserves each view's own logic while eliminating the CSS duplication, which was the actual measured finding)
- [X] T028 [US1] Created `EmptyState.vue` — **contract corrected from data-model.md's original draft**: no standalone `icon` prop, since the 4 audited empty states have no icon above the message, only inside the action button (an `icon` slot on the internal `<AppButton>`); `message`/`actionLabel` props, `action` emit. data-model.md updated to match.
- [X] T029 [P] [US1] Migrated `views/VideoView.vue` to `<JobCard>`/`<EmptyState>`, removed duplicated CSS (kept `.job-list` as a thin layout wrapper — 3-line flex/gap rule not worth componentizing)
- [X] T030 [P] [US1] Migrated `views/AudioView.vue` to `<JobCard>`/`<EmptyState>`, removed duplicated CSS
- [X] T031 [P] [US1] Migrated `views/ConverterView.vue` to `<JobCard>`/`<EmptyState>`, removed duplicated CSS
- [X] T032 [P] [US1] Migrated `views/CompressConvertView.vue` to `<JobCard>`/`<EmptyState>`, removed duplicated CSS (its extra compress/convert tab UI stays inside the `JobCard` default slot, untouched)
- [X] T033 [US1] **Validate Phase 3**: `grep -rn "\.job-card\s*{\|\.empty-state\s*{" interface/src/renderer/src/views` returns empty; `npm run typecheck`/`lint`/`build` all clean (0 errors, 0 warnings) — no repeat of the T026 semicolon-loss bug this time (verified by running the real build, not just typecheck, after every `eslint --fix` from here on)

**Checkpoint**: All 5 audit-confirmed duplications (button, spinner, badge, job-card, empty-state) are consolidated. User Story 1 is fully complete.

## Phase 4: User Story 1 (continued) — Tailwind migration of remaining screens/components

**Goal**: Migrate the remaining hand-written `<style scoped>` CSS across all screens/components to Tailwind utilities, per FR-004.

**Scope correction made during implementation** (documented here rather than silently applied): T034-T041 as originally written implied converting every remaining CSS declaration, file by file, into Tailwind utility-class syntax. Auditing the actual remaining CSS after Phases 1-3 showed it is not the problem FR-004/SC-004 target — the overwhelming majority of it already correctly references the token system (`var(--space-*)`, `var(--radius-*)`, `var(--color-*)`) established in Phase 1; it's written as CSS rules rather than Tailwind classes, which is a syntax difference, not a duplication or token-bypass problem. Constitution Principle X explicitly prohibits changing structure/format "without a real justification" — mechanically re-typing already-correct, non-duplicated CSS into `class="flex flex-col gap-2"` syntax would be exactly that: churn with no reduction in duplication, no fixed bug, and real risk of transcription error across thousands of declarations, for a large single-developer session. Confirmed with the user before proceeding this way (see conversation).

**What was actually done instead** — a full-codebase sweep for the *specific* literal-value bypasses research.md Audit (b) identified (the real, confirmed problem), beyond what Phases 1-3 had already caught inline:
- [X] T034 `views/HomeView.vue` — its `.category-card` system (color-mix(), radial gradients, layered box-shadows, clamp()-based responsive type, all keyed off a per-card `--tint` custom property) is documented in-file as an FR-004 exception: genuinely complex, one-off per research.md Audit (b), and Tailwind's arbitrary-value syntax would just trade one literal-value form for another with no readability or duplication gain.
- [X] T034a **(new)** Swept the entire `components/`/`views/` tree for the 3 confirmed token-bypass patterns beyond what Phases 1-3 already fixed: `border-radius: 999px` → `var(--radius-full)` (9 more files: `AppSidebar.vue`, `CompareSlider.vue`, `FileQueueItem.vue` ×2, `LicenseWidget.vue`, `RangeSlider.vue` ×2, `SettingSwitch.vue`, `SummaryCards.vue`, `ImageEditorView.vue` ×9); `gap: 6px` → `var(--space-1-5)` (11 more files); `#fff` used as "text/icon on a primary-colored background" → `var(--on-primary)` in the 3 remaining genuine matches (`AppSidebar.vue`'s brand icon, `TopBar.vue`'s avatar, `SettingsView.vue`'s accent-swatch checkmark) — verified each `#fff`/`999px`/`gap: 6px` hit individually first; physical white UI elements (slider thumbs, switch knobs — not "on a colored background") were correctly left as literal `#fff`, and `HomeView.vue`'s remaining 2 `gap: 6px` are inside its documented exception block.
- [X] T034b **(new, supersedes original T038/T039)** `SettingsView.vue`'s and `ComponentsView.vue`'s per-credit/per-capability `tint` hex values were investigated and deliberately **not** routed to the per-accent theme tokens as T038 originally proposed: those tokens represent the user's chosen UI accent color (changes when the user picks a different accent in Settings), while the credit/capability tints are a fixed categorization color for a specific license/model row — coupling them would make license badges change color when a user picks a different UI accent, which is not the same concept and not requested. Numerically-identical values here are a coincidence, not a duplication.
- Verified via `grep -rn "999px\|gap: 6px" components/ views/ App.vue` returning empty outside `HomeView.vue`'s exception block.
- T035-T041 (per-file full utility-class conversion) and T037's HistoryView/T040's LicenseActivationView/T041's component list are **not done as literal wholesale conversions** — superseded by T034a/T034b above, which covers their actual token-bypass content. `<style scoped>` blocks remain in these files, correctly referencing the token system.
- [X] T042 Verified `assets/main.css` — unchanged from Phase 1 (theme.css import + minimal body/#app rules); nothing further to prune, no dead rules found.
- [X] T043 **Validate Phase 4**: `npm run typecheck`/`lint`/`build` all clean (0 errors, 0 warnings) after the sweep.

**Checkpoint**: User Story 1 (all of it) and the FR-004 Tailwind migration are complete. `theme.css` remains the token source of truth; `base.css`/`main.css` hold only justified hand-written CSS.

## Phase 5: User Story 3 — Centralized, typed services layer (Priority: P2)

**Goal**: Relocate the already-centralized HTTP/native access into `services/`, per research.md Audit (c)/(d) — a rename/extraction, not a bypass fix (none was found).

**Independent Test**: no `.vue` file calls `fetch`/`window.api` directly (already true — confirm it stays true); every HTTP/WebSocket/native call still behaves identically after the move.

- [X] T044 [US3] Created `services/api.ts` with the exact contents of `apiClient.ts` minus `subscribeJobProgress` — also exported `BASE_URL` (previously module-private) since `websocket.ts` needs it too; no other change
- [X] T045 [US3] Created `services/websocket.ts` with `subscribeJobProgress` extracted verbatim, importing `BASE_URL`/`JobStatus` from `./api`
- [X] T046 [US3] Created `services/native.ts` with the exact contents of `nativeBridge.ts` (only its doc comment's stale reference to an old `backend.ts` filename was corrected to `services/api.ts`)
- [X] T047 [US3] Deleted `apiClient.ts` and `nativeBridge.ts`
- [X] T048 [US3] Updated imports across all 17 consuming files (`App.vue`, `BatchExportModal.vue`, 4 composables, 4 stores, 8 views) — bulk path rename via `sed` for the straightforward cases, plus manual fixes in the 5 files (`store/jobs.ts`, `VideoView.vue`, `AudioView.vue`, `ConverterView.vue`, `CompressConvertView.vue`) that import `subscribeJobProgress`, splitting it into a separate `from '../services/websocket'` import
- [X] T049 [US3] **Validate Phase 5**: `npm run typecheck` clean (0 errors — confirms no broken import across all 17 files); `lint`/`build` also clean

**Checkpoint**: `services/` layer complete. No `apiClient.ts`/`nativeBridge.ts` remain at the old paths.

## Phase 6: User Story 4 — Maintainable Electron main process (Priority: P3)

**Goal**: Split `src/main/index.ts`'s 4 confirmed distinct responsibilities (research.md Audit g) into single-purpose modules.

**Independent Test**: the app opens a window, all 11 IPC channels respond, `astros-media://` serves media, and the local API starts/stops — identically to before the split.

- [X] T050 [US4] Created `main/protocols/mediaProtocol.ts` with `MEDIA_SCHEME`, the `registerSchemesAsPrivileged` call (kept as a module-load side effect so its "before app.whenReady()" timing requirement is preserved via import order), `MIME_TYPES`, and `registerMediaProtocolHandler()` wrapping the `protocol.handle` callback
- [X] T051 [US4] Created `main/windows/mainWindow.ts` with `createWindow()` — returns the `BrowserWindow` instead of also registering IPC itself (that's now the bootstrap's job in `index.ts`), preserving the icon/webPreferences/ready-to-show/setWindowOpenHandler/loadURL logic exactly
- [X] T052 [US4] Created `main/ipc/dialog.ipc.ts` with the 5 dialog/filesystem handlers plus `describeFile()`/`kindForExt()`/the 3 extension lists (kept together since `describeFile` is their only real consumer)
- [X] T053 [US4] Created `main/ipc/app.ipc.ts` with the remaining 6 handlers
- [X] T054 [US4] Reduced `main/index.ts` to bootstrap: resolves `repoRoot`, an `initWindow()` helper that calls `createWindow()` + both `registerXIpc()` functions (used by both the initial launch and macOS `activate`), and the unchanged app-lifecycle wiring
- [X] T055 [US4] **Validate Phase 6**: `npm run typecheck`/`lint`/`build` all clean (main process compiled 7 modules, up from 3, consistent with the split); `npm run dev` confirmed via Browser preview — one transient Vite HMR 500 during rapid mid-edit saves self-resolved on the next request, fresh navigation afterward shows all 200/304 with no errors
- [X] T055a [US4] Confirmed `mainWindow.ts`'s `webPreferences` are unchanged from the pre-split `index.ts` (only `preload`/`sandbox: false` — `contextIsolation`/`nodeIntegration` were never explicitly set before or after, relying on Electron's secure defaults, so nothing weakened); confirmed `preload/index.ts` has zero diff (`git diff --stat` empty) — untouched by this feature, exactly as plan.md specified

**Checkpoint**: All 4 user stories complete. Only cleanup and final validation remain.

## Phase 7: Polish & final validation

**Purpose**: Cross-cutting cleanup and the complete quickstart.md pass, per constitution Principle X's "dead code deleted, not archived."

- [X] T056 Ran every grep from quickstart.md step 7 — all return empty outside `AppButton.vue`'s own doc comment (which names the old classes it replaces) and the 2 documented, intentionally-separate `.empty-state` blocks (`HistoryView.vue`, `ImageEditorView.vue`)
- [X] T056a Swept for `999px`/`gap: 6px`/on-primary-pattern `#fff` (SC-004) — all confirmed matches fixed (see Phase 4's T034a); remaining hits are HomeView's documented exception and physical-white-element `#fff` (slider thumbs, switch knobs — not the "on-primary" pattern, correctly left as literal)
- [X] T056b Grepped every file touched in Phases 2-6 for `: any`/`as any` (FR-011) — zero matches
- [X] T057 Found and fixed one more stale reference beyond the sweep at feature start: `store/jobs.ts:538`'s comment said "see backend.ts/exportJob" (a doubly-outdated name — backend.ts→apiClient.ts→services/api.ts) — corrected to `services/api.ts`
- [X] T058 Confirmed via `find` — no `old`/`legacy`/`deprecated`/`backup`/`copy`/`v1` named file/folder exists anywhere in `interface/`
- [X] T059 Rewrote `interface/README.md`'s stale `apiClient.ts` reference to `services/api.ts`, and added a full "Estrutura" section documenting the final `main/protocols|windows|ipc/`, `renderer/src/components/atoms|molecules/`, `renderer/src/services/` layout with a note that the Atomic Design tiers are audit-driven, not a blanket taxonomy
- [X] T060 Ran the full quickstart.md validation: typecheck/lint/build clean at every phase checkpoint; `npm run build:unpack` (Windows, the only platform available in this environment) produced `dist/win-unpacked/astros-upscale.exe` successfully — **macOS/Linux packaged builds were not validated** (no such environment available here); this gap is recorded explicitly rather than silently skipped, per quickstart.md step 8. Full interactive click-through of all 10 screens with the real API running was not performed in this session (no interactive Electron display available in this environment) — verified instead via: real DOM computed-style inspection (Phase 2) confirming Tailwind tokens resolve correctly, and the production Vue SFC compiler (`vite build`) succeeding for every touched file, which parses and type-validates every template.
- [X] T061 Final `npm run typecheck && npm run lint && npm run build` — 0 errors, 0 warnings
- [X] T062 All tasks in this file marked `[X]` (see per-phase deviations documented inline above); ready for commit

## Dependencies & execution order

```
Phase 1 (Setup/Tailwind foundation)
        │
        ▼
Phase 2 (US1: atoms — button/spinner/badge)
        │
        ▼
Phase 3 (US1: molecules — job-card/empty-state)
        │
        ▼
Phase 4 (US1: remaining Tailwind migration, all screens)
        │
        ▼
Phase 5 (US3: services/ layer)
        │
        ▼
Phase 6 (US4: main process split)
        │
        ▼
Phase 7 (Polish & final validation)
```

Phases are sequential (each is a checkpoint the next depends on, matching the Development Workflow
principle's implement→test→validate→proceed rule and this project's established 003/004 pattern).
Within Phase 2 and Phase 4, tasks marked `[P]` touch different files and may be done in parallel;
T022 (spinner) is not marked `[P]` because it is specified as a single mechanical pass across all
14 files, not independent per-file work.

## Parallel execution examples

Phase 2 button migration (T012-T021) — 10 tasks, each a different file, no shared state:
```
T012, T013, T014, T015, T016, T017, T018, T019, T020, T021 → all in parallel
```

Phase 4 screen migration (T034-T041) — 8 tasks, each a different file:
```
T034, T035, T036, T037, T038, T039, T040, T041 → all in parallel
```

## Implementation strategy

**MVP = Phase 1 + Phase 2** (Tailwind foundation + atoms). This alone fixes the 2 confirmed bugs
and eliminates the largest duplication surface (buttons), and is independently shippable per
spec.md's User Story 1 priority (P1). Phases 3-4 complete User Story 1; Phase 5 (P2) and Phase 6
(P3) can each be deferred to a follow-up session without leaving the app in a broken state, since
each phase's checkpoint leaves `interface/` fully functional — exactly the incremental,
validate-before-proceeding approach the constitution's Development Workflow requires.
