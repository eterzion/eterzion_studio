<!--
Sync Impact Report — constitution amendment
Version change: 3.0.0 → 4.0.0 (MAJOR — a principle now permits what it previously forbade)

MAJOR bump rationale: Principle V's technical-disclosure exception previously required the
disclosed view to be "informational only" and forbade "any choice that changes processing
results". It now permits exactly such choices, in exactly one place — the Compression Centre's
Advanced mode — under five cumulative conditions. Redefining a principle so it permits what it
previously forbade is MAJOR by this document's own versioning policy.

Modified principles:
  V. Models Are Internal — second bounded exception added, for user-controlled encoding
     parameters in the Compression Centre. The AI path (upscale, audio restoration) is
     explicitly excluded and remains under the unmodified rule.

Added principles: none
Renamed principles: none
Removed sections: none

Governance: review-gate list unchanged.

Migration note: no existing code becomes non-compliant. The exception is additive and scoped to
a feature that does not yet exist. `test_no_codec_leak.py` continues to hold for every video
route it covers — those routes belong to the editor, not to the Compression Centre.

Risk accepted, and by whom: the product owner (Eric Inácio), on 2026-08-21, accepts that the API
surface grows and that parts of it become coupled to codec vocabulary that may later need to
change. See the exception's own rationale for why the containment conditions bound that risk.

Deferred / follow-up TODOs: none. No placeholder tokens remain in this document.

---
Previous report
---------------
Version change: 2.6.0 → 3.0.0 (MAJOR — a principle now permits what it previously forbade)

MAJOR bump rationale: Principle XIII previously forbade, without exception, a client supplying a
filesystem path the API reads. It now permits exactly that, for exactly one registration route,
under four cumulative conditions. This document's own versioning policy states that redefining a
principle so it permits what it previously forbade is MAJOR — the same reasoning that made the
v2.0.0 bounded exception to Principle V a MAJOR change.

Modified principles:
  XIII. External Processes Are Invoked Structurally, Never Composed — bounded exception added to
        the "Files are addressed by internal identifier" clause, for a single registration route
        whose path comes from the operating system's own file dialog.
  XIV.  Interface Text Is Translatable By Default — factual correction only: the project ships 11
        locale files, not 12. Corrected in the principle's rationale and in the v2.6.0 amendment
        log entry. No normative change.

Added principles: none
Renamed principles: none
Removed sections: none

Governance: review-gate list unchanged.

Deferred / follow-up TODOs: none. No placeholder tokens remain in this document.

---
Previous report
---------------
Version change: 2.5.0 → 2.6.0 (MINOR — principles added, guidance materially expanded)

Added principles:
  XIII. External Processes Are Invoked Structurally, Never Composed
  XIV.  Interface Text Is Translatable By Default
  XV.   Source Media Is Never Overwritten

Modified principles (extended, not redefined):
  VII. Hardware Adaptive — every media operation must declare explicit ceilings and refuse
       oversized work before starting, naming the limiting factor.
  X.   Interface Structure Is Adapted, Not Templated — component decomposition rule added;
       explicitly non-retroactive (ImageEditorView.vue named as exempt).
  XI.  API Structure Is Consolidated By Domain, Not By Class — the "does it read as coherent"
       judgment is replaced by three testable conditions for justifying a new module.

Renamed principles: none
Removed sections: none

Governance: review-gate list extended with XIII, XIV, XV.

Deferred / follow-up TODOs: none. No placeholder tokens remain in this document.

Non-governance intents deferred to later Spec Kit stages (NOT executed here):
  - the video adjustments/effects/transform/trim/audio/export subsystem
  - the FFmpeg-backed processing, job, thumbnail and preview services
  - the custom video player component tree
  These are specification and implementation work; see Next Actions in the command output.
-->

<!--
SYNC IMPACT REPORT
==================
Version change: 2.4.0 → 2.5.0 (2026-08-13)

MINOR bump rationale: a new principle (XII. AI Audio Restoration Is Bounded, Provider-Isolated, and
Never Auto-Trusted) was added. It adds rules that did not previously exist — it does not remove or
weaken anything, so it is not a MAJOR change; it is more than a wording clarification, so it is not
a PATCH.

Added principles: XII. AI Audio Restoration Is Bounded, Provider-Isolated, and Never Auto-Trusted
(deterministic DSP — LUFS/peak/EQ/dynamics/stereo/limiting/normalisation/dithering — is never
replaced by AI, only supplemented when problem-detection identifies a real need; an AI provider's
output is never the final master, it always passes back through corrective DSP and a Quality Guard
that compares objective before/after metrics and can reject/reduce AI processing; AI models are
reachable only through an isolated `AudioRestorationProvider`-style adapter, never called directly
by orchestration code, with third-party inference code kept isolated behind it; lazy loading and
automatic DSP-only fallback are mandatory for every AI audio provider; heavy AI inference runs
isolated from the main API process, consistent with the existing isolated-worker architecture;
heavy ML dependencies of an audio provider are isolated from the main backend's dependency set;
restoration MUST preserve original musical intent — timbre, instrumentation, vocals, stereo
placement, transients, artistic ambience — restoration is not remixing; licensing rigor for audio
AI dependencies is identical to Principle IV, with conditional licences explicitly recorded as an
accepted, monitored risk in `docs/models/MODEL_LICENSES.md`, never assumed permissive).
Modified sections: Governance → Compliance review (added Principle XII to the mandatory review
gate list).
Removed sections: none.
Templates requiring review: none — the addition is additive and does not contradict existing
guidance in spec/plan/tasks template guidance.

---
Previous report
---------------
Version change: 2.3.0 → 2.4.0 (2026-08-12)

MINOR bump rationale: Principle X (Interface Structure Is Adapted, Not Templated) was materially
expanded — it adds permission and constraints that did not previously exist (Atomic Design tiers,
Tailwind design tokens, and a `services/` split, each conditional on a confirmed duplication audit)
without removing or weakening any existing rule, so it is not a MAJOR change; it is more than a
wording clarification, so it is not a PATCH.

Modified principles: X. Interface Structure Is Adapted, Not Templated (unchanged title — the
"component organisation follows reuse, not a fixed taxonomy" clause is extended to state that
Atomic Design tiers MAY be adopted once an audit confirms real, repeated component duplication;
a new clause permits a Tailwind-based design system to replace hand-written CSS under the same
"real duplication, not a template" test, with a hard requirement to preserve existing visual
behaviour; the "external-access code is isolated" clause is extended to cover a possible
`services/api|websocket|native` split replacing `apiClient.ts`/`nativeBridge.ts`, forbidding empty
scaffolds for traffic that doesn't exist; "no abstraction without a real consumer" and "dead code
deleted, not archived" are restated as applying identically to these new allowances, not relaxed
by them).
Modified sections: none outside Principle X — Governance's compliance review gate list already
names Principle X, no change needed there.
Removed sections: none.
Templates requiring review: none — the change narrows/extends conditions under an existing
principle and does not contradict spec/plan/tasks template guidance.

---
Previous report
---------------
Version change: 2.2.0 → 2.3.0 (2026-08-12)

MINOR bump rationale: a new principle (XI. API Structure Is Consolidated By Domain, Not By Class)
was added. It adds rules that did not previously exist — it does not remove or weaken anything, so
it is not a MAJOR change; it is more than a wording clarification, so it is not a PATCH.

Added principles: XI. API Structure Is Consolidated By Domain, Not By Class (fragmented
single-responsibility files inside `api/` consolidate into domain-cohesive modules —
processing/media/jobs/licensing/security/routes/schemas/payments/database — instead of one file
per class or one directory per technical layer; genuine technical separation still stands where a
responsibility is truly independent or a merge would stop reading as one coherent domain; no
behaviour change from consolidation — HTTP contracts, WebSocket contracts and processing/licensing/
payment logic are preserved exactly; empty pre-consolidation directories are removed, and
compatibility shims are folded in rather than deleted blind).
Modified sections: Governance → Compliance review (added Principle XI to the mandatory review gate
list).
Removed sections: none.
Templates requiring review: none — the addition is additive and does not contradict existing
guidance in spec/plan/tasks templates.

---
Previous report
---------------
Version change: 2.1.0 → 2.2.0 (2026-08-12)

MINOR bump rationale: a new principle (X. Interface Structure Is Adapted, Not Templated) was
added. It adds rules that did not previously exist — it does not remove or weaken anything, so
it is not a MAJOR change; it is more than a wording clarification, so it is not a PATCH.

