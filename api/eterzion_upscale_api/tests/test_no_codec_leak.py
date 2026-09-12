"""T086 (specs/007-video-editor-player) — SC-009 and Princípio V on the video
surface.

Mirrors the existing test_no_model_leak.py, which guards the same property for
models. The failure it prevents is not a crash: it is a response quietly
carrying an implementation name that the product has committed to keeping
internal, and that nobody notices until it is in a screenshot.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import media_handles
from app.main import app

FIXTURES = Path(__file__).resolve().parent / 'fixtures'

# Encoder, decoder and library names that must never reach a client. Matched
# case-insensitively as substrings, so 'H264_NVENC' and 'libvpx-vp9' are both
# caught.
FORBIDDEN = (
    'nvenc', 'qsv', 'amf', 'vaapi', 'videotoolbox',
    'libvpx', 'libaom', 'libsvtav1', 'librav1e',
    'x264', 'x265', 'libx264', 'libx265',
    # Filter names, including the two the graph switched to when `eq` and
    # `hqdn3d` turned out to be GPL — a rename must not quietly drop a name
    # from this list.
    'hqdn3d', 'fftdnoiz', 'lutyuv', 'unsharp', 'gblur', 'transpose', 'ffmpeg',
)


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()


@pytest.fixture
def handle_id(client):
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    return client.post('/media/handles', json={'path': str(source)}).json()['handle_id']


# O handle_id e' `vh_` + `secrets.token_urlsafe(32)`: 43 caracteres sorteados
# que voltam em toda resposta sobre o handle. Como a busca abaixo e' por
# substring e sem caixa, uma sequencia aleatoria como `...CpMduhQQSvnn...`
# contem `qsv` -- e o teste reprovou um PR por isso em 2026-09-12, sem
# vazamento nenhum. Um identificador gerado nunca e' nome de implementacao,
# entao ele sai do texto antes da busca.
_HANDLE_ID = re.compile(r'vh_[A-Za-z0-9_-]+')


def _assert_clean(payload: object, where: str) -> None:
    flat = _HANDLE_ID.sub('vh_<id>', str(payload)).lower()
    leaked = [name for name in FORBIDDEN if name in flat]
    assert not leaked, f'{where} expõe nome de implementação: {leaked}'


def test_um_handle_id_sorteado_nao_e_vazamento():
    """O id exato que reprovou o PR #83 -- tem `QSv` no meio."""
    _assert_clean({'handle_id': 'vh_gBN8duMVkUMQxsTnl-wdz9X-CpMduhQQSvnn6ABA_XQ'}, 'id sorteado')


def test_o_detector_continua_pegando_vazamento_de_verdade():
    """Ignorar o id nao pode cegar a busca no resto da resposta."""
    with pytest.raises(AssertionError, match='qsv'):
        _assert_clean({'handle_id': 'vh_abc', 'encoder': 'h264_qsv'}, 'vazamento real')


def test_export_options_names_no_encoder(client):
    """The response says a container is unavailable. Which encoder was missing
    is not the person's problem and not their decision."""
    response = client.get('/video/export-options')
    assert response.status_code == 200
    _assert_clean(response.json(), 'GET /video/export-options')


def test_handle_metadata_names_no_encoder(client, handle_id):
    _assert_clean(client.get(f'/media/handles/{handle_id}').json(), 'GET /media/handles/{id}')


def test_a_refusal_names_no_encoder(client, handle_id):
    """Error paths leak more often than success paths, because they are written
    while debugging and read by nobody afterwards."""
    response = client.post(
        '/video/edit-jobs',
        json={'handle_id': handle_id, 'edits': {}, 'container': 'webm', 'profile': 'fast'},
    )
    if response.status_code >= 400:
        _assert_clean(response.json(), 'POST /video/edit-jobs (recusa)')


def _without_prose(node: object) -> object:
    """Strip `description` and `summary` from a schema.

    Those carry route docstrings, which are written for whoever maintains the
    API and legitimately name filters and binaries — explaining that unsharp is
    a 5x5 convolution is the kind of thing a docstring is for. Princípio V
    governs what a PERSON USING THE PRODUCT sees: screens, error messages,
    output filenames. Developer documentation is not one of those surfaces, and
    a test that conflated the two would push explanation out of the code to
    satisfy a rule that was never about it.

    What remains — field names, enum values, defaults — does reach clients, and
    is what this checks.
    """
    if isinstance(node, dict):
        return {k: _without_prose(v) for k, v in node.items()
                if k not in ('description', 'summary')}
    if isinstance(node, list):
        return [_without_prose(item) for item in node]
    return node


def test_the_openapi_contract_names_no_encoder(client):
    """Covers every route at once, including any added later: an encoder name
    pinned into a Literal or a default would surface here even if no test ever
    called that route."""
    _assert_clean(_without_prose(client.get('/openapi.json').json()), 'o contrato OpenAPI')
