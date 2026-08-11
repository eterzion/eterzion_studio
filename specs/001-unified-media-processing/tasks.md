# Tasks: Unified Media Processing

**Input**: Design documents from `specs/001-unified-media-processing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md — all present and clarified (no NEEDS CLARIFICATION remaining)

**Tests**: included. Constitution Principle VIII (Tests Required) and the project's established
pattern (real subprocess/model tests over mocks for core logic) make them non-optional here.

**Organization**: by user story, in the priority order from `spec.md` (three P1, three P2, one P3).
Foundational work that every story depends on structurally — hardware detection, the
operation/profile resolver, the license gate, removing the GFPGAN/facexlib liability — is Phase 2,
not folded into any single story.

**Post-`/speckit.analyze` revision (2026-08-08)**: this version incorporates the fixes from the
analysis report — see the "Analyze fixes applied" note at the bottom for what changed and why.
Task numbering shifted from the pre-analysis version; do not cite old IDs from that report.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: which user story this task belongs to (US1–US7); absent for Setup/Foundational/Polish
- File paths are exact, from `plan.md`'s Project Structure

---

## Phase 1: Setup

**Purpose**: dependencies and empty module skeletons for what Foundational will fill in. No
behavior changes yet.

- [x] T001 [P] Add `pynvml`, `psutil`, `silero-vad`, `librosa` to `interface/astros_upscale_api/requirements.txt` and `requirements.txt` (root), pinned versions — approved in research.md R2/R4
- [x] T002 [P] Add `audiosronnx` and `SonicMaster` as pinned dependencies to `astros_upscale/audio.py`'s optional-extras group, replacing `denoiser`/`voicefixer` in the `[audio]` extra of `pyproject.toml`
- [x] T003 [P] Create empty module skeletons with docstrings: `astros_upscale/content_type.py`, `astros_upscale/hardware.py`, `astros_upscale/media_engine/__init__.py`, `astros_upscale/media_engine/probe.py`, `astros_upscale/media_engine/transcode.py`, `astros_upscale/media_engine/temporal.py`
- [x] T004 [P] Add `slow`/`hardware`/`video`/`audio` pytest markers to `interface/astros_upscale_api/pytest.ini` for the new test domains this feature adds

**Checkpoint**: dependencies resolvable, module skeletons importable, no runtime behavior changed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: infrastructure every user story depends on. **No user story work starts before this
phase is done** — in particular, US1 cannot be honestly tested until the GFPGAN/facexlib liability
is gone and the model registry no longer exposes 19 models.

**⚠️ CRITICAL**: this phase touches code every story exercises. Sequence matters more here than
elsewhere — file-level notes below call out real dependencies, not just nominal ones.

- [x] T005 Remove `astros_upscale/face_restore.py`, the `gfpgan` package dependency, and every `facexlib` import (confirmed to pull in GPL-3.0 SORT via `facexlib/__init__.py`) — grep and remove `face_recovery`/`face_recovery_strength` from `interface/astros_upscale_api/app/core/upscaler.py` and `app/models/schemas.py`
- [x] T006 Implement `astros_upscale/face_enhance.py` (new): YuNet (`cv2.FaceDetectorYN`, MIT) face detection + local unsharp/CLAHE/landmark-region enhancement, replacing what T005 removed — satisfies FR-015, licensed per `docs/models/MODEL_LICENSES.md` §2
- [x] T007 [P] Implement `astros_upscale/hardware.py`: `HardwareCapability` detection — `psutil` for CPU/RAM (total **and** available, FR-080), `pynvml` for NVIDIA VRAM with `torch.cuda.get_device_properties().total_memory` fallback, `ffmpeg -encoders`/`-decoders` output parsing — per research.md R4; `gpu_vendor="unknown"` and `vram_*=null` when not NVIDIA, never fabricated
- [x] T008 [P] Implement `astros_upscale/content_type.py`: image classifier (HSV saturation + Canny edge density + LAB color-block ratio heuristic, DSP only — research.md R1) and audio classifier (`silero-vad` presence-of-speech + `librosa` harmonic/percussive ratio — research.md R2)
- [x] T009 **[Analyze fix G2]** Implement history/job-record compatibility for identifiers `astros_upscale/core.py` is about to stop serving: `ultrasharp`, `animesharp`, `nmkd-siax`, `nmkd-superscale`, `liveaction-span`, and the removed `face_recovery` param (T005). Add a small compatibility map in `interface/astros_upscale_api/app/core/job_manager.py` (or a new `legacy_identifiers.py`) so old `Job`/history records referencing these render as "arquivado" in the UI instead of crashing lookups — satisfies FR-048 and the matching edge case in `spec.md`. **MUST land before T010.**
- [x] T010 Reduce `astros_upscale/core.py` `MODELS` registry: remove `ultrasharp`, `animesharp`, `nmkd-siax`, `nmkd-superscale`, `liveaction-span` (rejected licenses, `docs/models/MODEL_LICENSES.md` §1/§6) — leave the registry keyed toward one entry per content type, final selection pending T023/T024 benchmark. Depends on T009.
- [x] T011 Create `astros_upscale/media_engine/transcode.py` and `probe.py`, consolidating the three duplicate `_run_ffmpeg` implementations in `astros_upscale/utils/video_io.py`, `astros_upscale/audio.py`, and `astros_upscale/optimize.py` into one wrapper — fail loudly at import time if the resolved `ffmpeg` binary reports `--enable-gpl`/`--enable-nonfree` in `ffmpeg -version` (Constitution, Licensing and Distribution Constraints)
- [x] T012 Implement `interface/astros_upscale_api/app/core/profile_resolver.py`: `MediaRequest → Operation Resolver → Profile Resolver → Hardware Detection (T007) → Engine Resolver → Pipeline`, per FR-012 and briefing Seção 11 — the single chokepoint every job passes through
- [x] T013 Generalize `interface/astros_upscale_api/app/core/job_manager.py` from image-only to any `media_type`/`operation`: add `content_type_detected`, `capacity_check`, extended `error_category` (`hardware_insufficient`, `license_invalid`) per `data-model.md` Job entity
- [x] T014 **[Analyze fix G1]** Generalize the protected-execution dispatch in `interface/astros_upscale_api/app/core/worker_supervisor.py`/`isolated_worker.py`/`protected_loader.py`: today it only wraps the static `Upscaler` class (image path). Extend it to accept any registered processing module by reference, so `video_upscaler.py` (T042) and `audio_processor.py` (T053) can be dispatched through the same isolated-process + integrity-check + anti-rollback mechanism — satisfies FR-070 to FR-075 for the two new media domains, not just image.
- [x] T015 Extend `interface/astros_upscale_api/app/models/schemas.py` with `MediaRequest`, `Component`, `LicenseStatus`, and the extended `JobStatus`/`ErrorCategory` enums per `data-model.md` and `contracts/api.md` — reject a `model` field in the request schema outright (validation error, not silent ignore) per FR-011
- [x] T016 Wire the license gate into `interface/astros_upscale_api/app/api/routes_jobs.py`: every `POST /jobs*` route calls the `astros_licensing_service` for current `license.state` and blocks on `blocked`/`not_activated` per FR-051/FR-060, before any job is created — the *mechanism* only; the activation UI itself is US7 (Phase 5)
- [x] T017 [P] Move model-license authority from `interface/astros_upscale_app/src/renderer/src/data/modelLicenses.ts` to a new `interface/astros_upscale_api/app/core/license_registry.py`, sourced from `docs/models/MODEL_LICENSES.md` — the backend that resolves the model MUST be the backend that enforces its licence (FR-046, Constitution "Licensing and Distribution Constraints")

**Checkpoint**: no GFPGAN/GPL liability remains in the dependency tree; every job passes through a
real resolver, a real license gate, and (for image today, video/audio once T042/T053 land) the
protected-execution mechanism; hardware and content-type detection exist and are testable in
isolation; old history records don't crash. User story work can now begin.

---

## Phase 3: User Story 1 — Melhorar uma imagem sem entender de IA (Priority: P1) 🎯 MVP

**Goal**: a person drags in a photo, picks 2x/4x and Rápido/Equilibrado/Qualidade, gets back an
enhanced image, and never sees a model name anywhere.

**Independent Test**: process one image through all six combinations of scale × profile; confirm
increasing time from Rápido to Qualidade; confirm no response, log, or UI surface contains a model
identifier.

### Tests for User Story 1

- [x] T018 [P] [US1] Test: `profile_resolver` maps (content_type=photo, scale, profile) to exactly one implementation with differing execution parameters, never a different model; **and** that an unspecified `profile` resolves to `fast` (FR-008) and that Rápido/Equilibrado/Qualidade produce strictly non-decreasing measured cost in that order (FR-006) — in `interface/astros_upscale_api/tests/test_profile_resolver.py`. **[Analyze fix G5: added the default-profile and priority-ordering assertions this task previously lacked.]**
- [x] T019 [P] [US1] Test: `POST /jobs` response body, WebSocket progress messages, and output filenames never contain a model/checkpoint/engine identifier, for every image scale×profile combination, in `interface/astros_upscale_api/tests/test_no_model_leak.py`

### Implementation for User Story 1

- [x] T020 [US1] Update `interface/astros_upscale_api/app/core/upscaler.py` to resolve its model via `profile_resolver.py` (T012) instead of accepting a model id directly; call `face_enhance.py` (T006) for the face-region step
- [x] T021 [US1] Update `interface/astros_upscale_api/app/api/routes_jobs.py` to accept the `MediaRequest` contract (`media_type`, `operation`, `scale`, `profile`) for image enhance, rejecting any `model` field per T015's schema validation
- [x] T022 [US1] **[Analyze fix I1]** `interface/astros_upscale_app/src/renderer/src/views/ImageEditorView.vue`: remove the manual model/device selectors; replace with a content-type indicator that is **editable, not read-only** — a control limited to the valid content types for the detected media (e.g. `photo` ↔ `anime_image`) so the person can correct a wrong detection. Satisfies FR-096, which the pre-analysis version of this task contradicted.
- [x] T023 [US1] Run the FR-087–093 benchmark (perceptual metric primary, fidelity guard-rail, human visual pass) over the reference set for `photo` and `anime_image` content types — script in `scripts/benchmark_profiles.py`, results recorded in `docs/models/BENCHMARK_RESULTS.md`
- [x] T024 [US1] Finalize `astros_upscale/core.py` registry to exactly one implementation per `{photo, anime_image}` content type based on T023's results (completes T010)

**Checkpoint**: US1 fully functional and independently testable. This is the deployable MVP slice.

---

## Phase 4: User Story 2 — Converter e comprimir sem perder tempo com IA (Priority: P1)

**Goal**: PNG→WebP, MKV→MP4, WAV→MP3 — fast, no profile prompt, no AI invoked.

**Independent Test**: convert/compress one file of each media type; confirm no AI model is loaded
(log/instrumentation check); confirm compression levels produce measurably different file sizes.

### Tests for User Story 2

- [x] T025 [P] [US2] Test: `optimize_file` accepts a different output extension than input (conversion) for image/video/audio, in `tests/test_optimize.py` (extends the existing root-level test file)
- [x] T026 [P] [US2] Test: compress/convert operations never call into `profile_resolver`'s AI-model path — assert via mock/spy that no `spandrel`/`torch` model load occurs, in `interface/astros_upscale_api/tests/test_compress_convert_no_ai.py`

### Implementation for User Story 2

- [x] T027 [US2] Extend `astros_upscale/optimize.py`: remove the same-extension requirement in `optimize_file`, add real conversion paths for image (incl. AVIF), video, audio (FR-025 to FR-030)
- [x] T028 [US2] Route `optimize.py`'s ffmpeg calls through `media_engine/transcode.py` (T011) instead of its own `_run_ffmpeg`
- [x] T029 [US2] `interface/astros_upscale_api/app/api/routes_jobs.py`: accept `operation=compress`/`convert` without requiring a `profile` field when the combination doesn't warrant one (FR-005)
- [x] T030 [US2] New `interface/astros_upscale_app/src/renderer/src/views/CompressConvertView.vue`, replacing the "Otimizar" placeholder — add the corresponding compress/convert client methods to `interface/astros_upscale_app/src/renderer/src/backend.ts` (`contracts/api.md` §Jobs). **[Analyze fix G7.]**
- [x] T031 [US2] Wire `interface/astros_upscale_app/src/renderer/src/App.vue`'s `otimizar` sidebar key to `CompressConvertView.vue` instead of the generic "not implemented" branch

**Checkpoint**: US1 and US2 both independently functional — first two P1 slices deployable.

---

## Phase 5: User Story 7 — Comprar, ativar e continuar usando (Priority: P1)

**Goal**: activate with a purchase, keep working offline within tolerance, release/transfer between
machines without contacting support.

**Independent Test**: activate → process → go offline → process again (still works) → release →
reactivate on a second install.

### Tests for User Story 7

- [x] T032 [P] [US7] Test: activation happy path, installation-limit rejection with clear guidance, release-then-reactivate, **and reinstalling on the same machine does not consume an extra installation slot (FR-055)**, in `interface/astros_licensing_service/tests/test_activation_flow_extended.py` (extends existing licensing test suite). **[Analyze fix G6: FR-055 is exercised by the already-existing `INSERT OR REPLACE` idempotency, now explicitly asserted here instead of only implied.]**
- [x] T033 [P] [US7] Test: offline tolerance window — processing succeeds up to day 30 since last successful revalidation, warns from day 23, blocks after, and clock manipulation does not extend it, in `interface/astros_licensing_service/tests/test_offline_tolerance.py`
- [x] T034 [P] [US7] **[Analyze fix G4]** Test: no request or response body anywhere in the license-check path (`GET /license/status`, the T016 gate call, `astros_licensing_service` activation/webhook payloads) contains file bytes, file content hashes tied to processed media, or any field derived from the media being processed — in `interface/astros_licensing_service/tests/test_no_content_leakage.py`. Satisfies FR-062, which previously had no automated coverage.

### Implementation for User Story 7

- [x] T035 [US7] Implement the 30-day offline tolerance window in `astros_licensing_service` (config default per spec Assumptions; warn from day 23) — check against `installations.last_seen_at`, monotonic where possible to resist clock manipulation (FR-056 to FR-058)
- [x] T036 [US7] Implement `GET /license/status`, `POST /license/activate`, `POST /license/release` facade routes in `interface/astros_upscale_api/app/api/routes_license.py`, delegating to `astros_licensing_service` — no reimplementation of activation logic (Constitution Principle II)
- [x] T037 [US7] Remove the "unconfigured licensing_service_url → no enforcement" fallback path in `interface/astros_upscale_api/app/config.py`/`isolated_worker.py` for production builds; keep an explicit dev/test override, not a silent default
- [x] T038 [US7] New `interface/astros_upscale_app/src/renderer/src/views/LicenseActivationView.vue`: activation, status (installations used/limit, offline days remaining), release — add `GET /license/status`, `POST /license/activate`, `POST /license/release` client methods to `interface/astros_upscale_app/src/renderer/src/backend.ts` (`contracts/api.md` §Licença). **[Analyze fix G7.]**
- [x] T039 [US7] Wire app startup: block media screens behind `LicenseActivationView.vue` when `license.state ∉ {active, offline_tolerance, offline_expiring}`; a `blocked` state never touches files already on disk (FR-059/SC-019)

**Checkpoint**: all three P1 stories done. US1/US2 are now genuinely gated by a real license, not a
bypassed one — this is the point where the product's actual business model is enforced end-to-end.

---

## Phase 6: User Story 3 — Melhorar um vídeo preservando o que importa (Priority: P2)

**Goal**: upscale a video from the desktop app (today CLI-only) without breaking fps, audio, sync,
or aspect ratio.

**Independent Test**: process a short video with audio; verify via `ffprobe` that duration, frame
rate, audio channel count, and aspect ratio are unchanged.

### Tests for User Story 3

- [x] T040 [P] [US3] Test: `ffprobe`-verified fps/duration/audio-channel/aspect-ratio preservation across a real short clip, for both `real_video` and `anime_video` content types, in `interface/astros_upscale_api/tests/test_video_upscaler.py`
- [x] T041 [P] [US3] Test: secondary-elements detection flags extra audio tracks/subtitles/chapters and the job does not start without `secondary_elements_ack`, in `interface/astros_upscale_api/tests/test_secondary_elements.py`

### Implementation for User Story 3

- [x] T042 [US3] Implement `interface/astros_upscale_api/app/core/video_upscaler.py`, wrapping the existing `astros_upscale/cli.py` `run_video` logic as a job instead of a CLI-only path — reuses `VideoReader`/`VideoWriter` from `astros_upscale/utils/video_io.py`; **dispatched through the generalized protected-execution mechanism from T014**, not run as a bare in-process call
- [x] T043 [US3] Implement deterministic tiling in `astros_upscale/media_engine/temporal.py`: tile size/offset/overlap fixed for the whole video, never varied per frame (FR-101)
- [x] T044 [US3] Implement `atadenoise` (pre-upscale) and `deflicker` (post-upscale) temporal stabilization in `media_engine/temporal.py`, both LGPL FFmpeg filters — never `hqdn3d` (GPL) (FR-102, research.md §"Consistência temporal")
- [x] T045 [US3] Add `real_video` content type to `astros_upscale/core.py`: `2xPublic_realplksr_dysample_layernorm_real_nn` (Apache-2.0, `docs/models/MODEL_LICENSES.md` §3-ter)
- [x] T046 [US3] **[Analyze fix G3]** Add `anime_video` content type to `astros_upscale/core.py`: `realesr-animevideov3` (BSD-3-Clause, already approved and already in the pre-reduction registry) — FR-094 declares six content types; this one was previously left unwired with no documented reason, unlike the deliberate LC-001–004 gaps.
- [x] T047 [US3] Implement secondary-elements probing in `astros_upscale/media_engine/probe.py` (extra audio tracks, subtitles, chapters) and a pending-confirmation job state in `job_manager.py` (FR-081 to FR-086)
- [x] T048 [US3] `interface/astros_upscale_api/app/api/routes_jobs.py`: require `secondary_elements_ack=true` before enqueueing when the probe finds losses; skip the prompt entirely when nothing is lost (FR-085)
- [x] T049 [US3] New `interface/astros_upscale_app/src/renderer/src/views/VideoView.vue`, replacing the placeholder, with the secondary-elements confirmation dialog — add the video-enhance job client methods (incl. the `secondary_elements_ack` confirmation step) to `interface/astros_upscale_app/src/renderer/src/backend.ts`. **[Analyze fix G7.]**
- [x] T050 [US3] Wire `App.vue`'s `video` sidebar key to `VideoView.vue`

**Checkpoint**: US3 independently functional. Video enhance is now a real product feature, not a
CLI-only capability with an empty tab — and both live-action and anime video are covered, not just
one.

---

## Phase 7: User Story 4 — Melhorar um áudio ruim (Priority: P2)

**Goal**: noise reduction, loudness normalization, and voice clarity/music restoration, chosen by
Rápido/Equilibrado/Qualidade only.

**Independent Test**: process a recording with known noise; measure objectively that noise
decreased, loudness hit the target, and duration/channels are unchanged.

### Tests for User Story 4

- [x] T051 [P] [US4] Test: noise reduction is measurable (before/after noise-floor comparison), loudness normalization hits the configured LUFS target, duration and channel count preserved, in `interface/astros_upscale_api/tests/test_audio_processor.py`
- [x] T052 [P] [US4] Test: content-type classifier routes a speech sample to `audiosronnx` and a music sample to `SonicMaster`, in `interface/astros_upscale_api/tests/test_content_type_audio.py`

### Implementation for User Story 4

- [x] T053 [US4] Implement `interface/astros_upscale_api/app/core/audio_processor.py`: DSP chain (FFmpeg LGPL filters — `afftdn`/`anlmdn` noise reduction, `loudnorm` normalization, `deesser`/`firequalizer`/`acompressor` voice clarity) per `docs/models/MODEL_LICENSES.md` §4; **dispatched through the generalized protected-execution mechanism from T014**, not run as a bare in-process call
- [x] T054 [US4] Integrate `audiosronnx` as the `speech` content-type implementation (bandwidth extension, Apache-2.0)
- [x] T055 [US4] Integrate `SonicMaster` as the `music` content-type implementation, setting `license_status=approved_conditional` **and** `license_condition` (machine-readable trigger text — e.g. "cease use or negotiate an enterprise licence with Stability AI once annual revenue exceeds USD $1,000,000, per the Stable Audio Open VAE dependency") on its `ContentTypeImplementation` entry (`data-model.md`) — a data field only, no dependency on `component_manager.py` (T068, Polish) existing yet. `component_manager` reads both fields once T068 lands, making the licence-condition obligation (FR-099/FR-100) trackable and revisitable rather than a boolean nobody can interpret without going back to `docs/models/MODEL_LICENSES.md`. **[Analyze fix G9.]**
- [x] T056 [US4] Wire `astros_upscale/content_type.py`'s audio classifier (T008) into `audio_processor.py`'s dispatch (speech → audiosronnx path + DSP; music → SonicMaster + DSP)
- [x] T057 [US4] New `interface/astros_upscale_app/src/renderer/src/views/AudioView.vue`, replacing the placeholder — copy MUST NOT claim compression-artifact removal (FR-023; there is no implementation for it, see `spec.md` LC-003); add the audio-enhance job client methods to `interface/astros_upscale_app/src/renderer/src/backend.ts`. **[Analyze fixes U1, G7.]**
- [x] T058 [US4] Wire `App.vue`'s `audio` sidebar key to `AudioView.vue`

**Checkpoint**: US4 independently functional. All three "Melhorar" media types (image, video,
audio) now work end-to-end.

---

## Phase 8: User Story 5 — Funcionar bem na máquina que a pessoa tem (Priority: P2)

**Goal**: no GPU → CPU fallback, real GPU → real speedup, oversized file → honest refusal before
processing starts, not a crash mid-way.

**Independent Test**: run the same operation on a GPU machine and a CPU-only machine; confirm both
succeed and that the actually-applied execution parameters differ.

### Tests for User Story 5

- [x] T059 [P] [US5] Test: `HardwareCapability` with injected low-RAM/no-GPU values produces a smaller computed capacity than injected high-RAM/GPU values, in `interface/astros_upscale_api/tests/test_hardware.py`
- [x] T060 [P] [US5] Test: a request whose size exceeds computed capacity is rejected before any processing starts, with the limiting resource named in the error, in `interface/astros_upscale_api/tests/test_capacity_gate.py`

### Implementation for User Story 5

- [x] T061 [US5] Wire `hardware.py` (T007) into `profile_resolver.py` (T012), replacing the fixed `_TILE_THRESHOLD=1600`/`_TILE_SIZE=512` constants in `astros_upscale/core.py` with values computed from `HardwareCapability` (FR-031 to FR-035)
- [x] T062 [US5] Implement the capacity check (FR-076 to FR-080): estimate max processable size/duration from `HardwareCapability`, refuse with a named limiting resource before processing when exceeded — wired into `job_manager.py`'s job-creation path
- [x] T063 [US5] Surface an estimated-duration field in the `POST /jobs` response for long-running operations (FR-078), computed alongside the capacity check
- [x] T064 [US5] Audit every content-type implementation's model loading for a working `device="cpu"` path (spandrel `ModelLoader`) — fix any that assume CUDA is present

**Checkpoint**: US5 independently functional — the adaptive layer that FR-031 to FR-035 and the
Constitution's Principle VII require is real, not aspirational.

---

## Phase 9: User Story 6 — Acompanhar e controlar o que está rodando (Priority: P3)

**Goal**: queue multiple files, see accurate state for each, cancel what hasn't started or is
mid-flight, and have cancellation actually free resources.

**Independent Test**: queue several files, cancel one waiting and one processing, confirm states
reflect reality and the cancelled one actually stopped.

### Tests for User Story 6

- [x] T065 [P] [US6] Test: cancelling a video/audio job kills its worker subprocess and releases resources within 5 seconds, extending the real-subprocess pattern already used in `interface/astros_upscale_api/tests/test_worker_supervisor.py`

### Implementation for User Story 6

- [x] T066 [US6] Extend `interface/astros_upscale_app/src/renderer/src/views/HistoryView.vue` and the shared queue store to display `media_type`-aware job state, queue position, and error explanation across image/video/audio — including the "arquivado" rendering for legacy identifiers from T009
- [x] T067 [US6] Extend `job_manager.py`'s watchdog loop (`_watchdog_loop`) to cover the video/audio worker paths added in Phases 6–7, not just image

**Checkpoint**: all 7 user stories independently functional. Every screen in the product now does
what its tab claims.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: work that no single user story gates, but the spec and Constitution both require
before this feature is actually done.

- [x] T068 [P] Implement `interface/astros_upscale_api/app/core/component_manager.py`: on-demand download, integrity verification, local cache, eviction (FR-041/FR-042/FR-067 to FR-069, briefing Seção 20)
- [x] T069 [P] New `interface/astros_upscale_app/src/renderer/src/views/ComponentsView.vue`, replacing `ModelsView.vue`: capability-first list (FR-063), opt-in technical-details panel with licence/attribution (FR-065/FR-066) — remove `ModelsView.vue` once this ships, don't keep both (Constitution Principle II); add `GET /components`, `GET /components/{id}/details`, install/update/delete client methods to `interface/astros_upscale_app/src/renderer/src/backend.ts` per the contract already fixed in `contracts/api.md` (still parallel-safe against T070 — same interface, different files). **[Analyze fix G7.]**
- [x] T070 [P] Implement `interface/astros_upscale_api/app/api/routes_components.py`: `GET /components`, `GET /components/{id}/details`, install/update/delete, per `contracts/api.md` — remove the old `GET /models` route in `interface/astros_upscale_api/app/api/routes_models.py` once this ships (`contracts/api.md` explicitly names `/components` as its replacement; the old route returns raw model identifiers and violates FR-009/SC-002 if left reachable). **[Analyze fix G8.]**
- [x] T071 Remove `interface/astros_upscale_app/src/renderer/src/data/modelLicenses.ts` entirely — final sweep confirming no frontend surface holds license authority (FR-046, completes T017)
- [x] T072 Verify the FFmpeg binary the app actually embeds/ships reports no `--enable-gpl`/`--enable-nonfree` in `ffmpeg -version`; replace with an LGPL build if it does; record the verification (date, command output) in `docs/models/MODEL_LICENSES.md` §5
- [x] T073 [P] Add a visible attribution/credits surface (Settings or About) listing CC-BY-4.0 (Philip Hofmann), Apache-2.0 NOTICE texts, and BSD disclaimers for every shipped component (FR-045, SC-012)
- [x] T074 Run `quickstart.md` end-to-end against a real build (all 7 US sections + the transversal conformance checklist at the bottom)
- [x] T075 [P] Update `docs/audit/phase0-inventory.md` §6 "Pendências desta fase" to mark resolved items against this feature's actual delivery
- [x] T076 Full-repository sweep for any remaining raw model-name string reachable from a user-facing surface (final SC-002 verification, beyond what T019 already covers per-request); confirm FR-050 (no commercially-permitted capability lost in the transition without a recorded decision) against the full LC-001–004 list in `spec.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks every user story**; T005/T006 block T020 (US1); T007/T008 block T061 (US5) and T056 (US4); T009 blocks T010 (must land first, not just "completed by" — this is the analyze-fix ordering correction); T010 is completed by T024 (US1); T011 blocks T028 (US2) and T043/T044 (US3); T012 blocks all resolver-dependent tasks in every story; T014 blocks T042 (US3) and T053 (US4); T016 blocks T039 (US7); T017 blocks T071 (Polish)
- **User Stories (Phase 3–9)**: all depend on Foundational. The three P1 stories (US1, US2, US7) are listed first and can proceed in parallel once Foundational is done; US7's Phase 5 doesn't block US1/US2's Phases 3–4 structurally (the gate mechanism is already live from T016), but a fully honest end-to-end demo of any story implies US7 is also done
- **Polish (Phase 10)**: depends on all seven user stories being complete — T069/T070 in particular assume `component_manager.py` semantics that every content-type integration (T024, T045, T046, T054, T055) has already exercised. Note the one intentional forward reference: T055 sets `license_status=approved_conditional` as a data field before `component_manager.py` (T068) exists to read it — this is safe (no code dependency), but implementers following phases strictly should be aware T068 is where that field starts being acted on

