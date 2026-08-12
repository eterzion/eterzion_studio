# Feature Specification: Interface Design System — Atomic Design + Tailwind CSS

**Feature Branch**: `005-interface-design-system`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Refatoração completa da aplicação desktop em interface/ para Atomic
Design + Design System + Tailwind CSS, com camada services/, reorganização do main/preload do
Electron e tipagem TypeScript fortalecida — preservando 100% do comportamento e das funcionalidades
existentes (10 telas, 11 idiomas, contratos HTTP/WebSocket com api/, empacotamento Electron)."

## User Scenarios & Testing *(mandatory)*

<!--
  This feature has no end-user-visible behavior change by design (FR-001). Its "users" are the
  people who build and maintain interface/: whoever adds a screen, fixes a bug, or reviews a PR
  next. Each story below is independently testable and independently valuable, per the mandatory
  audit-first constraint added to Principle X (v2.4.0) — no story creates structure before its own
  duplication/justification is confirmed.
-->

### User Story 1 - Consistent, reusable UI building blocks (Priority: P1)

A developer adding a new screen or fixing a bug in an existing one needs a small, predictable set
of UI building blocks (buttons, inputs, cards, modals, badges, form fields) instead of hunting
across 19 components for one that's "close enough" and copy-pasting markup and styles.

**Why this priority**: This is the concrete pain point named in the request — duplicated
button/card/form-field/modal implementations across screens. It's also the foundation every other
story depends on: services and typing improvements are much less useful if the UI layer above them
still duplicates itself.

**Independent Test**: Can be fully tested by auditing `components/` and every `.vue` file's
`<style scoped>` block for genuinely repeated visual/behavioral patterns, consolidating only the
confirmed ones into typed, variant-driven components, and verifying every screen that used the old
markup renders identically after the swap.

**Acceptance Scenarios**:

1. **Given** two or more screens today implement visually-equivalent buttons with separate markup/CSS, **When** the audit confirms the duplication, **Then** those call sites are consolidated into one button component accepting a `variant`/`size`/`loading`/`disabled` prop set, with no visual change.
2. **Given** a UI pattern appears in exactly one place in the app, **When** the audit runs, **Then** no new reusable component is created for it — it stays where it is.
3. **Given** the consolidation is complete, **When** a developer greps for the old per-purpose component names (e.g. a hypothetical `SaveButton.vue`), **Then** none remain — the old and new implementations do not coexist.

---

### User Story 2 - One design system driving Tailwind, not scattered literals (Priority: P1)

A developer changing a color, spacing value, or radius today has to find and edit the same literal
value in multiple `.vue` files and/or `base.css`/`main.css`/`theme.css`, with no guarantee they
found every occurrence. They need one place that defines what "the app's primary color" or "the
app's card radius" is.

**Why this priority**: Equal priority to Story 1 — the design tokens are what make Story 1's
components consistent instead of independently re-guessing the same values. The two are usually
built together, but each is independently verifiable.

**Independent Test**: Can be tested by confirming Tailwind is configured with semantic theme tokens
derived from the real current values in `theme.css`/`base.css`/`main.css`, that the app's rendered
colors/spacing/typography are pixel-equivalent to before the change (no visual regression), and
that legacy CSS files contain only what a documented technical justification (Electron-specific
integration, custom scrollbar, complex animation) keeps there.

**Acceptance Scenarios**:

1. **Given** the current app has a defined visual language (colors, spacing scale, radii, shadows) expressed as scattered literals, **When** the design system is introduced, **Then** the same visual language is expressed as named Tailwind theme tokens, and the rendered app looks the same.
2. **Given** a component's old `<style scoped>` block only contained values expressible in Tailwind utilities, **When** it is migrated, **Then** the `<style>` block is removed, not left dormant alongside the new classes.
3. **Given** a component's old CSS contains something Tailwind genuinely cannot express, **When** it is migrated, **Then** the necessary hand-written CSS remains, with the specific technical reason evident from context (comment or obvious necessity, e.g. a custom scrollbar).

---

### User Story 3 - Centralized, typed access to the backend and to Electron (Priority: P2)

A developer wiring up a new screen's HTTP calls or native file-picker interaction today has to know
which of several components already call `fetch(...)` or `window.api...` directly, and repeat the
same request/response shape by hand. They need one typed entry point per concern (HTTP to `api/`,
Electron bridge) instead of ad hoc calls spread across components.

