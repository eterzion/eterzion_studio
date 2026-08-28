from __future__ import annotations

import json
import urllib.request

import pytest

from app import licensing, security
from astros_upscale import __version__


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b'{}'


@pytest.fixture
def captured_requests(monkeypatch):
    requests = []

    def _urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response()

    monkeypatch.setattr(urllib.request, 'urlopen', _urlopen)
    return requests


def _assert_common_headers(request: urllib.request.Request) -> None:
    assert request.get_header('Accept') == 'application/json'
    assert request.get_header('User-agent') == f'EterzionStudio/{__version__}'


def test_license_gate_get_sends_explicit_client_headers(captured_requests):
    assert licensing._http_get('https://license.eterzion.com/health') == {}

    request, timeout = captured_requests.pop()
    assert request.full_url == 'https://license.eterzion.com/health'
    assert timeout == 5.0
    _assert_common_headers(request)


def test_security_get_sends_explicit_client_headers(captured_requests):
    assert security._http_get('https://license.eterzion.com/public-key') == {}

    request, timeout = captured_requests.pop()
    assert request.full_url == 'https://license.eterzion.com/public-key'
    assert timeout == 15
    _assert_common_headers(request)


def test_activation_sends_json_and_explicit_client_headers(captured_requests):
    assert security._http_post('https://license.eterzion.com/activations', {'license_id': 'lic_1'}) == {}

    request, timeout = captured_requests.pop()
    assert request.get_method() == 'POST'
    assert json.loads(request.data.decode('utf-8')) == {'license_id': 'lic_1'}
    assert request.get_header('Content-type') == 'application/json'
    assert timeout == 15
    _assert_common_headers(request)


def test_release_sends_json_and_explicit_client_headers(captured_requests):
    assert security.release('https://license.eterzion.com', 'lic_1', 'install_1') == {}

    request, timeout = captured_requests.pop()
    assert request.get_method() == 'DELETE'
    assert request.full_url == 'https://license.eterzion.com/activations/install_1?license_id=lic_1'
    assert request.get_header('Content-type') == 'application/json'
    assert timeout == 15
    _assert_common_headers(request)