Added principles: X. Interface Structure Is Adapted, Not Templated (no empty domain/application
layers inside interface/ — that logic already lives in api/ per Principle IX; component
organisation follows reuse, not a rigid 5-tier taxonomy; the Electron bridge and the HTTP/WS
client are isolated and named for what they do, not given DDD-style repository/port ceremony; no
abstraction without a real consumer; dead code is deleted, not archived under legacy/old/v1
naming).
Modified sections: Governance → Compliance review (added Principle X to the mandatory review
gate list).
Removed sections: none.
Templates requiring review: none — the addition is additive and does not contradict existing
guidance in spec/plan/tasks templates.

---
Previous report
---------------
Version change: 2.0.0 → 2.1.0 (2026-08-12)

MINOR bump rationale: a new principle (IX. Two-Layer Architecture) was added. It adds a rule that
did not previously exist — it does not remove or weaken anything, so it is not a MAJOR change; it
is more than a wording clarification, so it is not a PATCH.

Added principles: IX. Two-Layer Architecture (interface/ ↔ api/ separation; no CLI/command layer
between them; the licensing service stays a separate process even though it is organised inside
api/).
Modified sections: Governance → Compliance review (added Principle IX to the mandatory review
gate list).
Removed sections: none.
Templates requiring review: none — the addition is additive and does not contradict existing
guidance in spec/plan/tasks templates.

---
Previous report
---------------
Version change: 1.0.0 → 2.0.0 (2026-08-08)

MAJOR bump rationale: Principle V was redefined in a way that PERMITS what it previously
FORBADE (exposing model names in an opt-in technical details view). Per this document's own
versioning policy, permitting a previously forbidden action is a MAJOR change. See the
Amendment log at the end of this file for the full rationale, including the Principle IV/V
contradiction it resolves.

Modified principles: V. Models Are Internal (scope narrowed to default surfaces + selection;
bounded exception added for informational technical disclosure).
Added sections: Amendment log.
Removed sections: none.
Templates requiring review: none — the change is permissive, not restrictive.

---
Previous report
---------------
Version change: (unratified template) → 1.0.0

Rationale for 1.0.0: first ratification. The file previously contained only unfilled
template placeholders; no prior governance existed to amend. This establishes the
initial governing principle set, so it is a MAJOR (initial) release rather than an
increment of an existing version.

Principles defined (all new):
  I.    Spec First
  II.   Reuse First
  III.  Performance First
  IV.   Commercial License Only
  V.    Models Are Internal
  VI.   No AI Without Benefit
  VII.  Hardware Adaptive
  VIII. Tests Required

Sections added:
  - Core Principles (8 principles)
  - Licensing and Distribution Constraints
  - Development Workflow
  - Governance

Sections removed: none (template placeholders replaced in place).

Templates requiring review for consistency:
  - .specify/templates/spec-template.md      — no changes required (principle-agnostic)
  - .specify/templates/plan-template.md      — no changes required (principle-agnostic)
  - .specify/templates/tasks-template.md     — no changes required (principle-agnostic)
  - .specify/templates/checklist-template.md — no changes required (principle-agnostic)

Deferred TODOs: none. All placeholders resolved.
-->

# Astros Constitution

Astros is a commercial desktop media processing product. It enhances, compresses and converts
images, video and audio. It is distributed as a paid, closed-source application.

Those three facts — commercial, desktop, closed-source — are the reason every principle below
exists. A rule that would be optional in a research project or an internal tool is not optional
here.

## Core Principles

### I. Spec First

No relevant feature MAY be implemented without a specification. The mandatory order is:

```
Spec → Plan → Tasks → Code
```

The specification is the source of truth. When code and spec disagree, the spec is authoritative
until formally amended — the code is the defect.

"Relevant" means: anything that changes what the product does, what it outputs, what it costs in
time or hardware, or what the user sees. Bug fixes that restore documented behaviour, and purely
mechanical refactors that preserve behaviour, are exempt.

**Rationale:** this project consolidates three codebases with overlapping functionality. Without a
written source of truth, "which implementation is correct" becomes unanswerable and the
consolidation reproduces the duplication it was meant to remove.

### II. Reuse First

Existing code MUST be analysed before any new implementation is written. The mandatory
decision order is:

```
Exists in Astros?          → no ↓
Exists in astros_upscale?  → no ↓
Exists in astros_audio_enhance? → no ↓
Then, and only then, create new
```

When an implementation exists, the mandatory progression is **REUSE → REFACTOR → ADAPT → INTEGRATE**.

Creating a new implementation of existing functionality MUST be justified in writing, in the plan,
with a concrete technical reason. "Cleaner", "more modern", or "easier to understand" are not
sufficient reasons on their own.

Three implementations of the same functionality MUST NOT coexist. Before removing any existing
code, its fate MUST be recorded explicitly as one of: **KEEP · MIGRATE · REFACTOR · REPLACE · REMOVE**.

**Rationale:** the working code in these repositories encodes hard-won knowledge about real
failure modes (codec quirks, memory limits, platform differences). Rewriting discards that
knowledge silently.

### III. Performance First

The global priority order, applied whenever a trade-off must be resolved, is:

```
1. Speed
2. Stability
3. Quality
4. Efficient hardware use
5. Simple UX
```

Speed ranking first does NOT authorise shipping something broken. It means: when two correct
implementations differ, the faster one wins; and when a quality improvement multiplies processing
time, it MUST be justified by a measured, perceptible gain — not assumed.

Any claim that a change improves or preserves performance MUST be backed by a measurement.
Unmeasured performance claims MUST NOT be recorded as fact.

**Rationale:** on a desktop product the user watches the progress bar. Latency is the feature they
experience most directly.

### IV. Commercial License Only

Only models, weights, datasets, libraries and components whose licence **explicitly** permits
commercial use MAY be included in the product.

The following are NOT evidence of commercial permission: "open source", "published on GitHub",
"publicly downloadable", "pip install works", a permissive licence on a *mirror*, or a permissive
licence recorded in a third-party catalogue.

Mandatory verification rules:

- **Code and weights MUST be verified separately.** A repository under MIT may distribute weights
  that are not MIT.
- **Embedded third-party components contaminate the whole.** A permissive licence at the top of a
  LICENSE file is void if the body declares non-commercial dependencies.
- **Training datasets MUST be checked** where they can restrict the resulting weights.
- **Absence of a licence file means all rights reserved.** That is a rejection, not a gap.
- **Doubt is rejection.** Anything indeterminate MUST be treated as rejected, and recorded as
  INDETERMINATE so authorisation can be sought later.
- Every verdict MUST cite the exact source URL and the literal text it rests on, with a
  verification date.

Verified licences MUST be recorded in `docs/models/MODEL_LICENSES.md`. That file is authoritative.

Attribution obligations imposed by approved licences (CC-BY, Apache-2.0 NOTICE, BSD disclaimers)
MUST be honoured in the shipped product UI, not only in source files.

**Rationale:** the product is sold. A non-commercial component is not a licensing footnote — it is
an infringement in every copy shipped, and it cannot be recalled once distributed.

### V. Models Are Internal

Models are infrastructure. The user MUST NEVER be required to see, choose, or reason about one in
order to use the product.

No default surface — home, editor, queue, history, settings, error messages, output filenames —
MAY expose a model name, checkpoint, model id, engine name, neural architecture, or internal
inference parameter.

The interface offers exactly three levels, and only where they are meaningful:

```
Rápido · Equilibrado · Qualidade
```

The API contract accepts intent, never implementation:

```json
{ "mediaType": "image", "operation": "upscale", "scale": 4, "profile": "fast" }
```

and MUST NOT accept:

```json
{ "model": "RealESRGAN_x4plus" }
```

No UI MAY offer model selection, or make the user's result depend on a model they picked.

**Bounded exception — technical disclosure.** A components/updates screen MAY present an
explicitly opt-in technical details view exposing model name, version, provenance and licence.
This exception is narrow and conditional:

- The screen's default presentation MUST speak in capabilities ("Melhoria de imagem — Qualidade"),
  never in model names.
- The technical view MUST be informational only. It MUST NOT offer selection, substitution, or any
  choice that changes processing results.
- Where a licence requires attribution, this view MUST carry it.

**Bounded exception — user-controlled encoding parameters.** The Compression Centre MAY expose
codec, container, CRF/CQ, bitrate, encoder selection, encoding preset, pixel format, sample rate
and channel layout as controls that DO change the result. This exception is narrow and
cumulative — all five conditions MUST hold:

1. **Compression only.** It applies to transcoding and re-encoding. It does NOT apply to the AI
   path: upscale, audio restoration and every other operation that runs a model stay under the
   unmodified rule above, where the user names intent and the backend resolves everything else.
2. **Advanced mode is opt-in.** The default (Basic) presentation MUST offer only preset, quality,
   format, resolution and target size. A person who never opens Advanced MUST never meet a codec
   name.