**Why this priority**: Valuable and reduces real risk (a typo'd endpoint URL, an inconsistent error
shape), but the app functions correctly today without it — this is a maintainability improvement,
not a fix for a user-facing defect, so it ranks below the two UI-consolidation stories that address
directly-named pain points.

**Independent Test**: Can be tested by confirming no `.vue` file under `views/` or `components/`
calls `fetch()` or `window.api.*` directly after the change (all such calls flow through the new
`services/` layer), and that every HTTP request/response shape has an explicit TypeScript type with
no behavioral change to what is sent or received.

**Acceptance Scenarios**:

1. **Given** `apiClient.ts` and `nativeBridge.ts` today centralize *most* but not all backend/Electron access, **When** the audit finds a component bypassing them, **Then** that call is routed through the appropriate service, with the exact same request made.
2. **Given** the app has no real WebSocket traffic today (confirmed by audit, not assumed), **When** the services layer is built, **Then** no `services/websocket/` folder is created.
3. **Given** the app does have real WebSocket traffic today, **When** the services layer is built, **Then** `services/websocket/` is created and centralizes connection/reconnect/listener logic that today is spread across call sites, with identical protocol behavior.

---

### User Story 4 - A maintainable Electron main process (Priority: P3)

A developer debugging a startup issue (window doesn't open, the local API doesn't start, the
`astros-media://` protocol serves the wrong file) today has to read through one `index.ts` that
mixes window creation, protocol registration, IPC handler registration, and API process management.
They need each concern in its own module.

**Why this priority**: Lowest priority because `src/main/index.ts` is read far less often than
`components/`/`views/`, and the current file, while doing several things, is not itself broken —
this is a pure maintainability improvement with the smallest blast radius if deferred.

**Independent Test**: Can be tested by confirming the app still opens a window, starts/stops the
local API, serves media through the custom protocol, and answers every IPC channel identically
after `index.ts` is split into single-responsibility modules (window creation, protocol
registration, IPC registration, API process orchestration) with `index.ts` reduced to
bootstrapping/wiring those modules together.

**Acceptance Scenarios**:

1. **Given** the app currently starts, connects to the local API, and serves preview images through `astros-media://`, **When** `index.ts`'s responsibilities are split into modules, **Then** all three behaviors are unchanged.
2. **Given** the preload script currently exposes a fixed set of `window.api` operations, **When** this story is implemented, **Then** the same operations are exposed with the same names and signatures — nothing is added or removed from the public bridge surface without a corresponding functional requirement elsewhere in this spec.

---

### Edge Cases

- What happens when the audit (Story 1/2) finds a component that is *almost* duplicated but has a
  genuine behavioral difference (e.g. two "cards" where one needs a different overflow behavior)?
  → It is not force-merged; the difference is preserved, either as a documented variant/prop or as
  a separate component, per Principle X's "no abstraction without a real consumer" and "genuine
  technical separation still stands" rules.
- What happens when a screen's current visual layout is inconsistent with another screen's
  equivalent element in a way that looks like a bug (e.g. two different button paddings for the
  same visual role)? → This is the one case where a visual change is permitted (FR-003); it must be
  called out explicitly as a confirmed inconsistency, not silently "fixed" as a side effect.
- What happens if Tailwind's installed-version-compatible configuration cannot express a currently
  used CSS feature (e.g. a specific animation curve)? → That rule stays as hand-written CSS with
  its necessity evident (FR-004); it is not a blocker for the rest of the migration.
- What happens to a store, composable, or component confirmed to be genuinely dead (no remaining
  caller) during the audit? → It is deleted in the same body of work, not archived (constitution
  Principle X, "dead code is deleted, not archived").
