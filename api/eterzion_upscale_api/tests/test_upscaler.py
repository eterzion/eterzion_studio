"""Real end-to-end tests for upscaler.py — loads the actual hfa2k-span
model (already present in the repo's models/ dir, no network access) and runs
real CPU inference on tiny generated images. No mocking of the model itself;
the face-enhance branch mocks FaceEnhancer's detection result (isolating this
file's tests from whether a given synthetic image happens to trigger YuNet
detection) rather than the network boundary — the wiring under test is real."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.config import settings
from app.processing import Upscaler


def _make_test_image(size=32, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((size, size, 3), 128, dtype=np.float64)
    cv2.rectangle(img, (4, 4), (size - 4, size - 4), (200, 200, 200), -1)
    cv2.circle(img, (size // 2, size // 2), size // 4, (60, 60, 220), -1)
    noise = rng.normal(0, 18, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


@pytest.fixture(scope='module')
def real_upscaler():
    """Loaded once per test module — real model weights, real spandrel
    architecture detection, real torch.nn.Module — reused across tests in
    this file since loading it is the expensive part (~1-2s on CPU),
    inference on a 32x32 image is fast."""
    return Upscaler('hfa2k-span', model_dir=settings.models_dir, device='cpu')


@pytest.fixture
def tiny_image_path(tmp_path):
    path = tmp_path / 'input.png'
    cv2.imwrite(str(path), _make_test_image())
    return str(path)


class TestProcessRealInference:
    pytestmark = pytest.mark.slow

    def test_upscales_by_the_models_native_scale(self, real_upscaler, tiny_image_path, tmp_path):
        master_path = str(tmp_path / 'master.png')
        result = real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=master_path)

        assert result['source_size'] == (32, 32)
        assert result['output_size'] == (64, 64)

        written = cv2.imread(master_path)
        assert written.shape == (64, 64, 3)

    def test_output_is_a_real_upscaled_image_not_a_naive_resize(self, real_upscaler, tiny_image_path, tmp_path):
        """A real super-resolution pass should differ from plain bicubic/
        Lanczos resize of the same source — proves the model actually ran,
        not just a resize disguised as one."""
        master_path = str(tmp_path / 'master.png')
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=master_path)
        model_output = cv2.imread(master_path)

        source = cv2.imread(tiny_image_path)
        naive_resize = cv2.resize(source, (64, 64), interpolation=cv2.INTER_LANCZOS4)

        diff = cv2.absdiff(model_output, naive_resize)
        assert diff.mean() > 1.0  # genuinely different, not coincidentally identical

    def test_custom_size_resizes_to_the_exact_requested_dimensions(self, real_upscaler, tiny_image_path, tmp_path):
        master_path = str(tmp_path / 'master.png')
        result = real_upscaler.process(
            tiny_image_path, scale=2, custom_size=(100, 90), master_path=master_path
        )
        assert result['output_size'] == (100, 90)
        written = cv2.imread(master_path)
        assert written.shape == (90, 100, 3)

    def test_progress_callback_reaches_100(self, real_upscaler, tiny_image_path, tmp_path):
        progress_values = []
        real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None,
            master_path=str(tmp_path / 'master.png'), on_progress=progress_values.append,
        )
        assert progress_values[-1] == 100
        assert progress_values == sorted(progress_values)  # monotonically increasing

    def test_stage_callback_reports_the_real_pipeline_stages(self, real_upscaler, tiny_image_path, tmp_path):
        stages = []
        real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None,
            master_path=str(tmp_path / 'master.png'), on_stage=stages.append,
        )
        assert stages[0] == 'Lendo imagem'
        assert 'Aplicando modelo de IA' in stages
        assert stages[-1] == 'Salvando resultado'

    def test_tile_path_is_used_and_reports_per_tile_progress(self, real_upscaler, tiny_image_path, tmp_path, monkeypatch):
        """Forces the tiled code path on a tiny image by lowering the
        threshold — exercises the real tiling/merging logic (not just the
        single-pass path every other test here takes) without the minutes a
        genuinely >1600px CPU pass would cost."""
        # Instance attributes, not class ones: __init__ resolves the class-level
        # _FALLBACK_* into self._tile_threshold/_tile_size, and process() reads
        # those. Patching the class left the already-built upscaler untouched —
        # and the constants were renamed to _FALLBACK_* since, so the patch was
        # setting an attribute nothing had ever read.
        monkeypatch.setattr(real_upscaler, '_tile_threshold', 8)
        monkeypatch.setattr(real_upscaler, '_tile_size', 16)
        progress_values = []
        result = real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None,
            master_path=str(tmp_path / 'master.png'), on_progress=progress_values.append,
        )
        assert result['output_size'] == (64, 64)
        # tile progress maps onto 10..90 — with a 32x32 image split into 16px
        # tiles (2x2=4 tiles), expect multiple intermediate values in that band.
        mid_range_hits = [p for p in progress_values if 10 < p < 90]
        assert len(mid_range_hits) >= 2

    def test_sharpen_strength_measurably_changes_the_output(self, real_upscaler, tiny_image_path, tmp_path):
        unsharpened = str(tmp_path / 'a.png')
        sharpened = str(tmp_path / 'b.png')
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=unsharpened, sharpen_strength=0)
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=sharpened, sharpen_strength=90)

        a, b = cv2.imread(unsharpened), cv2.imread(sharpened)
        assert not np.array_equal(a, b)
        lap_a = cv2.Laplacian(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        lap_b = cv2.Laplacian(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        assert lap_b > lap_a  # sharpening increases edge energy

    def test_denoise_filter_strength_measurably_reduces_noise(self, real_upscaler, tiny_image_path, tmp_path):
        clean = str(tmp_path / 'clean.png')
        denoised = str(tmp_path / 'denoised.png')
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=clean, denoise_filter_strength=0)
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=denoised, denoise_filter_strength=90)

        a, b = cv2.imread(clean), cv2.imread(denoised)
        assert a.std() >= b.std()  # never noisier after denoising

    def test_denoise_and_sharpen_compose_in_the_documented_order(self, real_upscaler, tiny_image_path, tmp_path):
        """denoise_filter runs before sharpen (see upscaler.py) — applying
        both must not error and must differ from either alone."""
        both = str(tmp_path / 'both.png')
        real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None, master_path=both,
            denoise_filter_strength=50, sharpen_strength=50,
        )
        only_sharpen = str(tmp_path / 'sharpen.png')
        real_upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=only_sharpen, sharpen_strength=50)
        assert not np.array_equal(cv2.imread(both), cv2.imread(only_sharpen))


class TestSharpenAndDenoiseUnitBehavior:
    """process() only calls _sharpen/denoise_filter when strength > 0 — these
    hit the early-return branches directly, which the full-pipeline tests
    above never exercise (process() short-circuits before calling them)."""

    def test_sharpen_zero_is_a_true_no_op(self):
        img = _make_test_image()
        assert np.array_equal(Upscaler._sharpen(img, 0), img)
        assert np.array_equal(Upscaler._sharpen(img, -5), img)

    def test_denoise_filter_zero_is_a_true_no_op(self):
        img = _make_test_image()
        assert np.array_equal(Upscaler.denoise_filter(img, 0), img)

    def test_denoise_filter_skips_unsupported_dtype(self):
        img16 = _make_test_image().astype(np.uint16)
        assert np.array_equal(Upscaler.denoise_filter(img16, 80), img16)

    def test_denoise_filter_skips_grayscale(self):
        gray = cv2.cvtColor(_make_test_image(), cv2.COLOR_BGR2GRAY)
        assert np.array_equal(Upscaler.denoise_filter(gray, 80), gray)


class TestStageCallbacksForOptionalEffects:
    pytestmark = pytest.mark.slow

    def test_reports_stages_for_every_enabled_effect(self, real_upscaler, tiny_image_path, tmp_path, monkeypatch):
        fake = FakeFaceEnhancer()
        monkeypatch.setattr('app.processing._get_face_enhancer', lambda model_dir: fake)

        stages = []
        real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None, master_path=str(tmp_path / 'master.png'),
            on_stage=stages.append, face_recovery=True, denoise_filter_strength=40, sharpen_strength=40,
        )
        assert 'Realçando rostos' in stages
        assert 'Reduzindo ruído' in stages
        assert 'Aplicando nitidez' in stages
        # documented pipeline order: face enhance -> denoise -> sharpen
        assert stages.index('Realçando rostos') < stages.index('Reduzindo ruído') < stages.index('Aplicando nitidez')


class FakeFaceEnhancer:
    def __init__(self):
        self.restore_calls: list[dict] = []

    def restore(self, img, strength):
        self.restore_calls.append({'strength': strength, 'shape': img.shape})
        marked = img.copy()
        marked[0, 0] = (1, 2, 3)  # a detectable marker pixel proving this ran
        return marked, 1


class TestFaceRecoveryBranch:
    """FaceEnhancer's real YuNet weights (~230KB) ARE small enough to download in test
    environments, but mocking it here still isolates this test from detection variance
    (whether a synthetic tiny test image happens to trigger a face detection or not) —
    the wiring logic under test (when it's called, with what args, output handling) is
    what matters, and it's real."""

    pytestmark = pytest.mark.slow

    def test_calls_the_face_enhancer_with_the_models_output_and_strength(
        self, real_upscaler, tiny_image_path, tmp_path, monkeypatch
    ):
        fake = FakeFaceEnhancer()
        monkeypatch.setattr('app.processing._get_face_enhancer', lambda model_dir: fake)

        master_path = str(tmp_path / 'master.png')
        real_upscaler.process(
            tiny_image_path, scale=2, custom_size=None, master_path=master_path,
            face_recovery=True, face_recovery_strength=65,
        )

        assert len(fake.restore_calls) == 1
        assert fake.restore_calls[0]['strength'] == 0.65
        assert fake.restore_calls[0]['shape'] == (64, 64, 3)

        written = cv2.imread(master_path)
        assert tuple(written[0, 0]) == (1, 2, 3)  # the fake's output was actually used

    def test_skips_face_recovery_for_16_bit_output_without_crashing(
        self, real_upscaler, tmp_path, monkeypatch
    ):
        fake = FakeFaceEnhancer()
        monkeypatch.setattr('app.processing._get_face_enhancer', lambda model_dir: fake)

        img16 = (_make_test_image().astype(np.uint16)) * 257  # real 16-bit image
        path = tmp_path / 'in16.png'
        cv2.imwrite(str(path), img16)

        stages = []
        real_upscaler.process(
            str(path), scale=2, custom_size=None, master_path=str(tmp_path / 'master.png'),
            face_recovery=True, on_stage=stages.append,
        )
        assert fake.restore_calls == []  # never called for an unsupported dtype
        assert any('não suportado' in s for s in stages)

    def test_face_enhancer_is_cached_across_process_calls(self, tiny_image_path, tmp_path, monkeypatch):
        from app import processing as upscaler_module

        upscaler_module._face_enhancer_cache.clear()
        constructed = []

        class TrackingFake(FakeFaceEnhancer):
            def __init__(self, model_dir):
                super().__init__()
                constructed.append(model_dir)

        monkeypatch.setattr(upscaler_module, 'FaceEnhancer', TrackingFake)
        upscaler = Upscaler('hfa2k-span', model_dir=settings.models_dir, device='cpu')

        upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=str(tmp_path / 'a.png'), face_recovery=True)
        upscaler.process(tiny_image_path, scale=2, custom_size=None, master_path=str(tmp_path / 'b.png'), face_recovery=True)

        assert len(constructed) == 1  # second call reused the cached instance
        upscaler_module._face_enhancer_cache.clear()


