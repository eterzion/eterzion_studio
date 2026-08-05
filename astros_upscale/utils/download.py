"""URL-download helper built on torch.hub, with SHA256 validation, atomic writes
and mirror-with-fallback support."""
from __future__ import annotations

import hashlib
import logging
import os
from urllib.parse import urlparse

from torch.hub import download_url_to_file

logger = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    """Raised when a model download fails or its checksum does not match."""


def sha256_of_file(path: str, chunk_size: int = 1 << 20) -> str:
    """Compute the SHA256 hex digest of a file, reading in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_file_from_url(url: str,
                       model_dir: str = 'models',
                       progress: bool = True,
                       file_name: str | None = None,
                       sha256: str | None = None) -> str:
    """Download a file from a URL into ``model_dir`` (skipping if already cached).

    The download goes to a ``.partial`` temporary file and is renamed only after
    completing (and, when ``sha256`` is given, after the checksum matches), so an
    interrupted download never leaves a corrupted file behind. When ``sha256`` is
    None, the computed hash is logged so it can be pinned later.

    Returns:
        str: The absolute path to the downloaded file.

    Raises:
        DownloadError: When the download fails or the checksum does not match.
    """
    os.makedirs(model_dir, exist_ok=True)
    filename = file_name if file_name is not None else os.path.basename(urlparse(url).path)
    cached_file = os.path.abspath(os.path.join(model_dir, filename))
    if os.path.exists(cached_file):
        return cached_file

    partial_file = cached_file + '.partial'
    print(f'Baixando "{url}"\n  -> {cached_file}')
    try:
        download_url_to_file(url, partial_file, hash_prefix=None, progress=progress)
    except Exception as error:
        if os.path.exists(partial_file):
            os.remove(partial_file)
        raise DownloadError(f'Falha ao baixar o modelo de {url} ({error}). '
                            'Verifique sua conexão ou se a URL ainda está no ar.') from error

    digest = sha256_of_file(partial_file)
    if sha256 is None:
        logger.warning('no pinned sha256 for %s; computed sha256=%s', filename, digest)
    elif digest.lower() != sha256.lower():
        os.remove(partial_file)
        raise DownloadError(f'Checksum SHA256 inválido para {filename} (baixado de {url}): '
                            f'esperado {sha256}, obtido {digest}. O arquivo foi descartado.')
    os.replace(partial_file, cached_file)
    return cached_file


def download_with_fallback(urls: list[str],
                          model_dir: str = 'models',
                          progress: bool = True,
                          file_name: str | None = None,
                          sha256: str | None = None) -> str:
    """Try each URL in ``urls`` in order (e.g. [mirror_url, original_url]) until one
    succeeds. All candidates share the same cached filename, so once any one of
    them has been downloaded successfully the others are never touched again.

    Raises:
        DownloadError: aggregating every failure, only if ALL urls failed.
    """
    filename = file_name if file_name is not None else os.path.basename(urlparse(urls[0]).path)
    cached_file = os.path.abspath(os.path.join(model_dir, filename))
    if os.path.exists(cached_file):
        return cached_file

    errors = []
    for url in urls:
        try:
            return load_file_from_url(url, model_dir=model_dir, progress=progress, file_name=filename, sha256=sha256)
        except DownloadError as error:
            logger.warning('source failed (%s); trying next mirror if any', url)
            errors.append(str(error))
    raise DownloadError('Todas as fontes de download falharam para ' + filename + ':\n' +
                        '\n'.join(f'  - {e}' for e in errors))


def local_file_status(url: str, model_dir: str = 'models', file_name: str | None = None) -> tuple[bool, int]:
    """Return (downloaded, size_in_bytes) for the file a URL would be cached as, without downloading."""
    filename = file_name if file_name is not None else os.path.basename(urlparse(url).path)
    path = os.path.join(model_dir, filename)
    if os.path.isfile(path):
        return True, os.path.getsize(path)
    return False, 0
