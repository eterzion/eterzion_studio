"""The real material, not a stand-in for it.

Every bug in the image pipeline found this week was invisible to synthetic
fixtures, because the fixtures differed from the real files in exactly the
property that mattered:

  - the chroma guard skipped any 4-channel image, so it never ran once on
    these icons — every test image I had written was 3-channel
  - sharpening reintroduced the colour the guard had removed, which a
    perfectly neutral test image cannot show (with R==G==B the per-channel
    filter moves all three identically)

These icons are 10x34 to 36x18 RGBA with the antialiasing carried in alpha and
a maximum chroma of 3 across the visible pixels — they are black and white.
Anything coloured in the output is invented. The set is small on purpose: five
files that between them cover the shapes, aspect ratios and alpha profiles the
pipeline has to survive.
"""
from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from app.processing import Upscaler

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'icones')
ICONS = sorted(f for f in os.listdir(FIXTURES) if f.endswith(('.webp', '.png')))


def load(name):
    return cv2.imread(os.path.join(FIXTURES, name), cv2.IMREAD_UNCHANGED)


def visible(img):
    return img[..., 3] > 128 if img.shape[2] == 4 else np.ones(img.shape[:2], bool)


def chroma(img):
    rgb = img[..., :3].astype(int)
    return rgb.max(axis=2) - rgb.min(axis=2)


@pytest.mark.parametrize('name', ICONS)
class TestTheChromaGuardOnRealIcons:
    def test_it_runs_at_all_on_a_transparent_icon(self, name):
        """The bug that hid for a whole session: 4-channel images were dropped
        on the first line, so none of this material was ever corrected."""
        icon = load(name)
        assert icon.shape[2] == 4, 'a fixture deixou de ser RGBA'
        polluted = cv2.resize(icon, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        seen = visible(polluted)
        assert seen.any()
        polluted[..., :3][seen] = (40, 200, 180)  # invencao grosseira
        out = Upscaler._suppress_invented_chroma(polluted, icon)
        assert chroma(out)[visible(out)].max() <= 12

    def test_alpha_comes_out_byte_identical(self, name):
        icon = load(name)
        doubled = cv2.resize(icon, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        out = Upscaler._suppress_invented_chroma(doubled, icon)
        assert np.array_equal(out[..., 3], doubled[..., 3])


@pytest.mark.parametrize('name', ICONS)
class TestSharpeningOnRealIcons:
    def test_it_does_not_reintroduce_colour(self, name):
        """These are black-and-white icons: sharpening must not tint them."""
        icon = load(name)
        doubled = cv2.resize(icon, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        before = chroma(doubled)[visible(doubled)].max()
        out = Upscaler._sharpen(doubled, 100)
        assert chroma(out)[visible(out)].max() <= before + 2

    def test_alpha_survives_sharpening(self, name):
        icon = load(name)
        doubled = cv2.resize(icon, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        out = Upscaler._sharpen(doubled, 100)
        assert np.array_equal(out[..., 3], doubled[..., 3])


@pytest.mark.parametrize('name', ICONS)
def test_pixel_art_enlargement_invents_no_colour(name, tmp_path):
    """End to end through the no-model path: the palette must not grow."""
    icon = load(name)
    source = tmp_path / name
    cv2.imwrite(str(source), icon)
    master = tmp_path / 'out.png'
    Upscaler.process_without_model(
        str(source), str(master), str(tmp_path),
        resize=(icon.shape[1] * 4, icon.shape[0] * 4),
    )
    out = cv2.imread(str(master), cv2.IMREAD_UNCHANGED)
    src_colours = {tuple(c) for c in np.unique(icon[..., :3].reshape(-1, 3), axis=0)}
    out_colours = {tuple(c) for c in np.unique(out[..., :3].reshape(-1, 3), axis=0)}
    assert out_colours <= src_colours, f'cores novas: {sorted(out_colours - src_colours)[:5]}'
