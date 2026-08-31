"""T023 — real benchmark for FR-087 to FR-093: picks the single implementation
per {photo, anime_image} content type that T024 locks into profile_resolver.py.

Methodology (research.md R3): classic SR degrade-and-restore protocol. For each
candidate model already in eterzion_upscale.core.MODELS under the relevant
category, a synthetic high-resolution reference image is downscaled by that
model's native scale, the model restores it, and the restoration is compared
against the original at the same resolution:
  - Fidelity guard-rail (FR-089): PSNR/SSIM via scikit-image — never disqualifies
    a candidate on its own (a soft-but-blurry upscale can "win" PSNR while
    looking worse), but a candidate that clearly falls apart here is flagged.
  - Perceptual metric, primary (FR-088): LPIPS (AlexNet backbone) — dev-only
    tool per research.md R3, never shipped to the product; not installed as a
    runtime dependency of eterzion_upscale itself.

Honesty notes, disclosed rather than hidden:
  - Reference images are procedurally generated (gradients/noise for "photo",
    flat color blocks + hard edges for "anime_image"), not real photographs —
    no licensed/public-domain photo dataset was fetched for this pass. They
    exercise the same signal categories content_type.py's own classifier keys
    on (continuous tone + noise vs. flat shading + sharp edges), but a result
    here is a same-machine, small-sample comparison, not a claim about
    real-world photo/anime performance in general.
  - FR-087's "human visual pass" cannot be performed by this script — it has
    no human reviewer. That step is left for a person to do before treating
    this pass as final; see the caveat this script writes into the results doc.

Run: python scripts/benchmark_profiles.py
Writes: docs/models/BENCHMARK_RESULTS.md
"""
from __future__ import annotations

import time

import cv2
import lpips
import numpy as np
import torch
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

from eterzion_upscale.core import MODELS, load_model

HR_SIZE = 96  # keep CPU runtime bounded; still enough structure to differentiate models
CATEGORIES = {'photo': 'Fotos', 'anime_image': 'Anime'}

_lpips_model = lpips.LPIPS(net='alex')


def _make_photo_reference(size: int) -> np.ndarray:
    """Continuous-tone gradient + sensor-like noise + soft blobs — the same
    signal shape content_type.classify_image() associates with 'photo'
    (low saturation blocks, dense edges, no flat-shaded regions)."""
    rng = np.random.default_rng(42)
    y, x = np.mgrid[0:size, 0:size]
    base = (0.5 + 0.5 * np.sin(x / 11.0) * np.cos(y / 17.0)) * 180 + 40
    img = np.stack([base, base * 0.85 + 10, base * 0.7 + 25], axis=-1)
    for _ in range(6):
        cx, cy, r = rng.uniform(0, size, 2).tolist() + [rng.uniform(size * 0.1, size * 0.3)]
        yy, xx = np.mgrid[0:size, 0:size]
        mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2
        img[mask] += rng.uniform(-30, 30, 3)
    img += rng.normal(0, 8, img.shape)  # sensor noise
    return np.clip(img, 0, 255).astype(np.uint8)


def _make_anime_reference(size: int) -> np.ndarray:
    """Flat-shaded color blocks + hard linework — the signal shape
    classify_image() associates with 'anime_image' (high saturation, large
    dominant-color regions, sparse sharp edges)."""
    rng = np.random.default_rng(7)
    img = np.full((size, size, 3), 235, dtype=np.uint8)
    palette = [(60, 200, 230), (40, 90, 220), (200, 220, 60), (230, 130, 40), (180, 60, 200)]
    for _ in range(10):
        color = palette[rng.integers(0, len(palette))]
        shape = rng.integers(0, 2)
        pts = rng.integers(0, size, size=(4, 2)) if shape == 0 else None
        if shape == 0:
            cv2.fillConvexPoly(img, cv2.convexHull(pts), color)
        else:
            center = tuple(rng.integers(0, size, 2).tolist())
            radius = int(rng.uniform(size * 0.08, size * 0.22))
            cv2.circle(img, center, radius, color, -1)
    # crisp linework on top
    for _ in range(15):
        p1 = tuple(rng.integers(0, size, 2).tolist())
        p2 = tuple(rng.integers(0, size, 2).tolist())
        cv2.line(img, p1, p2, (20, 20, 20), 2)
    return img