### User Story Dependencies

- **US1 (P1)**: depends only on Foundational
- **US2 (P1)**: depends only on Foundational — no dependency on US1
- **US7 (P1)**: depends only on Foundational (T016 already provides the mechanism; Phase 5 builds the user-facing flow around it)
- **US3 (P2)**: depends on Foundational; reuses `media_engine` (T011) and the generalized protected dispatch (T014) built in Foundational, not on US1/US2 code
- **US4 (P2)**: depends on Foundational (including T014); independent of US1/US2/US3
- **US5 (P2)**: depends on Foundational (T007/T008); its tasks modify the resolver every other story already calls, so in practice sequence it after at least one processing story (US1) has a working baseline to test capacity gating against
- **US6 (P3)**: depends on Foundational; touches job/queue surfaces that US3/US4 extend, so sequence last among processing-adjacent stories

### Within Each User Story

- Tests before implementation, and MUST fail first
- Backend resolution/processing logic before the Vue view that calls it
- View wiring into `App.vue`'s sidebar routing is the last task in each story that has a UI component

### Parallel Opportunities

- All Setup tasks (T001–T004) — different files, no shared state
- Within Foundational: T007, T008, T017 are mutually independent of each other (not of T005/T006/T009/T010/T011/T014, which touch shared files sequentially or have a hard ordering — T009 before T010, T011/T012/T013 before T014's downstream consumers)
- Once Foundational is done: **US1, US2, and US7 can be staffed in parallel** at the story level — but T030 (US2) and T038 (US7) both add methods to `interface/astros_upscale_app/src/renderer/src/backend.ts`, and T049/T057/T069 (US3/US4/Polish) do the same later. This is a small, additive, low-conflict shared file (each task adds its own client method), not a logical dependency — but if staffed by different people at the same time, rebase/merge `backend.ts` deliberately rather than assuming zero overlap. **[Analyze fix G7 follow-up: this note replaces the earlier, now-inaccurate "none of their implementation tasks touch the same files."]**
- Within each story, all `[P]`-marked test tasks run together before that story's implementation tasks begin

---

## Parallel Example: Foundational

```bash
# After T005/T006 (face-restore removal) land, these three can run together:
Task: "Implement astros_upscale/hardware.py per research.md R4"
Task: "Implement astros_upscale/content_type.py per research.md R1/R2"
Task: "Move model-license authority to app/core/license_registry.py"
```

## Parallel Example: P1 stories

```bash
# Once Foundational's checkpoint is reached, three people/agents can work simultaneously:
Task: "US1 — image enhance (T018-T024)"
Task: "US2 — compress/convert (T025-T031)"
Task: "US7 — license activation (T032-T039)"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational) — **critical, blocks everything**
2. Phase 3 (US1) → stop, validate against quickstart.md's US1 section
3. This is the smallest deployable slice that is honestly better than what ships today: one
   image model per content type instead of nineteen exposed by name, real hardware-adaptive
   tiling instead of a fixed threshold, and no GPL/non-commercial liability in the dependency tree.
4. **Caveat, not an extra phase**: T016 (Foundational) gates every `POST /jobs` behind a valid
   license, so validating US1 in isolation still requires an active test license against
   `astros_licensing_service` — reachable directly through its existing, already-implemented API
   even before US7's facade routes (T036) or UI (T038) exist. `quickstart.md`'s Pré-requisitos
   already states this; it's restated here so "MVP = Phase 3 only" isn't read as "no license
   needed yet". **[Analyze fix G10, found in re-verify pass 11.]**

### Incremental Delivery

1. Setup + Foundational → foundation ready, GFPGAN/facexlib liability gone
2. US1 → validate → this is the MVP
3. US2 → validate (independent of US1, can ship same week)
4. US7 → validate — **do this before calling the product launch-ready**; without it the licensing
   infrastructure stays the "built but switched off" state the Phase 0 audit found
5. US3, US4, US5 in any order — each is independently demoable
6. US6 → validate
7. Polish — component management UI, attribution surface, final license/GPL verification sweep

### Notes specific to this feature

- T009/T010/T024 split the model-registry reduction into three tasks deliberately: T009 protects
  existing history against what's about to disappear, T010 removes what's already known to be
  rejected (license), T024 finalizes what remains based on **measurement** (Constitution
  Principle III — no model gets chosen by reputation or file size).
- T055's `license_status=approved_conditional` wiring exists because FR-099/FR-100 explicitly
  forbid treating the SonicMaster decision as a one-time approval — it needs to stay a checkable,
  revisitable fact in the running system, not just a paragraph in `MODEL_LICENSES.md`.
- Any task that touches `astros_upscale/core.py`'s `MODELS` registry (T009, T010, T024, T045,
  T046) or the audio engine registry (T054, T055) MUST cite the corresponding row in
  `docs/models/MODEL_LICENSES.md` in its commit message — this is the enforcement mechanism for
  Constitution Principle IV at the commit level, not just at spec level.

### Analyze fixes applied (2026-08-08)

`/speckit.analyze` ran **13 times total** against this file (the initial pass plus 12
re-verification passes at increasing levels of scrutiny — ID sequencing, cross-reference
integrity, `[P]`-marker file conflicts, `plan.md`/`contracts/api.md`/`data-model.md` cross-artifact
consistency, Success Criteria coverage, `MODEL_LICENSES.md` section citations, Assumptions-value
consistency, MVP-path license-gate dependency, tests-before-implementation ordering across all 7
stories, same-file edit ordering, and terminology consistency across all four artifacts).
Task numbering shifted once, in the first pass (72 → 76 tasks); every later pass only edited
descriptions in place, so no IDs moved after that:

| Finding | Fix |
|---|---|
| I1 (CRITICAL) — T020 (now T022) described the content-type indicator as read-only, contradicting FR-096 | Made it an editable override control |
| G1 (CRITICAL) — video/audio processing had no task routing them through the protected-execution mechanism FR-070–075 require | Added T014 (generalize the dispatch) and referenced it from T042/T053 |
| G2 (CRITICAL) — no task protected existing history from the model-registry reduction, despite spec.md naming this exact edge case | Added T009, sequenced before T010 |
| G3 (HIGH) — `anime_video` content type had no implementation task despite an already-approved model existing | Added T046 |
| G4 (MEDIUM) — FR-062 (no file-content leakage into license checks) had no automated test | Added T034 |
| G5 (MEDIUM) — default-to-fast and profile priority ordering weren't asserted anywhere | Extended T018 |
| G6 (LOW) — FR-055 (reinstall doesn't consume an extra slot) wasn't cited in its covering test | Extended T032 |
| U1 (LOW) — no task guarded AudioView.vue's copy against overpromising artifact removal | Added a note to T057 |
| I2 (LOW, found in re-verify pass 2) — T055 forward-referenced `component_manager` (T068, Polish) from inside US4 (Phase 7), ambiguous under strict phase ordering | Clarified as a data-field-only reference, no code dependency; noted in Dependencies |
| G7 (MEDIUM, found in re-verify pass 3) — `backend.ts`, explicitly marked "ESTENDER" in `plan.md`, was touched by zero tasks | Added client-method work to T030/T038/T049/T057/T069; corrected the now-inaccurate "no shared files" claim in Parallel Opportunities |
| G8 (HIGH, found in re-verify pass 6) — `contracts/api.md` names `/components` as the replacement for `GET /models`, but no task removed the old route, which still leaks raw model identifiers | Extended T070 to remove `routes_models.py`'s old route |
| G9 (LOW, found in re-verify pass 7) — T055 set `license_status=approved_conditional` but not the paired `license_condition` trigger text `data-model.md` defines, leaving FR-100's "revisitable" requirement under-served | Extended T055 to set both fields |

| G10 (MEDIUM, found in re-verify pass 11) — "MVP First" implied Phase 3 (US1) alone is demoable, without noting T016's Foundational license gate blocks every `POST /jobs` regardless of story | Added an explicit caveat to "MVP First", cross-referencing what `quickstart.md`'s Pré-requisitos already required |

No findings in re-verify passes 4, 5, 8, 9, 10, 12, 13, 14, or 15 — checklist format (all 76
lines), `[P]`-marker file-conflict safety, Success Criteria coverage, `MODEL_LICENSES.md` section
citations, Assumptions-value consistency (30-day offline tolerance, day-23 warning, installation
limit), tests-before-implementation ordering in every story, same-file task ordering (T005 before
T015 on `schemas.py`), and cross-artifact terminology consistency were all confirmed correct as
written.
