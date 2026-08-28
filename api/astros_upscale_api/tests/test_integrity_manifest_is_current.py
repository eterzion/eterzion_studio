"""The manifest checked into the repo must match the files checked into the repo.

test_integrity.py covers the *mechanism* thoroughly, and does it against a
scratch manifest in tmp_path — on purpose, so those tests never depend on the
state of the real integrity_manifest.json. That is the right call for testing
the mechanism, and it is also precisely the gap this file closes: nothing was
checking the real manifest, so the mechanism stayed correct while its data went
stale.

That is not hypothetical. jobs.py and processing.py were changed during feature
007 without regenerating the manifest, and the result was that every image job
failed on a developer machine — the worker refused to start, and the error that
surfaced was "O worker isolado não respondeu a tempo ao iniciar", a startup
timeout that says nothing about integrity. The real reason was only visible by
running the worker module by hand. A stale manifest is a total outage wearing
the mask of a flaky timeout.

The failure mode this guards against is a legitimate edit, not an attack: an
attacker who edits a protected file also regenerates the manifest, and this
test passes just the same. What it catches is us forgetting a documented step,
which is the only way this mechanism has ever actually broken.
"""
from __future__ import annotations

from app import security


def test_manifest_matches_the_protected_files_on_disk():
    ok, problems = security.verify_integrity()
    assert ok, (
        'O manifesto de integridade está defasado em relação aos arquivos '
        'protegidos. O worker isolado vai RECUSAR INICIAR, e o sintoma será um '
        'timeout que não menciona integridade.\n\n'
        'Corrija regenerando o manifesto (passo manual por design — '
        'security.py o compara a um lockfile):\n'
        '    cd api/astros_upscale_api && python -m app.security\n\n'
        f'Problemas encontrados: {problems}'
    )


def test_every_protected_file_is_listed_in_the_manifest():
    """A newly protected module that nobody added to the manifest fails closed
    at worker startup. Catching it here costs a second; catching it there costs
    an afternoon of reading the wrong error message."""
    manifest = security._load_manifest()
    assert manifest is not None, 'integrity_manifest.json ausente ou ilegível'

    on_disk = security.compute_hashes()
    missing = sorted(set(on_disk) - set(manifest))
    assert not missing, (
        f'Arquivos protegidos fora do manifesto: {missing}. '
        'Rode `python -m app.security` a partir de api/astros_upscale_api.'
    )