- What happens if splitting `apiClient.ts` into `services/api/*` would require inventing a
  WebSocket/native sub-service that has nothing real to centralize? → That sub-service is not
  created (FR-007; Principle X v2.4.0's explicit "no empty scaffold" rule).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The refactor MUST NOT change any user-observable behavior of the application — all
  10 existing screens (Home, ImageEditor, Video, Audio, Converter, CompressConvert, History,
  Settings, Components, LicenseActivation) MUST continue to exist and function identically from a
  user's perspective, except for visual corrections explicitly justified under FR-003.
- **FR-002**: All 11 existing languages (pt-BR, pt-PT, en, es, fr, de, it, ja, ko, ru, zh) MUST
  continue to work; no visible string introduced or touched during the refactor may be hardcoded —
  it MUST go through the existing vue-i18n system.
- **FR-003**: A visual change (color, spacing, sizing, layout) is permitted only where it corrects
  a *confirmed* inconsistency between two or more screens that should share the same visual
  treatment. Every such change MUST be identifiable as a deliberate fix, not an incidental result of
  the CSS/Tailwind migration.
- **FR-004**: The system MUST replace `base.css`/`main.css`/`theme.css` with Tailwind CSS utilities
  and a semantic design-token theme configuration, derived from the real values currently in those
  files, wherever Tailwind can express the need. Hand-written CSS MAY remain only where a specific,
  identifiable technical reason exists (Electron-specific integration, custom scrollbar styling,
  complex pseudo-elements, third-party library overrides, non-trivial animation) — not for
  convenience once an equivalent utility exists.
- **FR-005**: Before any Atomic Design tier (atoms/molecules/organisms/templates) is introduced
  into `components/`, a concrete audit of existing components and view-level markup MUST identify
  the specific, named instances of duplication that justify each tier. A tier MUST NOT be created
  to hold only one or two members that could as easily stay in a flatter structure.
- **FR-006**: Reusable UI components (buttons, inputs, cards, modals, badges, and any other pattern
  the audit confirms as duplicated) MUST be consolidated into single components with a typed
  variant/size/state prop API (e.g. `variant`, `size`, `loading`, `disabled`), replacing multiple
  independent single-purpose implementations of the same visual role. `any` MUST NOT be used in
  these components' prop or emit types.
- **FR-007**: HTTP communication with `api/astros_upscale_api` and Electron-bridge access currently
  spread across `apiClient.ts`, `nativeBridge.ts`, and any component calling `fetch`/`window.api`
  directly MUST be consolidated into a `services/` layer (at minimum `services/api/`, and
  `services/native/` or an equivalent Electron-bridge boundary). A `services/websocket/` (or
  equivalent) sub-layer MUST be created only if the audit confirms the application has real
  WebSocket traffic to centralize; it MUST NOT be created as an empty scaffold otherwise.
- **FR-008**: No existing HTTP request/response contract with `api/astros_upscale_api` or the
  licensing flow with `api/astros_licensing_service` MAY change as a result of this refactor —
  same paths, methods, request/response shapes, status codes, and (if applicable per FR-007) the
  same WebSocket message behavior.
- **FR-009**: `src/main/index.ts`'s responsibilities (window creation, `astros-media://` protocol
  registration, IPC handler registration, local-API process orchestration via `apiProcess.ts`) MUST
  be separated into modules with a single clear responsibility each, with `index.ts` reduced to
  bootstrapping those modules. Behavior of window creation, the custom protocol, every IPC channel,
  and API process start/stop MUST remain identical.
- **FR-010**: The Electron preload script MUST continue to expose only the specific operations it
  exposes today via `contextBridge` — the same operation names and signatures. `contextIsolation`
  MUST remain `true` and `nodeIntegration` MUST remain `false`; no whole Node.js module (`fs`,
  `child_process`, `shell`, `process`) MAY be exposed to the renderer.
- **FR-011**: TypeScript types MUST be strengthened across HTTP request/response payloads, IPC
  channel payloads, store state, and component props/emits touched by this refactor. New or
  modified code introduced by this refactor MUST NOT use `any`; `unknown` MUST be used at external
  boundaries whose data still requires validation.
- **FR-012**: FFmpeg bundling (`scripts/fetch-ffmpeg.mjs`) and `electron-builder` packaging for
  Windows (NSIS), macOS (dmg), and Linux (AppImage/snap/deb) MUST continue to function without
  modification to their externally observable output, for both an unpackaged dev build and a
  packaged production build.
- **FR-013**: Any component, store, composable, CSS rule, or file confirmed during the audit to
  have no remaining caller/consumer MUST be deleted as part of this refactor, not archived under a
  `legacy`/`old`/`v1`/`backup`-style name, and MUST NOT coexist alongside its replacement once the
  replacement is in place.
- **FR-014**: `interface/README.md` MUST be updated at the end of the refactor to describe the
  actual final structure and styling stack (Tailwind CSS, replacing the current inaccurate mention),
  not the reference structure originally proposed.
- **FR-015**: No dependency MAY be added beyond Tailwind CSS and its direct build-tooling
  requirements (e.g. PostCSS/Autoprefixer if required by the verified Tailwind version) without a
  concrete technical justification recorded in the implementation plan.
- **FR-016**: At completion, `npm run typecheck`, `npm run lint`, and `npm run build` MUST all pass
  with zero errors attributable to this refactor.