3. **Only what the machine has.** Every technical option offered MUST be gated on a functional
   probe, per Principle XIII. Offering an encoder this machine cannot run is the same defect
   whether the user chose it or the backend did.
4. **Intent still resolves without it.** Every technical control MUST have a working automatic
   value. "Automático" is not a placeholder; it is the path Basic mode uses, and Advanced mode
   MUST remain fully usable while every control is left on it.
5. **Licensing is not a user choice.** The Licensing and Distribution Constraints below are NOT
   subject to this exception. A GPL encoder MUST NOT become available because a person asked for
   it in Advanced mode.

**Rationale:** the harm this principle prevents is forcing an engineering decision onto someone who
cannot evaluate it, and welding the product to an implementation detail that must stay free to
change. Neither harm occurs when a user deliberately opens a details panel to read what is
installed and under what licence. Without this exception the principle would also contradict
Principle IV, which requires attribution to be visible in the shipped product — and attribution is
impossible without naming what is being attributed.

The second exception rests on the same reading. Compression is not a place where the product knows
better: a person targeting an 8 MB upload limit, a specific player's codec support, or an archival
master has a constraint the backend cannot infer. Refusing them CRF is not protecting them from an
engineering decision — it is withholding the only control that answers their question. The harm the
principle names returns only if that vocabulary reaches someone who did not ask for it, which is
what condition 2 prevents, or if it becomes the only way to get a result, which is what condition 4
prevents.

The risk being accepted is real and is recorded in the amendment log: the API surface grows, and
part of it becomes coupled to codec names that may later need to change. It is bounded by
conditions 1 and 3 — the AI path, where implementation churn is highest, is untouched, and no
option outlives the runtime's ability to serve it.

### VI. No AI Without Benefit

AI MUST NOT be used where a traditional tool produces a better result, a faster result, or an
equally good result more reliably.

Format conversion, transcoding, remuxing, container changes, and conventional compression MUST use
specialised tools (FFmpeg, codec libraries, established DSP) rather than learned models.

Choosing a learned model over a traditional implementation MUST be justified by measurement, not by
novelty.

**Rationale:** a neural network that duplicates what a mature codec already does costs orders of
magnitude more time, memory and licensing risk for no user-visible gain.

### VII. Hardware Adaptive

Processing MUST adapt automatically to the hardware actually present.

The system MUST detect: CPU, RAM, GPU, VRAM, CUDA availability, and the encoders and decoders
actually available at runtime. It MUST adapt: model choice, tile size, batch size, precision,
encoder selection, concurrency, and worker count.

Absence of a GPU MUST NOT produce an arbitrary failure. Where CPU execution is technically
possible, it MUST be used as a fallback:

```
GPU available → GPU pipeline
otherwise     → CPU fallback
```

Where an operation is genuinely infeasible on CPU, the product MUST present a clear, honest
explanation of the limitation — never a generic error.

Hardware capability MUST be detected, never assumed. Hardcoded constants that pretend to be
adaptive (a fixed tile size described as "automatic") violate this principle.

**Every media operation MUST declare its own ceilings.** Adapting to the hardware present is not
sufficient on its own: an operation that scales with input size (duration, resolution, frame
count, frame rate, file size) MUST define explicit maximum values and MUST refuse work that
exceeds them before starting it, with the limiting factor named. A refusal that arrives after
minutes of processing, or an out-of-memory crash, is a violation of this principle even on
hardware the operation was never going to fit. The existing capacity gate (`_capacity_check_for`
in `routes.py`, rejecting with `hardware_insufficient` and a `limiting_resource`) is the
established shape; new media operations extend it rather than inventing a parallel one.

**Rationale:** the same installer runs on a laptop with integrated graphics and on a workstation
with 24GB of VRAM. A single fixed configuration is wrong on both.

### VIII. Tests Required

Every migration and every new feature MUST have tests.

Existing tests from `astros_upscale` and `astros_audio_enhance` MUST be preserved or adapted — never
silently deleted.

Test integrity rules:

- Core business logic, security boundaries and processing pipelines MUST be tested against real
  behaviour. Mocking is legitimate only at genuine external boundaries (network calls, paid APIs,
  hardware not present in CI).
- A feature MUST NOT be declared validated without executing the corresponding command and
  observing the result.
- Failing tests, discovered vulnerabilities and technical limitations MUST be reported, never
  omitted.
- Slow but genuine integration tests (real subprocess, real inference) MAY be separated into an
  opt-in tier, but MUST NOT be replaced by mocks that assert nothing real.

**Rationale:** this product processes irreplaceable user files and enforces a paid licence. A test
suite that passes by mocking the thing under test provides false confidence about both.

### IX. Two-Layer Architecture

The repository MUST be organised into exactly two top-level source layers: `api/` and `interface/`.
No third layer of commands, scripts, or prompts MAY sit between them.

```
interface/  → the Electron/Vue application: screens, components, state, HTTP/WebSocket clients.
api/        → everything else that is not the visual application: the HTTP API, the licensing
              service, business logic, persistence, configuration, integrations, and the service
              logic formerly exposed only as CLI commands.
```

Mandatory rules:

- **One channel.** `interface/` MUST communicate with `api/` exclusively over HTTP/WebSocket,
  through explicit, versionable API contracts (request/response schemas). `interface/` MUST NOT
  import, `require`, or otherwise directly reference an `api/` source module, package, or internal
  file path.
- **No reverse dependency.** `api/` MUST NOT depend on, import, or read any file specific to
  `interface/` (its components, assets, build output, or configuration). `api/` MUST be runnable
  and testable with `interface/` absent.
- **No command layer between them.** A user MUST NOT need to run a terminal command to use any
  product capability. Business logic that today exists only behind a CLI entry point (argument
  parser, interactive prompt, `if __name__ == '__main__':` command dispatch) MUST be refactored so
  the underlying logic becomes a service callable from `api/`'s HTTP routes, and the command-line
  entry point that only parsed arguments and printed to a terminal MUST be removed once nothing
  depends on it. This is a **REUSE/REFACTOR** move under Principle II, not a rewrite: the logic
  itself moves, it is not reimplemented from scratch.
- **Folder separation is not process separation.** Organising the licensing service's source under
  `api/` (e.g. `api/licensing/`) is a filesystem/repository concern only. It MUST continue to run
  as its own process, on its own port, with its own secrets and its own persistence, and MUST NOT
  share a process, an in-memory secret, or a signing key with the local desktop API — this
  requirement is unchanged from how the licensing service already operates and is not relaxed by
  where its source files live.
