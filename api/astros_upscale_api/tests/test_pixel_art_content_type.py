"""pixel_art is the content type that resolves no model.

Not "the model we picked for pixel art" — the finding that none belongs there.
Measured over 40 of the owner's real 32x32 icons, all four approved models
shifted the shape by 18 to 24 mean luma levels and invented colour on a
black-and-white source, while repeating pixels shifted it by none.

The rule has to hold at every scale, which is what separates this from the
existing Original mode: Original skips the model because it is not enlarging,
pixel_art skips it even when it is.
"""
from __future__ import annotations

from app import licensing
from app.schemas import ContentType


def test_pixel_art_is_a_real_content_type():
    assert 'pixel_art' in ContentType.__args__


def test_it_is_treated_as_image_content():
    assert 'pixel_art' in licensing._IMAGE_VIDEO_CONTENT_TYPES


def test_it_is_declared_model_free():
    assert licensing.MODEL_FREE_CONTENT_TYPES == {'pixel_art'}


def test_no_model_is_registered_for_it():
    """A model mapped here would quietly start running again."""
    assert 'pixel_art' not in licensing._CONTENT_TYPE_IMPLEMENTATIONS


def test_every_other_image_type_still_resolves_a_model():
    """The exception must stay an exception."""
    for content_type in ('photo', 'anime_image', 'real_video', 'anime_video'):
        assert content_type in licensing._CONTENT_TYPE_IMPLEMENTATIONS, content_type
        assert content_type not in licensing.MODEL_FREE_CONTENT_TYPES, content_type
