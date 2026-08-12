<!--
SYNC IMPACT REPORT
==================
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

**Rationale:** the harm this principle prevents is forcing an engineering decision onto someone who
cannot evaluate it, and welding the product to an implementation detail that must stay free to
change. Neither harm occurs when a user deliberately opens a details panel to read what is
installed and under what licence. Without this exception the principle would also contradict
Principle IV, which requires attribution to be visible in the shipped product — and attribution is
impossible without naming what is being attributed.

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
  is supposed to contain lives elsewhere is not architecture, it is decoration.
- **Component organisation follows reuse, not a fixed taxonomy.** `interface/` is not obligated
  to use the full Atomic Design five-tier split (atoms/molecules/organisms/templates/pages). A
  simpler split — generic, reusable primitives versus composite blocks tied to one feature — MUST
  be used only where it measurably reduces fragmentation, and MUST NOT be imposed as a taxonomy
  exercise on a component count too small to need it.
- **External-access code is isolated and named for what it does.** The boundary code that talks
  to something outside the renderer process (the Electron `contextBridge` bridge, the HTTP/WebSocket
  client that talks to `api/astros_upscale_api`) MUST be kept out of components and views — no
  component or view may call `fetch`/IPC directly — and MUST be named so its purpose is obvious
  from the name alone. It MUST NOT be dressed up as a `repository`/`port`/`adapter` abstraction
  when there is, and will only ever be, one real implementation.
- **No abstraction without a real consumer.** Interfaces or contracts for a single implementation,
  wrapper functions that only forward a call, `index.ts` files that exist only to re-export, and
  splitting a file for line-count reasons alone (with no distinct responsibility behind the split)
  are all prohibited. A file MUST be split only when it has genuinely separable responsibilities,
  is reused from more than one place, or splitting it measurably improves testability or
  maintainability — never on size alone.
- **Dead code is deleted, not archived.** Files or folders named/suffixed `old`, `legacy`,
  `deprecated`, `backup`, `copy`, `temp`, `v1`, `previous` (or equivalent) MUST NOT exist in
  `interface/`. If the current flow does not use it, it is removed — "keeping it just in case" is
  not a valid reason to keep unreferenced code in a version-controlled repository.

**Rationale:** this project already carries the scar tissue of applying structure for its own
sake — three independently-grown backend surfaces before Principle IX consolidated them. Importing
a generic "medium/large web project" template wholesale into a small, thin Electron renderer would
reproduce that exact mistake on the frontend: folders that exist to satisfy a pattern instead of a
real need, adding indirection a ~20-component app never asked for. Principle II (Reuse First) and
this principle share the same instinct — prefer what the codebase already needs over what a
template says it should have.

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
V (Models Are Internal), VIII (Tests Required), IX (Two-Layer Architecture) and
X (Interface Structure Is Adapted, Not Templated) are the mandatory review gates.

Complexity MUST be justified. A simpler implementation that satisfies the specification is
preferred to a more capable one that exceeds it.

### Amendment log

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

**Version**: 2.2.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-12
