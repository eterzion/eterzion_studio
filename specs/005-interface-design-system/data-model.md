# Data Model: Interface Design System

This feature has no persistence/domain-data model in the usual sense (no new API entities, no new
storage). The "entities" here are the design/code artifacts this refactor introduces or moves, and
the contract each one commits to.

## Design tokens (extend `theme.css`)

| Token | Value | Replaces |
|---|---|---|
| `--on-primary` | `#fff` | ~20 literal `#fff`/`#ffffff` occurrences used for text/icons on colored backgrounds |
| `--radius-full` | `999px` | ~20 literal `border-radius: 999px` occurrences (pill shape) |
| `--space-1-5` | `6px` | ~15 literal `gap: 6px` occurrences (sits between existing `--space-1`=4px and `--space-2`=8px) |

No other new tokens are added — every other candidate value found in research.md Audit (b) is
either already covered by an existing token (routed to it instead of adding a new one) or falls
below the 3-file duplication bar and is left as a literal.

## `AppButton.vue` (atom)

- **Props**: `variant: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'`,
  `size: 'sm' | 'md' | 'lg'` (default `'md'`), `loading?: boolean`, `disabled?: boolean`,
  `iconOnly?: boolean`.
- **Slots**: `default` (label), `icon` (leading icon, optional).
- **Replaces**: `.primary-btn`, `.secondary-btn`, `.btn-outline`, `.btn-primary`, `.btn-secondary`,
  `.danger-btn`, `.icon-btn`, `.copy-btn`, `.retry-btn`, and the other one-off button classes
  enumerated in research.md Audit (a), at every call site.
- **Contract**: visually equivalent to the closest-matching existing variant at each call site
  (no unrequested visual change), except the two confirmed defects it fixes by construction
  (unstyled `.primary-btn` instances; any button previously relying on the undefined `--border-1`).

## `AppSpinner.vue` (atom)

- **Props**: `size?: number` (default matches the most common existing usage, 16–20px range
  observed in research.md).
- **Replaces**: the 13 duplicated `.spin`/`@keyframes spin` CSS blocks and their paired
  `Loader2`/`LoaderCircle` icon usage.
- **Contract**: same animation timing (`1s linear infinite`) and rotation as today.

## `AppBadge.vue` (atom)

- **Props**: `tone: 'neutral' | 'success' | 'warning' | 'danger' | 'info'`,
  `shape?: 'rounded' | 'pill'` (default `'pill'`, matching the majority of existing usages).
- **Replaces**: `.chip`, `.credit-license-badge`, `.icon-badge` (badge-shape usage only — the
  license-status icon-badge's larger decorative ring stays a separate concern), `.version-badge`,
  `.license-pill`, `.status-badge`, `.license-error-badge`.
- **Contract**: same visual tone mapping per call site as today (e.g. a currently-green "active"
  badge stays visually green via `tone="success"`).

## `JobCard.vue` (molecule)

- **Props**: typed against the existing job shape already used by `VideoView.vue`/
  `AudioView.vue`/`ConverterView.vue`/`CompressConvertView.vue` (filename, status, progress,
  error message, thumbnail/preview reference) — the exact fields are read from the current
  byte-identical `.job-card` markup in those 4 files during implementation, not invented here.
- **Slots**: `actions` (per-view action buttons differ slightly — e.g. "reprocess" only in some
  flows — so the action row stays a slot, not a fixed prop list).
- **Replaces**: the 4-way duplicated `.job-card`/`.job-list` CSS and its paired markup.
- **Contract**: identical layout/spacing/status-color behavior in all 4 consuming views.

## `EmptyState.vue` (molecule)

- **Props**: `message: string` (goes through vue-i18n at the call site, not hardcoded inside the
  component), `actionLabel?: string`; emits `action` when the action button is clicked. No
  standalone `icon` prop — the 4 byte-identical empty states audited have no icon above the
  message, only inside the action button, exposed via an `icon` slot on the button.
- **Replaces**: the 4-way byte-identical `.empty-state` CSS + near-identical markup in
  VideoView/AudioView/ConverterView/CompressConvertView. `ImageEditorView.vue`'s and
  `HistoryView.vue`'s independently-styled empty states are NOT migrated to this component (research.md
  Audit (a) — they are not part of the confirmed 4-file duplication; forcing them in would be an
  unjustified visual change).

## `services/api.ts` (renamed from `apiClient.ts`)

- **Contract**: byte-identical exported function signatures and request/response shapes to
  today's `apiClient.ts`, minus `subscribeJobProgress` (moved to `services/websocket.ts`). No
  HTTP path, method, header, or payload shape changes — this is a file rename plus import-path
  updates at every call site, not a rewrite.

## `services/websocket.ts` (extracted from `apiClient.ts`)

- **Contract**: exports `subscribeJobProgress(jobId, onUpdate, onError)` with the exact same
  signature and behavior as today (same URL construction, same message handling, same
  disconnect/error semantics). `store/jobs.ts` and the 4 views that call it directly update their
  import path only.

## `services/native.ts` (renamed from `nativeBridge.ts`)

- **Contract**: byte-identical exported surface (`api`, `hasNativeApi`) to today's
  `nativeBridge.ts` — no change to what `window.api` operations are wrapped or how.

## `main/protocols/mediaProtocol.ts`, `main/windows/mainWindow.ts`, `main/ipc/dialog.ipc.ts`,
## `main/ipc/app.ipc.ts`

- **Contract**: each exports the exact function(s) `index.ts` calls today at the same lifecycle
  points, with identical behavior — protocol scheme name, IPC channel names, dialog options,
  window configuration, and app-lifecycle hook wiring are all preserved exactly (research.md
  Audit (g) enumerates every channel/responsibility that must survive the split unchanged).
