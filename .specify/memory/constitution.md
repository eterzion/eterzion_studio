<!--
SYNC IMPACT REPORT
==================
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
V (Models Are Internal) and VIII (Tests Required) are the mandatory review gates.

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

**Version**: 2.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-08