- **Development-time build/packaging references** (Dockerfiles, PyInstaller specs, CI workflow
  paths, the Electron main process's resolution of where to launch the local API) MUST be updated
  to match the new layout as part of any change that moves files — a reorganisation MUST NOT leave
  stale paths that happen to still work by accident.

**Rationale:** this project already had three sibling backend surfaces (a root CLI package, a
local desktop API, and a separate licensing service) that grew independently, each reachable in a
different way. A user-facing command layer between the interface and the backend duplicates
validation, error handling, and licence enforcement in two places instead of one, and makes "which
layer is authoritative" ambiguous — the same failure mode Principle I exists to prevent, applied to
runtime architecture instead of specifications.

### X. Interface Structure Is Adapted, Not Templated

Generic architectural templates (Atomic Design, Clean Architecture, layered folder conventions)
inform how `interface/` is organised, but MUST be adapted to what this specific application
actually is — a thin Electron/Vue presentation client — never applied literally when a literal
application would create structure with no real purpose.

- **No empty domain/application layers.** Because Principle IX already requires every piece of
  business logic to live in `api/`, `interface/` MUST NOT contain `domain/`, `application/`, or
  `use-cases/` directories. A layer that would hold nothing (or near-nothing) because the logic it
  is supposed to contain lives elsewhere is not architecture, it is decoration. This rule is not
  relaxed by anything below.
- **Component organisation follows reuse, confirmed by audit, not a fixed taxonomy.**
  `interface/` is not obligated to use the full Atomic Design five-tier split
  (atoms/molecules/organisms/templates/pages), and MUST NOT adopt it as a taxonomy exercise on a
  component count too small to need it. Once a concrete audit of the actual components and views
  confirms real, repeated duplication (the same button/card/form-field/modal pattern reimplemented
  independently across multiple files), some or all Atomic Design tiers MAY be adopted as the
  organising structure for `components/` — adopted only for the tiers that duplication actually
  justifies, not applied uniformly out of consistency for its own sake. A tier with one or two
  members that could as easily sit in a flatter structure is not justified by this clause.
- **A Tailwind-based design system MAY replace hand-written CSS, without becoming a redesign.**
  The current hand-written stylesheets (`base.css`, `main.css`, `theme.css`) MAY be replaced by
  Tailwind CSS utilities plus a small set of semantic design tokens (colour, spacing, typography,
  radius, shadow — expressed as Tailwind theme extensions, not scattered literals), when doing so
  measurably removes real, repeated duplication across component styles. The migration MUST
  preserve existing visual behaviour — colours, spacing, typography, layout, hierarchy — as it
  stands today; a visual change is permitted only where it fixes a confirmed inconsistency between
  screens, never as an unrequested redesign riding along with the structural change. Hand-written
  CSS MAY remain where Tailwind genuinely cannot express the need (Electron-specific integration,
  custom scrollbars, complex pseudo-elements, third-party library overrides, non-trivial
  animation) — it MUST NOT remain merely out of convenience once an equivalent utility exists.
- **External-access code is isolated and named for what it does.** The boundary code that talks
  to something outside the renderer process (the Electron `contextBridge` bridge, the HTTP/WebSocket
  client that talks to `api/astros_upscale_api`) MUST be kept out of components and views — no
  component or view may call `fetch`/IPC directly — and MUST be named so its purpose is obvious
  from the name alone. It MUST NOT be dressed up as a `repository`/`port`/`adapter` abstraction
  when there is, and will only ever be, one real implementation. Where the volume of HTTP
  endpoints or Electron-bridge calls genuinely justifies splitting today's single `apiClient.ts`/
  `nativeBridge.ts` into a `services/` layer (e.g. `services/api/`, `services/native/`), the same
  naming-for-what-it-does rule applies to each resulting file; a `services/websocket/` (or any
  other) split MUST NOT be created as an empty or near-empty scaffold when the application has no
  corresponding real traffic to centralise there.
- **No abstraction without a real consumer.** Interfaces or contracts for a single implementation,
  wrapper functions that only forward a call, `index.ts` files that exist only to re-export, and
  splitting a file for line-count reasons alone (with no distinct responsibility behind the split)
  are all prohibited — this applies identically to Atomic Design tiers, design tokens, and the
  `services/` split described above: each one MUST be justified by a real, cited duplication or
  responsibility, not created to satisfy the shape of a template. A file MUST be split only when
  it has genuinely separable responsibilities, is reused from more than one place, or splitting it
  measurably improves testability or maintainability — never on size alone.
- **Dead code is deleted, not archived.** Files or folders named/suffixed `old`, `legacy`,
  `deprecated`, `backup`, `copy`, `temp`, `v1`, `previous` (or equivalent) MUST NOT exist in
  `interface/`. If the current flow does not use it, it is removed — "keeping it just in case" is
  not a valid reason to keep unreferenced code in a version-controlled repository. This rule is
  not relaxed by anything above: once a component, style, or module is superseded by its Atomic
  Design/Tailwind/`services/` equivalent, the superseded version MUST be deleted in the same body
  of work, not kept alongside it "for comparison."

**Rationale:** this project already carries the scar tissue of applying structure for its own
sake — three independently-grown backend surfaces before Principle IX consolidated them. Importing
a generic "medium/large web project" template wholesale into a small, thin Electron renderer would
reproduce that exact mistake on the frontend: folders that exist to satisfy a pattern instead of a
real need, adding indirection a ~20-component app never asked for. Principle II (Reuse First) and
this principle share the same instinct — prefer what the codebase already needs over what a
template says it should have. `interface/` has since grown to roughly 19 components and 10 views
with confirmed repeated UI patterns (buttons, cards, form fields, modals reimplemented
independently) and CSS that a README already claimed was Tailwind-based but wasn't — the same
instinct that kept this principle's original judgment conditional ("too small to need it") is what
now permits Atomic Design tiers, Tailwind design tokens, and a `services/` split once an audit
confirms the condition that was previously absent is now present. The bar does not move: structure
is still earned by demonstrated duplication, never assumed from a template's shape.

**A component MUST NOT grow past the point where its own parts stop being reusable.** A view or
component that contains several independently meaningful controls — each with its own state,
event handling, and visual contract — MUST decompose them into child components or composables
once any one of them is needed in a second place, or once the file can no longer be read as one
responsibility. This is the same "earned by demonstrated duplication" bar the rest of this
principle uses, applied inside a file instead of across the folder tree: a large file is not a
violation on its own, and MUST NOT be split to hit a line count.

This rule governs new code and any file being substantially reworked. It is **not** retroactive:
`ImageEditorView.vue` (~1800 lines) is not made non-compliant by this amendment, and MUST NOT be
split as an isolated refactor. It becomes subject to the rule when a change would add another
independently meaningful control to it, at which point the new control — and whatever it shares
with an existing one — is extracted rather than appended.

### XI. API Structure Is Consolidated By Domain, Not By Class

Generic layered conventions (one file per class, one directory per technical tier — `api/`,
`core/`, `models/`) inform how `api/`'s subpackages are organised, but MUST be adapted to what
each subpackage's actual responsibility surface looks like — never applied literally when the
result is fragmentation with no real navigational benefit.

- **Consolidate by domain, not by class or by technical layer.** Inside `astros_upscale_api/app/`,
  the `app/api/`, `app/core/`, and `app/models/` directory split MUST NOT be kept as a rule of its
  own; route handlers for different resources belong together in `routes.py`, model
  upscale/video/audio/component/capacity orchestration belongs together in `processing.py`, job
  scheduling/worker supervision/subprocess isolation belongs together in `jobs.py`, the licence
  gate/cache/registry/profile-resolution/offline-tolerance chain belongs together in
  `licensing.py`, the isolation/integrity/DPAPI/protected-loader/identity stack belongs together in
  `security.py`, and request/response schemas belong together in a single `schemas.py`. The same
  domain-grouping applies to `astros_licensing_service/app/`: activation, authorisation and service
  identity into `licensing.py`; package definitions and their cryptography into `packages.py`; the
  Stripe/Mercado Pago/base provider files into one `payments.py`; the four route files into one
  `routes.py`.
- **Genuine technical separation still stands.** If a piece of a consolidation target has a
  separable, independently-testable responsibility, or merging it would produce a file that no
  longer reads as one coherent domain, that piece MAY remain — or become — its own file. This
  principle does not mandate merging past the point where the result stops being readable; a
  smaller number of files is a consequence of removing accidental fragmentation, not a target
  pursued for its own sake.
- **The test for a new file is a consumer, not a category.** A new module inside a domain package
  is justified when at least one of these is true, and the justification MUST be stated in the
  plan that introduces it: (a) it has tests that exercise it directly, without going through its
  sibling modules; (b) a module outside its own domain imports it; (c) it isolates a third-party
  dependency, subprocess, or external contract that the rest of the domain MUST NOT reach past.
  A module that satisfies none of these belongs inside the domain file it serves, however large
  that domain is. Naming a file after a technical tier — `validation.py`, `models.py`,
  `controllers.py`, `types.py`, `utils.py` — is by itself never a justification, because it names
  a category rather than a consumer; the same code named after what it actually owns
  (`video_effects.py`, `video_thumbnails.py`) may well qualify under (a), (b) or (c).
- **No behaviour change from consolidation.** HTTP paths, methods, request/response schemas, status
  codes, WebSocket message contracts, and the processing/licensing/payment logic itself MUST be
  preserved exactly. Moving code between files is a file-organisation change, not a redesign, and
  MUST NOT alter what any consumer (the `interface/` app, a test, an external client) observes.
- **No abstraction added to make the merge easier.** Consolidating files MUST NOT introduce a new
  facade, base class, or indirection layer whose only purpose is to paper over the merge — call
  sites are updated to the new module path directly, per Principle X's existing "no abstraction
  without a real consumer" rule, which applies here identically.
- **Dead structure is removed, not left behind.** `app/api/`, `app/core/`, `app/models/`, and any
  other pre-consolidation directory MUST be deleted once empty — not left as an empty shell "in
  case something still imports it." Existing compatibility shims (e.g. `legacy_identifiers.py`)
  MUST NOT be deleted without first confirming nothing external — persisted data, another service,
  an already-shipped client — still depends on them; where still needed, their logic is folded into
  the module it now conceptually belongs to, not kept as a standalone pass-through file.

**Rationale:** this project already carries the scar tissue of applying structure for its own
sake twice — three independently-grown backend surfaces before Principle IX consolidated them,
and a generic frontend template that Principle X declined to apply literally. `api/`'s internal
layout grew the same way: one class per file inside `app/core/` and `app/api/`, and a matching
`app/models/` for schemas, none of which reflects a real boundary a consumer of the code needs.
The same instinct that kept `interface/` small and reuse-driven under Principle X applies to the
API's internal module layout — prefer what the codebase's actual responsibility surface needs
over what a generic layered-architecture habit says it should have.

### XII. AI Audio Restoration Is Bounded, Provider-Isolated, and Never Auto-Trusted

Generative/learned models MAY be used for music restoration and mastering, but only as a bounded,
optional stage inside a deterministic DSP pipeline that owns the final result — never as a
replacement for that pipeline, and never reachable directly by the rest of the application.

- **Deterministic DSP is never replaced by AI.** Loudness measurement (LUFS, True Peak, RMS), peak
  detection, DC offset correction, high-pass/notch/parametric/dynamic EQ, compression and
  multiband compression, limiting, gain staging, stereo and phase analysis, normalisation and
  dithering MUST remain traditional, deterministic DSP, independent of any AI provider. A learned
  restoration model MAY be invoked only when a problem-detection stage identifies a class of
  degradation traditional DSP does not adequately address (e.g. excessive reverb, severe clipping,
  complex distortion, complex tonal imbalance, general restoration of a poor-quality recording) —
  audio MUST NOT be sent to an AI provider by default or unconditionally; doing so is exactly the
  hardware-cost/time-cost violation Principle VI (No AI Without Benefit) already forbids, applied
  to the audio-mastering pipeline specifically.
- **An AI provider's output is never the final master.** It MUST always pass back through this
  project's own corrective DSP and a Quality Guard stage before becoming output. The Quality Guard
  MUST compare objective before/after metrics (LUFS, Peak, True Peak, dynamic range, stereo
  correlation, spectral balance, clipping, phase, distortion indicators) and MUST reject or reduce
  the AI-provided processing when it introduces a measurable technical regression. An AI
  restoration stage that cannot be independently verified is not permitted to ship as-is.
- **AI restoration models are reachable only through an isolated provider interface.** The rest of
  the application MUST depend on an abstract provider contract (e.g. `AudioRestorationProvider`)
  and MUST NOT import or call a specific model's library directly from mastering/orchestration
  code. Each model gets one concrete adapter (e.g. `SonicMasterProvider`) implementing that
  contract; swapping or adding a model MUST NOT require changes to the orchestration engine that
  calls it. Third-party model code (e.g. a cloned inference repository) MUST be kept isolated
  behind its adapter — prefer a thin adapter over forking or modifying third-party source, and
  reuse only what the adapter needs (inference path), not that project's training pipeline.
- **Lazy loading and fallback are mandatory for every AI audio provider.** A model MUST NOT be
  loaded at application startup; it loads only when an operation that actually needs it is
  requested, and remains loaded for reuse across subsequent operations in the same session. When a
  provider is unavailable for any reason (failed load, insufficient GPU/VRAM, missing runtime
  dependency), the system MUST fall back to DSP-only restoration automatically — the absence or
  failure of an AI provider MUST NOT make the product unusable, consistent with Principle VII
  (Hardware Adaptive)'s existing "no arbitrary failure" rule extended to this pipeline.
- **Heavy AI inference runs isolated from the main API process,** consistent with the process
  isolation architecture already established for model inference (`docs/processing-protection-architecture.md`
  Fase 1, and the isolated worker in `api/astros_upscale_api/app/jobs.py`). A crash or resource
  exhaustion inside audio-restoration inference MUST NOT take down the primary API process.
- **Heavy ML dependencies of an audio-restoration provider MUST be isolated from the main backend
  environment** — installed into a separate environment/extra, not pulled automatically into
  `astros_upscale_api`'s primary requirements — consistent with the project's existing preference
  for a lean primary backend dependency set (see `api/README.md`).
- **Restoration MUST preserve the original musical intent.** AI-assisted restoration MUST NOT
  unnecessarily alter timbre, instrumentation, vocal characteristics, stereo placement, transients,
  or the recording's artistic ambience. Restoration is not remixing; this is an acceptance
  criterion for any AI audio feature, not merely product guidance, and MUST be checked as part of
  that feature's validation.
- **Licensing rigor for audio AI dependencies is identical to Principle IV, with explicit tracking
  of conditional licences.** A model, weight, or supporting component (including a required
  encoder/decoder such as a third-party VAE) used for AI audio restoration MUST clear the same
  Commercial License Only verification Principle IV already requires. Where a dependency's licence
  is conditional rather than unconditionally permissive (e.g. free only below a stated revenue
  threshold), that condition MUST be recorded explicitly in `docs/models/MODEL_LICENSES.md` as an
  accepted, monitored risk — never silently treated as equivalent to an unconditional permissive
  licence.

**Rationale:** the technical audit performed before this principle was written found a concrete
case this principle exists to prevent: a capable, Apache-2.0-licensed restoration model
(SonicMaster) whose only path to production use requires a VAE distributed under a licence that
is free only below a revenue threshold, and whose reference inference code is a research
repository, not an installable package, wired directly into whatever calls it. Without a provider
boundary, that specific model's shape (its checkpoint format, its chunking strategy, its
dependency pins) would leak into the mastering pipeline itself, exactly the coupling Principle II
(Reuse First) and Principle X/XI's "adapted, not templated" instinct already reject elsewhere in
this codebase. Music restoration also carries a failure mode none of the existing principles name
directly: a generative model can produce audio that measures worse than the input it "restored,"
or that no longer sounds like the same recording — Principle VIII (Tests Required) requires tests
to exist, but does not by itself require the specific before/after technical comparison an AI
mastering stage needs to avoid silently shipping a regression.