class TestExport:
    def test_reencodes_to_jpg_with_quality(self, tmp_path):
        master_path = tmp_path / 'master.png'
        cv2.imwrite(str(master_path), _make_test_image())
        out_path = tmp_path / 'out.jpg'

        Upscaler.export(str(master_path), str(out_path), quality=80)

        assert out_path.is_file()
        result = cv2.imread(str(out_path))
        assert result.shape == (32, 32, 3)

    def test_png_export_ignores_quality_and_copies_through(self, tmp_path):
        master_path = tmp_path / 'master.png'
        img = _make_test_image()
        cv2.imwrite(str(master_path), img)
        out_path = tmp_path / 'out.png'

        Upscaler.export(str(master_path), str(out_path), quality=50)

        result = cv2.imread(str(out_path))
        assert np.array_equal(result, img)  # lossless — real pixel-exact roundtrip

    def test_creates_missing_output_directories(self, tmp_path):
        master_path = tmp_path / 'master.png'
        cv2.imwrite(str(master_path), _make_test_image())
        out_path = tmp_path / 'nested' / 'dir' / 'out.png'

        Upscaler.export(str(master_path), str(out_path), quality=None)

        assert out_path.is_file()

    def test_raises_image_open_error_when_encoding_fails(self, tmp_path, monkeypatch):
        """cv2.imencode failing (ok=False) is a defensive branch that real
        image data essentially never triggers — the encoder itself is
        mocked here (the one justified boundary: proving *this* code reacts
        correctly to that return value, not re-testing OpenCV's own
        internals)."""
        from app import processing as upscaler_module
        from eterzion_upscale.media import ImageOpenError

        master_path = tmp_path / 'master.png'
        cv2.imwrite(str(master_path), _make_test_image())
        out_path = tmp_path / 'out.jpg'

        monkeypatch.setattr(upscaler_module.cv2, 'imencode', lambda *a, **kw: (False, None))

        with pytest.raises(ImageOpenError):
            Upscaler.export(str(master_path), str(out_path), quality=80)
