"""T034 (eterzion_licensing_service half): static audit of every payload this
service accepts or produces in the activation/webhook path — a content-
carrying field here would be a permanent leak channel, not a one-off
request. FR-062: no field derived from processed media, ever. The dynamic
half (what license_gate.py in eterzion_upscale_api actually sends over the
wire) lives in that project's own tests/test_license_gate_no_leakage.py —
a different Python package, not importable from here."""
from __future__ import annotations

import dataclasses

_SUSPICIOUS_SUBSTRINGS = (
    'file', 'path', 'content', 'hash', 'sha256', 'md5', 'bytes', 'media',
    'input_path', 'output_path', 'source', 'checksum',
)


def _assert_no_suspicious_field(fields: set[str], context: str) -> None:
    for field in fields:
        for term in _SUSPICIOUS_SUBSTRINGS:
            assert term not in field.lower(), f'{context}: field {field!r} looks content-derived'


def test_activate_request_has_no_media_derived_field():
    from app.routes import ActivateRequest

    fields = set(ActivateRequest.model_fields.keys())
    assert fields == {'license_id', 'install_id', 'signing_public_key_b64', 'encryption_public_key_b64'}
    _assert_no_suspicious_field(fields, 'ActivateRequest')


def test_payment_event_has_no_media_derived_field():
    from app.payments import PaymentEvent

    fields = {f.name for f in dataclasses.fields(PaymentEvent)}
    assert fields == {'provider', 'reference', 'email', 'amount', 'currency'}
    _assert_no_suspicious_field(fields, 'PaymentEvent')


def test_license_row_has_no_media_derived_field():
    from app.licensing import License

    fields = {f.name for f in dataclasses.fields(License)}
    assert fields == {'id', 'email', 'status', 'activation_limit', 'payment_provider', 'payment_reference'}
    _assert_no_suspicious_field(fields, 'License')


def test_activations_status_response_has_no_media_derived_field(client, license_factory, install_keys):
    """The real, live response body from GET /activations/{id}/status — not
    just the schema, the actual bytes a client would receive."""
    lic = license_factory()
    client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
    res = client.get('/activations/install-1/status')
    assert res.status_code == 200
    _assert_no_suspicious_field(set(res.json().keys()), 'GET /activations/{id}/status response')


def test_authorization_request_has_no_media_derived_field():
    from app.routes import AuthorizeRequest

    fields = set(AuthorizeRequest.model_fields.keys())
    _assert_no_suspicious_field(fields, 'AuthorizeRequest')