### XIII. External Processes Are Invoked Structurally, Never Composed

Any invocation of an external binary — FFmpeg, FFprobe, a Python worker, any other subprocess —
MUST be built from structured arguments, never by composing a string.

Mandatory rules:

- **No shell, no concatenation.** Subprocesses MUST be launched with an argument list and
  `shell=False`. A value that originated outside the process — an HTTP request body, a filename, a
  configuration file — MUST NOT be concatenated, interpolated, or formatted into a command line,
  a filter graph string, or any other text that a binary will parse as instructions. Where a
  library exists that builds the invocation structurally (`ffmpeg-python`, already used by
  `run_ffmpeg` in `astros_upscale/media.py`), it MUST be used rather than hand-assembling
  equivalent text.
- **Closed vocabularies, validated server-side.** Every client-supplied value that selects
  behaviour rather than magnitude — container, codec, encoder preset, pixel format, filter name,
  aspect ratio — MUST be validated against an explicit allowlist in `api/` before use. Numeric
  values MUST be range-checked. Validation performed in `interface/` is a usability affordance and
  MUST NOT be the only place it happens; the API MUST behave correctly when called directly.
- **Availability is verified, not assumed.** An allowlist entry means "permitted", not "present".
  Before starting work that depends on a codec, encoder, or container, the API MUST confirm the
  runtime actually provides it and MUST fail with a clear reason if it does not — never begin
  processing that will die partway through.
- **Files are addressed by internal identifier.** A client MUST NOT supply a filesystem path that
  the API then reads or writes. Clients reference media by an identifier the API issued; the API
  resolves that identifier to a path it owns. Filenames arriving from a client are treated as
  display text and MUST be sanitised before being used to construct any path.

  **Bounded exception — registration by the desktop shell.** Exactly one route MAY accept a
  filesystem path: the one whose only purpose is to register a file and return the identifier every
  other route then uses. That exception is conditional on all of the following, and is void if any
  fails:

  - The path MUST originate from the operating system's own file dialog, invoked by the Electron
    main process. A path typed, pasted, or otherwise composed by the renderer, or arriving from any
    source outside that dialog, MUST NOT be accepted.
  - The registration route MUST validate the path before anything else — that it exists, that it is
    a file, that it is media the product can read — and MUST NOT return the path in any response.
  - No other route MAY accept a path. Where a second one appears to need it, the answer is another
    identifier, not a second exception.
  - The identifier MUST NOT be a reversible encoding of the path.

  **Rationale for the exception:** the product is a desktop application whose entire purpose is
  operating on files the person already has. Something has to name the first file, and on a desktop
  that something is the native dialog. Forbidding it outright does not remove the path from the
  system — it pushes it into an undocumented side channel, which is worse than one audited route.
  The risk Principle XIII actually targets is a path chosen by untrusted input reaching a command
  builder; requiring the path to come from the OS dialog and stopping at one route addresses that
  risk directly, while every subsequent operation still speaks only in identifiers.
- **Temporary artefacts are cleaned up on every exit path.** Intermediate files created during
  processing MUST be removed on success, on failure, and on cancellation alike.

**Rationale:** this codebase already does all of the above, and none of it is written down —
`run_ffmpeg` builds graphs structurally, `WorkerSupervisor` spawns with `shell=False` and a
`_restricted_env` allowlist, and the local API resolves job outputs to paths it chose. That makes
the safety a property of who wrote each call site rather than a property of the project. A media
editing surface multiplies the number of client-controlled values that reach a command builder
from a handful to dozens; the practice has to be a rule before that happens, not after.

