"""T019: no response, log field, or output filename may contain a model/
checkpoint/engine identifier, for every image scale x profile combination
(Constitution Principle V, FR-009/FR-011). Checks the actual known model
identifiers from eterzion_upscale.processing.MODELS/ALIASES against the real JSON
returned by POST /jobs* and GET /jobs/{id} — not a guess at what "looks like"
a model name.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import jobs_router
from eterzion_upscale.processing import ALIASES, MODELS

_KNOWN_MODEL_IDENTIFIERS = set(MODELS) | set(ALIASES)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


def _iter_string_values(payload):
    """Walk a JSON-decoded structure and yield every leaf string VALUE — never
    dict keys, never numbers/bools. Matching against values only (with exact
    equality, not substring) is what avoids false positives like the
    `adjustments.denoise` slider (an int, and even as a key merely SHARES a
    name with the unrelated `denoise` model in eterzion_upscale.processing.MODELS —
    a real leak means the model's own identifier appears as a value)."""
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_string_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_string_values(item)
    elif isinstance(payload, str):
        yield payload


def _assert_no_model_identifier_leaks(payload: dict) -> None:
    leaked = [v for v in _iter_string_values(payload) if v in _KNOWN_MODEL_IDENTIFIERS]
    assert not leaked, f'Identificador(es) de modelo vazado(s) na resposta: {leaked}\n{payload}'


@pytest.mark.parametrize('scale', ['2x', '4x'])
@pytest.mark.parametrize('profile', ['fast', 'balanced', 'quality'])
def test_create_job_response_never_leaks_a_model_identifier(client, real_input_file, scale, profile):
    res = client.post('/jobs/local', json={
        'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': scale, 'profile': profile, 'input_path': real_input_file,
        },
    })
    assert res.status_code == 200
    _assert_no_model_identifier_leaks(res.json())

    job_id = res.json()['id']
    got = client.get(f'/jobs/{job_id}')
    assert got.status_code == 200
    _assert_no_model_identifier_leaks(got.json())
