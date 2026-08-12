# Implementation Plan: Interface Design System — Atomic Design + Tailwind CSS

**Branch**: `005-interface-design-system` | **Date**: 2026-08-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-interface-design-system/spec.md`

## Summary

Replace `interface/`'s hand-written CSS with Tailwind CSS driven by the design tokens
`theme.css` already defines, and consolidate the specific, audit-confirmed UI duplication
(buttons, spinners, badges, job cards, empty states) into a small, pragmatic Atomic Design
structure (`atoms/`, `molecules/`) — nothing more. Relocate the already-centralized HTTP/native
access into a `services/` layer, split `src/main/index.ts`'s confirmed distinct responsibilities
into single-purpose modules, and strengthen TypeScript types on the touched surfaces. Every
structural addition traces to a specific finding in [research.md](research.md); nothing is created
speculatively.

## Technical Context

**Language/Version**: TypeScript 5.9.3, Vue 3.5.25 (`<script setup>` SFCs)

**Primary Dependencies**: Electron 39, electron-vite 5, Vite 7.2, vue-i18n 11, @lucide/vue 1.28,
@fontsource-variable — plus **Tailwind CSS v4** (new, via `@tailwindcss/vite`; see research.md
"Tailwind configuration approach")

**Storage**: N/A (no persistence layer in `interface/`; `localStorage` for settings/history is
unchanged by this feature)

**Testing**: `npm run typecheck`, `npm run lint`, `npm run build` (no frontend automated test
suite exists or is added — see spec.md Assumptions)

**Target Platform**: Electron desktop app — Windows (NSIS), macOS (dmg), Linux (AppImage/snap/deb)

**Project Type**: Desktop app (Electron main + preload + Vue renderer)

**Performance Goals**: No specific new performance target — Tailwind's JIT engine and v4's
`@tailwindcss/vite` plugin are expected to keep dev-server HMR and production bundle size at or
below current levels; not independently measured beyond confirming the build succeeds (constitution
Principle III requires measurement only for *claimed* improvements, and none is claimed here).

**Constraints**: Zero user-visible behavior change except the two confirmed-inconsistency fixes
named in research.md (unstyled `.primary-btn` instances; missing `--border-1` borders).

**Scale/Scope**: 18 components, 10 views, 5 stores, 5 composables, `apiClient.ts`,
`nativeBridge.ts`, `src/main/index.ts` (248 lines) + `apiProcess.ts`, `src/preload/index.ts`,
3 CSS files, 11 locale files (content unchanged, only new/changed component text needs new keys —
none is anticipated since no new user-facing copy is introduced by this refactor).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Spec First | This plan follows an approved spec (spec.md) | ✅ Pass |
| II. Reuse First | Every structural addition (AppButton, AppSpinner, AppBadge, JobCard, EmptyState, services/websocket.ts, main/protocols, main/ipc, main/windows) is justified by a specific research.md finding of real duplication/separable responsibility, not assumed | ✅ Pass |
| VIII. Tests Required | No frontend test suite exists; spec.md Assumptions records this and substitutes typecheck/lint/build + manual verification, consistent with prior features 003/004's validation approach | ✅ Pass (scope explicitly bounded in spec) |
| IX. Two-Layer Architecture | No change to `api/`; `interface/` continues to communicate only via HTTP/WebSocket through `services/` | ✅ Pass |
| X. Interface Structure Is Adapted, Not Templated (v2.4.0) | Every Atomic Design tier, design token, and `services/` sub-file traces to an Audit (a)-(g) finding in research.md; tiers/files NOT justified by the audit (organisms/, templates/, services/websocket as a folder, form-field consolidation, store/composable splitting) are explicitly NOT created | ✅ Pass — this plan is the direct application of the v2.4.0 amendment |

No violations to record in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-interface-design-system/
├── plan.md              # This file
├── research.md          # Phase 0 output — the audit and its decisions
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── README.md         # Phase 1 output — preserved-contracts statement
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (interface/, final structure — only additions/moves justified by research.md)

```text
interface/
├── src/
│   ├── main/
│   │   ├── index.ts                    # reduced to app-lifecycle bootstrap
│   │   ├── apiProcess.ts               # unchanged
│   │   ├── protocols/
│   │   │   └── mediaProtocol.ts        # NEW — astros-media:// + file-kind helpers (from index.ts)
│   │   ├── windows/
│   │   │   └── mainWindow.ts           # NEW — createWindow() (from index.ts)
│   │   └── ipc/
│   │       ├── dialog.ipc.ts           # NEW — 5 dialog/fs channels + describeFile() (from index.ts)
│   │       └── app.ipc.ts              # NEW — 6 remaining channels (from index.ts)
│   │
│   ├── preload/
│   │   └── index.ts                    # unchanged (same window.api surface)
│   │
│   └── renderer/
│       └── src/
│           ├── App.vue                 # unchanged logic; migrated to Tailwind
│           ├── main.ts                 # unchanged; imports styles/tailwind.css instead of assets/main.css
│           ├── nativeBridge.ts         # REMOVED — moved to services/native.ts
│           │
│           ├── views/                  # unchanged — all 10 screens stay here (no pages/ rename)
│           │   └── *.vue                # migrated to Tailwind utilities + AppButton/AppSpinner/AppBadge/JobCard/EmptyState
│           │
│           ├── components/
│           │   ├── atoms/
│           │   │   ├── AppButton.vue    # NEW — consolidates ~20 duplicated button classes
│           │   │   ├── AppSpinner.vue   # NEW — consolidates 13-copy .spin/@keyframes block
│           │   │   └── AppBadge.vue     # NEW — consolidates 7 independent badge/pill implementations
│           │   ├── molecules/
│           │   │   ├── JobCard.vue      # NEW — consolidates byte-identical .job-card in 4 views
│           │   │   └── EmptyState.vue   # NEW — consolidates byte-identical .empty-state in 4 views
│           │   └── *.vue                # remaining 18 components stay flat — no confirmed duplication (research.md Audit a)
│           │
│           ├── services/
│           │   ├── api.ts               # RENAMED from apiClient.ts — unchanged HTTP functions/contracts
│           │   ├── websocket.ts         # NEW — subscribeJobProgress() extracted from apiClient.ts (real WS logic, research.md Audit d)
│           │   └── native.ts            # RENAMED from nativeBridge.ts — unchanged Electron-bridge wrapper
│           │
│           ├── store/                   # unchanged — no restructuring justified (research.md Audit e)
│           ├── composables/             # unchanged — no restructuring justified (research.md Audit e)
│           ├── i18n/                    # unchanged — 11 locales untouched
│           │
│           ├── styles/
│           │   └── tailwind.css         # NEW — @theme block mapping to theme.css's existing tokens + Tailwind directives
│           │
│           └── assets/
│               ├── theme.css            # unchanged content — remains the single source of truth for token *values*
│               ├── base.css             # PRUNED — dead --ev-c-* variables removed (research.md Audit b); resets kept
│               └── main.css             # PRUNED — component-specific rules migrated to Tailwind utilities per-file; imports styles/tailwind.css
│
├── electron.vite.config.ts              # updated: add @tailwindcss/vite plugin
├── tsconfig.web.json                    # updated if a new alias is added (see Aliases below)
└── package.json                         # + tailwindcss, @tailwindcss/vite (only new deps, per FR-015)
```

**Structure Decision**: no `domain/`/`application/`/`use-cases/`, no `organisms/`/`templates/`/
`pages/`, no `services/websocket/` folder (a single `websocket.ts` file, not a folder, since it's
one function's worth of logic) — each omission is a direct application of research.md's "found NOT
to be real duplication/no separable responsibility" findings, per constitution Principle X v2.4.0.
No new import aliases are introduced (`@renderer` already exists and is sufficient for the new
`services/`/`components/atoms/`/`components/molecules/` paths; adding `@services`/`@components`
aliases was considered and rejected — the existing single alias already keeps import depth
shallow, e.g. `@renderer/services/api`, and constitution Principle X forbids adding structure
without a confirmed need).

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