### XIV. Interface Text Is Translatable By Default

Text that a person reads in `interface/` MUST live in the locale files, not in a component.

- **New user-facing strings MUST be added as i18n keys** and rendered through the translation
  layer. This covers labels, descriptions, hints, placeholders, empty states, button text, status
  vocabulary, and error messages shown to a person. It does not cover code comments, log output,
  test fixtures, or developer-facing diagnostics.
- **A string added in one locale MUST be added in all of them.** A key that exists only in
  `pt-BR.json` is worse than an untranslated literal, because it fails at runtime for every other
  locale instead of degrading visibly during development.
- **This rule is not retroactive.** The roughly 32 Portuguese literals currently sitting in
  templates (only `AppSidebar`, `HomeView` and `SettingsView` use `useI18n` today) do not become
  non-compliant by this amendment. They MUST be extracted when the component containing them is
  substantially reworked, and MUST NOT be extracted as an isolated sweep that touches every view at
  once for no functional reason.

**Rationale:** the project ships 11 locale files and 42 keys. Every screen built since then has put
its text directly in the template, so the translation surface has been shrinking relative to the
application for as long as the application has been growing. The cost of that is asymmetric:
writing a key costs seconds while the component is being written, and extracting one later costs a
pass over every locale plus a re-read of code nobody is otherwise touching.

### XV. Source Media Is Never Overwritten

An operation on a media file MUST produce a new file. The input MUST still exist, byte-identical,
when the operation finishes.

- **Output never lands on the input.** Where a result would collide with an existing file, the
  default MUST be to write alongside it under a distinct name. Overwriting MUST require an
  explicit, per-operation instruction from the person — never a default, never a fallback when a
  destination is ambiguous.
- **Previews are disposable and separate.** A preview — reduced resolution, a fragment, a lower
  bitrate, a generated thumbnail — MUST be written to storage the API owns, MUST NOT be presented
  as the result of the operation, and MUST NOT replace either the source or a previously produced
  output.
- **Derived artefacts are invalidated, not trusted.** Caches keyed to a source file (thumbnails,
  timeline sprites, cached masters) MUST be invalidated when that file changes. A cache key MUST
  include something that changes with the file's content, not its path alone.

**Rationale:** the existing image pipeline already behaves this way — a lossless master is cached
separately and re-encoded on export, and a name collision renames rather than overwrites. Editing
introduces the first operations whose whole purpose is to alter how a file looks, which is exactly
when "the output is the input" starts to feel natural to implement and starts destroying people's
originals when it is wrong.

## Licensing and Distribution Constraints

These constraints follow from Principle IV and from the product being closed-source and commercial.
They are recorded separately because they constrain packaging and build configuration, not
feature design.

**FFmpeg MUST be built and distributed under LGPL.** Builds configured with `--enable-gpl` place
the entire application under GPL v2+, which is incompatible with a closed-source commercial
product. Builds configured with `--enable-nonfree` are not legally redistributable at all.

LGPL compliance requires all of: dynamic linking (separate shared libraries, not statically
embedded), distribution of the corresponding FFmpeg source, the user's ability to replace those
libraries, and visible attribution.

**GPL encoders MUST NOT be bundled.** `libx264` and `libx265` are GPL. H.264 and H.265 output MUST
therefore come from hardware encoders (NVENC, QSV, AMF) or from a commercially licensed encoder —
never from a GPL software encoder in the shipped build.

Patent licensing for codecs is a separate legal question from encoder software licensing, and MUST
NOT be assumed to be resolved by choosing a permissively licensed encoder.

**License authority lives in the backend.** The component that resolves which model to run MUST be
the component that enforces whether that model may be used. Licence metadata MUST NOT live only in
the frontend.

## Development Workflow

The mandatory sequence for any significant body of work:

```
Constitution → Specify → Clarify → Plan → Tasks → Analyze → Implement → Validate
```

Rules that govern the sequence:

- `Analyze` MUST run before `Implement`. Implementation MUST NOT begin while a critical violation
  of any principle remains unresolved.
- Implementation MUST be incremental. Each phase follows: **implement → test → validate → benchmark
  (where applicable) → proceed**. A single large rewrite is not permitted.
- Scope MUST NOT be reduced silently. Where a requirement is not applicable to the technology in
  use, the reason MUST be recorded explicitly and an equivalent alternative implemented.
- Benchmarks MUST precede the final choice of what backs each of the three profiles. Models MUST
  NOT be selected by reputation, popularity, or parameter count.
- Licence verification MUST precede benchmarking. Measuring a model that cannot be distributed is
  wasted effort.

A feature is NOT complete because it compiles. Completion requires that it runs, that its tests
pass, that its benchmarks are documented where applicable, and that spec, plan, tasks and
implementation agree.

## Governance

This constitution supersedes other development practices within the Astros project. Where a
convention, habit, or prior decision conflicts with a principle here, the principle prevails.

**Amendment procedure.** Amendments MUST be recorded in this file, MUST state the rationale, and
MUST include a migration note where existing code becomes non-compliant. An amendment that
weakens a principle MUST state explicitly what risk is being accepted and by whom.

**Versioning policy.** This document is versioned semantically:

- **MAJOR** — a principle is removed, or redefined in a way that permits what it previously forbade.
- **MINOR** — a principle or section is added, or guidance is materially expanded.
- **PATCH** — clarification, wording, or correction that does not change meaning.

**Compliance review.** Every plan produced by `/speckit.plan` MUST be checkable against these
principles, and `/speckit.analyze` MUST verify compliance before implementation is authorised.
Principles IV (Commercial License Only), III (Performance First), II (Reuse First),
V (Models Are Internal), VIII (Tests Required), IX (Two-Layer Architecture),
X (Interface Structure Is Adapted, Not Templated), XI (API Structure Is Consolidated By Domain,
Not By Class), XII (AI Audio Restoration Is Bounded, Provider-Isolated, and Never Auto-Trusted),
XIII (External Processes Are Invoked Structurally, Never Composed), XIV (Interface Text Is
Translatable By Default) and XV (Source Media Is Never Overwritten) are the mandatory review
gates.

Complexity MUST be justified. A simpler implementation that satisfies the specification is
preferred to a more capable one that exceeds it.

### Amendment log

**v4.0.0 — 2026-08-21 — Principle V: bounded exception for user-controlled encoding parameters**

*What changed:* Principle V's technical-disclosure exception required the disclosed view to be
"informational only" and forbade "any choice that changes processing results". A second bounded
exception now permits exactly such choices — codec, container, CRF/CQ, bitrate, encoder, encoding
preset, pixel format, sample rate, channels — in the Compression Centre's Advanced mode, under
five cumulative conditions.

*Why:* compression is the one place where the product does not know better. A person targeting an
8 MB upload limit, a device's codec support, or an archival master holds a constraint the backend
cannot infer, and refusing them CRF withholds the only control that answers it. The principle's
stated harm — forcing an engineering decision onto someone who cannot evaluate it — is prevented
by conditions 2 and 4 instead: Basic mode never shows a codec name, and every technical control
has a working "Automático" that Basic mode itself uses.

*Risk accepted, by whom:* the product owner (Eric Inácio) accepts that the API surface grows and
that part of it becomes coupled to codec vocabulary that may later have to change. Conditions 1
and 3 bound it — the AI path, where implementation churn is highest, is explicitly excluded, and
no option may be offered that a functional probe does not confirm.

*Migration note:* no existing code becomes non-compliant. The exception is additive and scoped to
a feature that does not yet exist. `test_no_codec_leak.py` continues to hold unchanged for the
video-editor routes it covers; those routes are not the Compression Centre.

*What did NOT change:* the AI path. Upscale and audio restoration remain under the unmodified
rule — intent in, backend resolves. The Licensing and Distribution Constraints are explicitly
not subject to this exception: no GPL encoder becomes available because someone asked for it.

**v3.0.0 — 2026-08-14 — Principle XIII: bounded exception for file registration by the desktop shell**

*What changed:* Principle XIII's "Files are addressed by internal identifier" clause previously
forbade, without exception, a client supplying a filesystem path that the API reads or writes. It
now permits exactly one route to do so — the route whose sole purpose is to register a file and
return the identifier every other route uses — under four cumulative conditions: the path comes
from the operating system's own file dialog invoked by the Electron main process; the route
validates before doing anything else and never returns the path; no second route may accept a path;
and the identifier is not a reversible encoding of the path.