def _lpips_distance(a: np.ndarray, b: np.ndarray) -> float:
    def to_tensor(img: np.ndarray) -> torch.Tensor:
        t = torch.from_numpy(img).float().permute(2, 0, 1).unsqueeze(0) / 127.5 - 1.0
        return t

    with torch.no_grad():
        return float(_lpips_model(to_tensor(a), to_tensor(b)).item())


def _evaluate_candidate(name: str, hr: np.ndarray) -> dict:
    entry = MODELS[name]
    scale = entry['scale']
    if scale < 2:
        return {'name': name, 'skipped': 'scale < 2, not a real upscale candidate for this benchmark'}
    lr = cv2.resize(hr, (HR_SIZE // scale, HR_SIZE // scale), interpolation=cv2.INTER_CUBIC)

    start = time.perf_counter()
    model = load_model(name, model_dir='models', device='cpu', half=False)
    restored, _mode = model.enhance(lr)
    elapsed = time.perf_counter() - start

    if restored.shape[:2] != hr.shape[:2]:
        restored = cv2.resize(restored, (hr.shape[1], hr.shape[0]), interpolation=cv2.INTER_LANCZOS4)

    return {
        'name': name,
        'scale': scale,
        'architecture': entry['architecture'],
        'psnr': float(psnr(hr, restored, data_range=255)),
        'ssim': float(ssim(hr, restored, channel_axis=2, data_range=255)),
        'lpips': _lpips_distance(hr, restored),  # lower is better (more perceptually similar)
        'seconds': elapsed,
    }


def run() -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}
    for content_type, category in CATEGORIES.items():
        hr = _make_photo_reference(HR_SIZE) if content_type == 'photo' else _make_anime_reference(HR_SIZE)
        candidates = [name for name, entry in MODELS.items() if entry['category'] == category]
        rows = []
        for name in candidates:
            print(f'[{content_type}] evaluating {name}...')
            rows.append(_evaluate_candidate(name, hr))
        rows = [r for r in rows if 'skipped' not in r]
        rows.sort(key=lambda r: r['lpips'])  # primary metric: perceptual, lower is better
        results[content_type] = rows
    return results


def write_report(results: dict[str, list[dict]], path: str) -> None:
    lines = [
        '# Resultados do Benchmark de Perfis (T023, FR-087 a FR-093)',
        '',
        '**Metodologia**: `scripts/benchmark_profiles.py` — protocolo clássico de SR '
        '(degrade-and-restore) sobre imagens de referência sintéticas geradas neste próprio '
        'script (ver docstring). Métrica principal: LPIPS (menor = mais parecido '
        'perceptualmente); guarda-corpo de fidelidade: PSNR/SSIM (maior = melhor).',
        '',
        '**Limitação disclosed**: referências são sintéticas, não fotos/arte reais — resultado '
        'é uma comparação relativa entre candidatos nesta máquina, não uma medição de qualidade '
        'no mundo real. O passe de avaliação visual humana exigido por FR-087 **não foi feito** '
        '— nenhum humano revisou os resultados; isso fica pendente antes de tratar esta escolha '
        'como definitiva sem revisão.',
        '',
    ]
    for content_type, rows in results.items():
        lines.append(f'## {content_type}')
        lines.append('')
        lines.append('| Modelo | Arquitetura | Escala | LPIPS ↓ | PSNR ↑ | SSIM ↑ | Tempo (s) |')
        lines.append('|---|---|---|---|---|---|---|')
        for r in rows:
            marker = ' **(vencedor)**' if r is rows[0] else ''
            lines.append(
                f"| {r['name']}{marker} | {r['architecture']} | {r['scale']}x | "
                f"{r['lpips']:.4f} | {r['psnr']:.2f} | {r['ssim']:.4f} | {r['seconds']:.2f} |"
            )
        lines.append('')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    report = run()
    write_report(report, 'docs/models/BENCHMARK_RESULTS.md')
    for content_type, rows in report.items():
        winner = rows[0]['name'] if rows else None
        print(f'{content_type}: winner = {winner}')
