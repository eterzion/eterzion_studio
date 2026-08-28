"""T016 (specs/007-video-editor-player) — the two properties contracts/api.md
promises about every video route, asserted against the live app.

This is what SC-007 measures, and it is deliberately written against the app's
own OpenAPI schema rather than against a list of routes maintained by hand: a
route added later inherits the check without anyone remembering to extend it.

  1. No route accepts a filesystem path, except POST /media/handles — the
     bounded exception in constitution v3.0.0. Its third condition ("no other
     route may accept a path") is exactly what test_only_one_route_accepts_a_path
     enforces, and it is the condition most likely to erode as the surface grows.
  2. No route accepts a codec, encoder, preset, CRF or pixel format
     (Princípio V: the API accepts intent, never implementation).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import media_handles

FIXTURES = Path(__file__).resolve().parent / 'fixtures'

# Field names that would mean the client is choosing an implementation, or
# naming a location on disk. Matched as substrings so `video_codec`,
# `input_path` and `output_path` are all caught.
IMPLEMENTATION_FIELDS = ('codec', 'encoder', 'preset', 'crf', 'pix_fmt', 'pixel_format', 'bitrate')
PATH_FIELDS = ('path',)

# Campos cujo nome casa com a heurística acima e que **não** são escolha de
# implementação. A lista é nominal e curta de propósito: afrouxar o padrão —
# deixar de casar "preset", por exemplo — esconderia `encoding_preset` junto, e
# é justamente ele que o Princípio V proíbe. Cada entrada precisa de uma razão
# escrita.
#
# `preset_id` (specs/008, FR-014) identifica um **preset de configurações
# salvas** — "Discord 8 MB", uma coisa que a pessoa nomeia e guarda. Não é o
# `-preset` de encoder, não vira argumento de FFmpeg, e é o backend que resolve
# o que ele significa. Um identificador opaco que o cliente recebeu da própria
# API não fixa implementação nenhuma.
ALLOWED_IMPLEMENTATION_LOOKALIKES = frozenset({'preset_id'})

# Routes that predate this feature. They are outside its scope and are not made
# non-compliant by it — POST /jobs/local in particular accepts a local path and
# is explicitly NOT covered by the v3.0.0 exception (it is not a registration
# route and returns no identifier). Listed here so this test constrains the new
# surface without silently blessing the old one.
PRE_EXISTING_PATH_ROUTES = {
    ('/jobs', 'post'),
    ('/jobs/local', 'post'),
    ('/jobs/{job_id}/export', 'post'),
    ('/preview/denoise', 'post'),
    ('/content-type/detect', 'post'),
    ('/jobs/detect-content-type', 'post'),
}

REGISTRATION_ROUTE = ('/media/handles', 'post')


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()


def _request_field_names(schema: dict, body_schema: dict | None, seen=None) -> set[str]:
    """Every property name reachable in a request body, following $ref and
    nesting — a forbidden field one level down is still a forbidden field."""
    if body_schema is None:
        return set()
    seen = seen if seen is not None else set()
    names: set[str] = set()

    if '$ref' in body_schema:
        ref = body_schema['$ref'].rsplit('/', 1)[-1]
        if ref in seen:
            return names
        seen.add(ref)
        return _request_field_names(schema, schema.get('components', {}).get('schemas', {}).get(ref), seen)

    for key, value in (body_schema.get('properties') or {}).items():
        names.add(key)
        names |= _request_field_names(schema, value, seen)
    for combinator in ('anyOf', 'allOf', 'oneOf'):
        for entry in body_schema.get(combinator, []):
            names |= _request_field_names(schema, entry, seen)
    if 'items' in body_schema:
        names |= _request_field_names(schema, body_schema['items'], seen)
    return names


def _routes_with_bodies(client):
    schema = client.get('/openapi.json').json()
    for path, methods in schema['paths'].items():
        for method, operation in methods.items():
            body = operation.get('requestBody')
            if not body:
                continue
            content = (body.get('content') or {}).get('application/json')
            if not content:
                continue
            yield path, method, _request_field_names(schema, content.get('schema'))


def test_no_route_accepts_an_implementation_choice(client):
    """Princípio V. A `codec` field anywhere would let the interface — or
    anything calling the API directly — pin an implementation the backend is
    supposed to own."""
    offenders = {
        # Tupla, e não lista: o conjunto precisa de elementos hasháveis. A versão
        # com `sorted(...)` levantava TypeError exatamente quando havia um
        # infrator — o único momento em que a mensagem importava.
        (path, method, tuple(sorted(_suspects(fields))))
        for path, method, fields in _routes_with_bodies(client)
        if _suspects(fields)
    }
    assert not offenders, f'rotas aceitando escolha de implementação: {offenders}'


def _suspects(fields) -> set[str]:
    return {
        f for f in fields
        if f.lower() not in ALLOWED_IMPLEMENTATION_LOOKALIKES
        and any(bad in f.lower() for bad in IMPLEMENTATION_FIELDS)
    }


def test_a_lista_de_excecoes_nao_cobre_o_que_o_principio_proibe():
    """A guarda da guarda.

    Uma lista de exceções é o lugar onde um princípio morre em silêncio: basta
    alguém acrescentar `encoding_preset` a ela para o teste acima continuar
    verde enquanto a API passa a aceitar escolha de encoder. Estes nomes nunca
    podem ficar isentos.
    """
    proibidos = {'preset', 'encoding_preset', 'video_codec', 'audio_codec',
                 'encoder', 'encoder_preference', 'crf', 'pix_fmt'}
    assert not (ALLOWED_IMPLEMENTATION_LOOKALIKES & proibidos)


def test_only_one_route_accepts_a_path(client):
    """Third condition of the v3.0.0 bounded exception, and the one that erodes
    first as a surface grows: it is always tempting to let just one more route
    take a path."""
    accepting = {
        (path, method)
        for path, method, fields in _routes_with_bodies(client)
        if any(bad in f.lower() for f in fields for bad in PATH_FIELDS)
    }
    new_offenders = accepting - PRE_EXISTING_PATH_ROUTES - {REGISTRATION_ROUTE}
    assert not new_offenders, f'rotas novas aceitando caminho: {new_offenders}'


def test_the_registration_route_does_accept_a_path(client):
    """The inverse guard. If this ever stops being true the exception has been
    refactored away and the test above became vacuous."""
    accepting = {
        (path, method)
        for path, method, fields in _routes_with_bodies(client)
        if any(bad in f.lower() for f in fields for bad in PATH_FIELDS)
    }
    assert REGISTRATION_ROUTE in accepting


@pytest.mark.parametrize('extra_field', ['codec', 'preset', 'crf', 'pix_fmt', 'output_path'])
def test_unknown_fields_are_rejected_not_ignored(client, extra_field):
    """Quickstart scenario 8, from the outside. extra='forbid' turns an unknown
    key into a 422 rather than one that is silently dropped — which is the
    difference between a caller learning its request was wrong and a caller
    believing it got what it asked for."""
    response = client.post('/media/handles', json={'path': 'x', extra_field: 'libx264'})
    assert response.status_code == 422


def test_handle_response_never_carries_a_path(client):
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')

    response = client.post('/media/handles', json={'path': str(source)})
    assert response.status_code == 201
    body = response.json()

    # Checked against every value, not against a field allowlist: a field added
    # later would otherwise leak the path silently.
    flat = str(body)
    assert str(source) not in flat
    assert str(source.parent) not in flat
    assert body['display_name'] == 'curto.mp4'


def test_registering_a_missing_file_is_refused(client):
    response = client.post('/media/handles', json={'path': 'C:/nao/existe.mp4'})
    assert response.status_code == 404


def test_export_options_never_name_an_encoder(client):
    """Princípio V applies to this surface like any other: a person is told the
    container is unavailable, never which encoder was missing."""
    response = client.get('/video/export-options')
    assert response.status_code == 200
    body = response.json()
    flat = str(body).lower()
    for name in ('nvenc', 'qsv', 'amf', 'libvpx', 'libaom', 'x264', 'x265'):
        assert name not in flat, f'nome de encoder vazou na resposta: {name}'
    assert body['profiles'] == ['fast', 'balanced', 'quality']
    assert body['ceilings']['max_duration_seconds'] > 0