Also corrected, without normative effect: Principle XIV's rationale and the v2.6.0 amendment log
said the project ships **12** locale files. It ships **11** (`interface/src/renderer/src/i18n/locales/`,
and `SUPPORTED_LOCALES` in `i18n/index.ts`). Both occurrences fixed.

*Why:* `/speckit.analyze` on feature `007-video-editor-player` found the contradiction. That
feature builds the identifier registry Principle XIII asks for, and the registry's own entry point
violated the principle it exists to satisfy: something has to name the first file, and on a desktop
product that something is the native file dialog. The options were to forbid it (which does not
remove the path from the system — it pushes it into an undocumented side channel), to leave the
violation standing, or to name the exception and fence it. The risk the principle actually targets
is a path chosen by untrusted input reaching a command builder. Requiring the path to originate
from the OS dialog and confining it to one audited route addresses that risk directly, while every
subsequent operation still speaks only in identifiers.

*Migration:* no existing compliant code becomes non-compliant. `POST /jobs/local`, which accepts a
local path today, is **not** blessed by this exception — it is not a registration route and it does
not return an identifier. It remains outside the exception and should migrate to identifiers in
work of its own; this amendment does not authorise a second path-accepting route.

*Risk accepted:* one route reads a filesystem path supplied over HTTP. The exposure is bounded by
the four conditions, and by the fact that the local API binds to loopback. What is explicitly not
accepted: a renderer-composed path, a path echoed back in a response, a second exception, or an
identifier from which the path can be recovered. Accepted on the reasoning above by the project
owner, at the recommendation of the analysis that found the conflict.

**v2.6.0 — 2026-08-14 — Principles XIII, XIV and XV added; VII, X and XI extended**

*What changed:* added three principles and tightened three existing ones, all driven by the video
media-editing feature spec that follows this amendment.

- **XIII (External Processes Are Invoked Structurally, Never Composed)** — codifies what the
  codebase already does (`run_ffmpeg` building graphs via `ffmpeg-python`, `WorkerSupervisor`
  spawning with `shell=False` and a `_restricted_env` allowlist, job outputs resolved to
  API-owned paths) as a rule rather than a habit, and adds the parts that had no precedent:
  server-side allowlists for every client-supplied codec/container/preset, runtime verification
  that an allowed codec is actually present before work starts, addressing files by
  API-issued identifier rather than client-supplied path, and cleanup of temporary artefacts on
  every exit path.
- **XIV (Interface Text Is Translatable By Default)** — new. The project ships 11 locale files
  with 42 keys, while only three components use `useI18n` and roughly 32 user-facing strings sit
  directly in templates. Without a rule, a feature of this size decides the question by omission.
- **XV (Source Media Is Never Overwritten)** — new. Generalises the image pipeline's existing
  behaviour (cached lossless master, rename-on-collision) to a rule covering previews, derived
  artefacts, and cache invalidation keyed to file content.
- **VII extended** — hardware adaptation alone does not bound an operation. Every media operation
  must now declare explicit ceilings (duration, resolution, frame rate, frame count, file size)
  and refuse work that exceeds them before starting, naming the limiting factor.
- **X extended** — adds a decomposition rule for components whose parts stop being reusable, using
  the same "earned by demonstrated duplication" bar the principle already applies to folders.
- **XI extended** — replaces the judgment call about when a new module is justified with three
  testable conditions (directly tested / imported across domains / isolates an external contract),
  and states that naming a file after a technical tier is never a justification by itself.

*Rationale:* the incoming feature adds a subsystem large enough to break each of these open. It
introduces dozens of client-controlled values that reach an FFmpeg command builder (XIII), a
frontend surface explicitly specified as ~11 components and 6 composables against a codebase whose
largest view is ~1800 lines (X), a backend surface that legitimately needs several modules inside
one domain where Principle XI previously offered only "does it read as coherent" (XI), operations
whose cost scales with duration and resolution rather than with a fixed model pass (VII), dozens
of new labels in a project whose translation coverage has been shrinking (XIV), and the first
operations whose purpose is to alter how a file looks (XV).

*Migration:* no existing code becomes non-compliant. XIV and X's decomposition rule are explicitly
non-retroactive and name the existing code they exempt (`ImageEditorView.vue`, the ~32 template
literals), including a prohibition on sweeping refactors undertaken solely to comply. XIII
describes existing practice at every current call site; VII's ceilings extend the capacity gate
already in `routes.py` rather than replacing it.

*Risk accepted:* none — every change adds constraints. XI's new criterion narrows when a new file
is permitted rather than widening it, and X's decomposition rule cannot be used to justify
splitting a file that has no second consumer.

**v2.5.0 — 2026-08-13 — Principle XII added: AI Audio Restoration Is Bounded, Provider-Isolated,
and Never Auto-Trusted**

*What changed:* added a new principle governing how any AI/generative model MAY be used for music
restoration and mastering: deterministic DSP (loudness/EQ/dynamics/stereo/limiting/normalisation/
dithering) is never replaced by AI, only supplemented when a problem-detection stage finds a
degradation class traditional DSP does not adequately address; an AI provider's output is never
the final master — it always passes back through this project's own corrective DSP and a Quality
Guard stage that compares objective before/after metrics (LUFS, Peak, True Peak, dynamic range,
stereo correlation, spectral balance, clipping, phase, distortion indicators) and can reject or
reduce AI processing that regresses them; AI models are reachable only through an isolated
provider adapter (e.g. `AudioRestorationProvider` / `SonicMasterProvider`), never called directly
by orchestration code, with third-party inference repositories kept isolated behind their adapter
rather than forked or modified in place; lazy loading and automatic DSP-only fallback are
mandatory for every AI audio provider; heavy AI inference runs isolated from the main API process,
consistent with the isolated-worker architecture already established for model inference; heavy ML
dependencies of an audio provider are kept out of the main backend's primary dependency set;
restoration MUST preserve the original musical intent (timbre, instrumentation, vocals, stereo
placement, transients, artistic ambience) as an acceptance criterion, not just guidance; and
licensing rigor for audio AI dependencies is identical to Principle IV, with conditional licences
(e.g. free only below a stated revenue threshold) explicitly recorded as an accepted, monitored
risk in `docs/models/MODEL_LICENSES.md`, never silently treated as unconditionally permissive.
Added Principle XII to the mandatory `/speckit.analyze` compliance review gates in Governance.

*Why:* a technical audit of a candidate restoration model (SonicMaster, Apache-2.0 code/weights)
performed immediately before this amendment found the exact case this principle exists to head
off: a capable model whose only path to production requires a third-party VAE licensed free only
below a revenue threshold, and whose reference inference code is a research repository (no
`setup.py`/`pyproject.toml`, hardcoded absolute paths in its batch-inference scripts) — the kind of
dependency that, without an explicit boundary, tends to get wired directly into orchestration code
rather than isolated behind an adapter. That coupling is the same "structure for its own sake, or
no structure at all" failure mode Principles IX/X/XI already corrected elsewhere in this codebase
(three independently-grown backend surfaces, a literal frontend template, file-per-class API
fragmentation) — this is that same instinct applied to how a new, still-experimental class of
dependency (a generative audio model) is allowed to enter the product at all. Music restoration
also introduces a failure mode none of the existing principles name directly: a generative model
can produce audio that measures worse than its input, or that no longer sounds like the same
recording. Principle VIII (Tests Required) requires tests to exist, but not the specific
before/after objective-metric comparison an AI mastering stage needs to avoid silently shipping a
regression — this principle's Quality Guard requirement closes that gap. Principle VI (No AI
Without Benefit) already forbids using AI where traditional tooling does as well or better; this
principle makes that concrete for the mastering pipeline specifically, by naming which operations
stay deterministic DSP unconditionally.

*Migration:* no existing code becomes non-compliant — the project has no AI audio restoration
pipeline yet. This principle governs the design produced by the feature spec that follows it
(`/speckit.specify` → `/speckit.plan` for the `audio-engine` module); it does not itself create,
move, or delete any files.

*Risk accepted:* none beyond what is explicitly named inside the principle itself — the Stable
Audio Open VAE's revenue-threshold licence condition, which this amendment requires to be tracked
in `docs/models/MODEL_LICENSES.md` as an accepted, monitored risk rather than resolved by this
constitutional change.

**v2.4.0 — 2026-08-12 — Principle X expanded: Atomic Design, Tailwind design tokens and a
`services/` split MAY be adopted once duplication is confirmed**