### Key Entities

- **Design token**: A named, semantic value (e.g. `color-surface`, `spacing-4`, `radius-lg`)
  defined once in the Tailwind theme configuration and referenced by utility classes across the
  app, replacing a literal value previously duplicated across CSS files/components.
- **UI component (Atomic Design tier)**: A `.vue` file classified as an atom, molecule, organism,
  or template only when the audit confirms the tier is warranted; carries a typed prop/emit
  contract and, where applicable, named variants.
- **Service module**: A TypeScript module under `services/` owning one category of external
  communication (HTTP to `api/`, Electron native bridge, and WebSocket only if justified), exposing
  typed functions that replace direct `fetch`/`window.api` calls from UI code.
- **Main-process module**: A TypeScript module under `src/main/` owning one Electron main-process
  responsibility (window lifecycle, protocol registration, IPC registration, API process
  orchestration), replacing a single responsibility currently mixed into `index.ts`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 10 existing screens remain reachable and usable with the same functionality,
  verified by exercising each screen's primary flow after the refactor.
- **SC-002**: All 11 languages continue to display correctly with no hardcoded strings introduced,
  verified by switching the app's language and checking screens touched by this refactor.
- **SC-003**: The number of independent implementations of the same visual UI role (button, card,
  modal, form field, badge) confirmed as duplicated during the audit is reduced to one canonical,
  variant-driven implementation per role, with zero of the old implementations remaining in the
  codebase.
- **SC-004**: Zero hand-written CSS rule remains for a value expressible in the Tailwind
  configuration once the migration completes, except rules with a recorded technical justification.
- **SC-005**: `npm run typecheck`, `npm run lint`, and `npm run build` complete successfully (exit
  code 0) after the refactor, run directly and not assumed.
- **SC-006**: A person opening the app before and after the refactor, without being told a
  refactor happened, cannot identify a visual difference except in locations explicitly documented
  as intentional inconsistency fixes (FR-003).
- **SC-007**: The packaged Electron application (at least one platform's build) starts, connects to
  the local API, and completes one full media-processing action end-to-end after the refactor.

## Assumptions

- The project has no existing automated frontend test suite; "regression-free" is verified through
  the existing quality gates (`typecheck`, `lint`, `build`) plus manual verification of each screen,
  not through new automated tests (creating a test suite was not requested and is out of scope).
  **Constitutional note**: Principle VIII ("Every migration and every new feature MUST have
  tests") is written without an explicit `interface/` carve-out, and its rationale section is
  framed around processing pipelines and licence enforcement — backend concerns `interface/` does
  not itself implement. `interface/` has never had an automated test suite in this repository's
  history (predating this feature), so this is a pre-existing, project-wide gap this feature does
  not introduce and is not in scope to close. It is recorded here explicitly, per `/speckit.analyze`
  findings, rather than silently assumed compliant — a follow-up feature to establish frontend test
  coverage (e.g. component tests via Vitest + Vue Test Utils) is the correct place to resolve the
  gap, not this refactor.
- SC-002 ("all 11 languages continue to display correctly") is validated by sampling 3 locales
  (quickstart.md step 4), not exhaustively re-checking all 11 screen-by-screen. This is a
  deliberate scope decision: every locale draws from the same `i18n/locales/*.json` key structure,
  which this feature does not modify (FR-002) — sampling verifies the *mechanism* (vue-i18n wiring,
  no hardcoded strings introduced) still works, which generalizes across locales; it does not
  re-verify translation *content* accuracy, which was never this feature's concern.
- "The audit" referenced throughout is performed once, early, as part of `/speckit.plan`, and its
  concrete findings (which components/styles are duplicated, whether WebSocket traffic exists,
  which files are dead) are recorded there and drive every downstream structural decision — this
  spec intentionally does not pre-decide those findings.
- Tailwind CSS's specific version is not pinned by this spec; the implementation plan MUST verify
  compatibility with the project's actual installed Vue/Vite/electron-vite/TypeScript versions
  before configuring it, per constitution Principle X v2.4.0.
- "Real WebSocket traffic" in FR-007/Edge Cases refers to whatever the current codebase actually
  implements — this spec does not assume an answer either way; the plan's audit determines it.
- Packaging verification (SC-007) is performed on at least the developer's current platform
  (Windows, per repository environment); full cross-platform packaging verification on macOS/Linux
  is not required if those build environments are unavailable, but any such gap MUST be reported
  explicitly rather than silently assumed passing.