*What changed:* Principle X's "component organisation follows reuse, not a fixed taxonomy" clause
now explicitly permits adopting Atomic Design tiers (atoms/molecules/organisms/templates/pages —
whichever tiers duplication actually justifies, not necessarily all five) once a concrete audit
confirms real, repeated UI duplication. A new clause permits replacing the hand-written stylesheets
(`base.css`, `main.css`, `theme.css`) with Tailwind CSS plus a small set of semantic design tokens
under the same "confirmed duplication, not a template" test, with a hard requirement to preserve
existing visual behaviour — this is a refactor, not a redesign, unless a change fixes a confirmed
cross-screen inconsistency. The "external-access code is isolated and named for what it does"
clause is extended to cover a possible split of today's single `apiClient.ts`/`nativeBridge.ts`
into a `services/api/`, `services/websocket/`, `services/native/` layer, with the constraint that a
sub-folder MUST NOT exist as an empty scaffold for traffic the application doesn't actually have
(e.g. no `services/websocket/` unless the app genuinely uses a WebSocket). The existing "no empty
domain/application layers", "no abstraction without a real consumer", and "dead code deleted, not
archived" rules are restated as applying identically to all of the above — explicitly not relaxed.

*Why:* a full interface/ refactor was requested (Atomic Design, an internal design system,
complete Tailwind migration, an explicit services/ layer) that sits in real tension with this
principle's original, more skeptical wording ("not obligated to use the full ... split", "MUST NOT
be imposed ... on a component count too small to need it"). The request itself already agrees with
Principle X's underlying instinct — it explicitly frames the target structure as "uma referência
arquitetural, não uma obrigação literal", asks for pragmatic tier adoption rather than a checklist,
and forbids empty directories/files, unused abstractions, and unnecessary `index.ts` files. So this
amendment is not a reversal of Principle X's philosophy; it is that same philosophy applied to a
scale trigger the original wording reserved judgment on. `interface/` has grown to roughly 19
components and 10 views, with an audit-confirmable amount of repeated button/card/form-field/modal
UI, and its README already (inaccurately) claimed Tailwind was already in use — the condition
Principle X's "too small to need it" language was waiting for is now plausibly met, but the
principle still requires that condition to be *confirmed by audit*, not assumed from the shape of
a template, before any tier, token, or services/ sub-folder is created.

*Migration:* no existing compliant code becomes non-compliant by this amendment alone. It
authorises — but does not itself perform — the reorganisation carried out under the feature spec
that follows it. The duplication audit required by this amendment is part of that feature's
`/speckit.plan`/`/speckit.tasks` work, not of this constitutional change.

*Risk accepted:* none beyond what Principle X already accepted when first ratified — this
amendment only makes explicit, conditional permission for structure the codebase did not
previously have codified; it does not permit skipping the audit, and it does not permit anything
that contradicts the "adapted, not templated" instinct the rest of the principle still enforces.

**v2.0.0 — 2026-08-08 — Principle V bounded exception for technical disclosure**

*What changed:* Principle V previously forbade exposing model names anywhere, unconditionally. It
now forbids exposing them on default surfaces and forbids model selection, while permitting an
opt-in, informational technical details view inside the components/updates screen.

*Why:* two reasons, one of them a defect.

1. The product requires a components/updates screen (decision of 2026-08-08), and the owner
   chose to allow an optional technical detail view within it.
2. **The original wording contradicted Principle IV.** Principle IV requires licence attribution
   to be visible in the shipped product. Approved components carry CC-BY-4.0 and Apache-2.0
   NOTICE obligations. Attribution is impossible without naming what is being attributed. As
   written, v1.0.0 made compliance with IV and V mutually exclusive. This amendment resolves that.

*Migration:* no existing compliant code becomes non-compliant. The removal of model-selection UI
required by v1.0.0 still stands — only the informational disclosure is newly permitted.

*Risk accepted:* a user who opens the details panel learns which model backs a profile. Judged
acceptable because the view offers no choice, so it cannot shift an engineering decision onto the
user, and the product remains free to change implementations.

**v2.1.0 — 2026-08-12 — Principle IX added: Two-Layer Architecture**

*What changed:* added a new principle requiring the repository to be organised into exactly two
top-level source layers, `api/` and `interface/`, communicating only over HTTP/WebSocket, with no
CLI/command layer between them. Added Principle IX to the mandatory `/speckit.analyze` compliance
review gates in Governance.

*Why:* the repository had grown three independently-evolving backend surfaces — a root-level CLI
package (`astros_upscale`), a local desktop API (`interface/astros_upscale_api`), and a separate
licensing service (`interface/astros_licensing_service`) — plus the Electron frontend, each
reachable through a different mechanism (terminal commands, HTTP, filesystem/subprocess coupling).
This ambiguity about which layer is authoritative is the same failure mode Principle I (Spec
First) exists to prevent, applied to runtime architecture. Consolidating into two layers with one
communication channel removes it.

*Migration:* existing code is not yet compliant — `astros_upscale/cli.py` exposes an interactive
command layer, and the three backend surfaces are not yet organised under a single `api/` root.
This amendment governs the reorganisation carried out under feature spec that follows it; it does
not itself move any files. The licensing service's operational isolation (separate process,
separate secrets) is unaffected — only its location in the repository tree changes.

*Risk accepted:* none — this principle only adds structure that the codebase did not previously
have; it does not permit anything that was previously forbidden.

**v2.2.0 — 2026-08-12 — Principle X added: Interface Structure Is Adapted, Not Templated**

*What changed:* added a new principle governing the internal organisation of `interface/`:
no empty `domain/`/`application/`/`use-cases/` layers, component grouping by reuse instead of a
rigid five-tier taxonomy, an isolated and clearly-named external-access layer (Electron bridge +
HTTP/WS client) instead of DDD-style repository/port ceremony, no abstraction without a real
consumer, and no archived dead code under `legacy`/`old`/`v1`-style naming. Added Principle X to
the mandatory `/speckit.analyze` compliance review gates in Governance.

*Why:* a generic "medium/large web project" template (Atomic Design + Clean Architecture,
domain/application/infrastructure/presentation layers) was proposed for `interface/`. Applied
literally, it would create `domain/` and `application/` folders holding little or nothing, because
Principle IX already requires all business logic to live in `api/` — the same "structure for its
own sake" failure mode Principle IX itself was written to correct on the backend side, this time
on the frontend. This principle makes explicit that generic templates are a source of ideas to
adapt, not a checklist to satisfy.

*Migration:* no existing compliant code becomes non-compliant. `interface/` today has no
`domain/`/`application/` folders and, per audit, only one confirmed dead file
(`components/Versions.vue`, unused electron-vite boilerplate) — this principle governs the
reorganisation carried out under the feature spec that follows it, and does not itself move or
delete any files.

*Risk accepted:* none — this principle only adds structure/constraints the codebase did not
previously have codified; it does not permit anything previously forbidden.

**v2.3.0 — 2026-08-12 — Principle XI added: API Structure Is Consolidated By Domain, Not By Class**

*What changed:* added a new principle governing the internal module layout of `api/`'s two
FastAPI services: fragmented single-responsibility files consolidate into domain-cohesive modules
(`processing.py`, `media.py`, `jobs.py`, `licensing.py`, `security.py`, `routes.py`, `schemas.py`,
`payments.py`, `database.py`) instead of one file per class or one directory per technical layer
(`app/api/`, `app/core/`, `app/models/`); genuine technical separation still stands where a
responsibility is truly independent or a merge would stop reading as one coherent domain; no
behaviour change from consolidation — HTTP/WebSocket contracts and processing/licensing/payment
logic are preserved exactly; no new abstraction is introduced to ease the merge; empty
pre-consolidation directories are deleted, and compatibility shims are folded in rather than
deleted without confirming nothing external still depends on them. Added Principle XI to the
mandatory `/speckit.analyze` compliance review gates in Governance.

*Why:* a structural refactor of `api/` was requested to reduce excessive file fragmentation
(`astros_upscale_api/app/core/` alone held one file per concern — `upscaler.py`,
`video_upscaler.py`, `audio_processor.py`, `component_manager.py`, `capacity.py`,
`license_gate.py`, `license_cache.py`, `license_registry.py`, `profile_resolver.py`,
`offline_tolerance.py`, `protected_loader.py`, `secure_tempdir.py`, `integrity.py`, `dpapi.py`,
`install_identity.py`, `worker_supervisor.py`, `isolated_worker.py`, `job_manager.py` — 18 files
for what groups into five real domains) — the same "structure for its own sake" failure mode
Principle IX corrected across the repository's top level and Principle X corrected inside
`interface/`, occurring a third time inside `api/`'s own internal layout.

*Migration:* no existing compliant code becomes non-compliant by this amendment alone — it
governs the reorganisation carried out under the feature spec that follows it, and does not
itself move, merge, or delete any files.

*Risk accepted:* none — this principle only adds structure/constraints the codebase did not
previously have codified; it does not permit anything previously forbidden.

**Version**: 4.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-21
