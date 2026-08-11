#!/usr/bin/env python
"""Mirror every registered model to a GitHub Release of your own repository.

Run this ONCE (and again whenever you add/change a model in astros_upscale.core.MODELS)
to publish your own copy of every model file as assets of a GitHub Release, and
generate ``models.json`` — the mirror map astros_upscale reads to prefer your
release over the original upstream URLs (falling back to upstream automatically
if your mirror is ever unreachable).

Requirements:
    - the GitHub CLI (`gh`) installed and authenticated: https://cli.github.com/
    - push access to the target repository

Usage:
    python scripts/mirror_models.py --repo your-user/astros_upscale
    python scripts/mirror_models.py --repo your-user/astros_upscale --tag models-v1
    python scripts/mirror_models.py --repo your-user/astros_upscale --only nomos-webphoto dejpg

This script does NOT commit the .pth files to git — they are uploaded as
release assets. Only the generated ``models.json`` (a small text file with
names, hashes, URLs and license attributions) should be committed.

Some community models are distributed under licenses that require attribution
and/or forbid commercial use (see the "license" field of each entry and
README.md's "Origem e licença dos modelos" section) — mirroring them here does
not change those terms, it only changes where the bytes are hosted.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from astros_upscale.core import MODELS  # noqa: E402
from astros_upscale.utils.download import load_file_from_url, sha256_of_file  # noqa: E402

# Author/license attribution for every model, confirmed against each model's
# original page (Real-ESRGAN's own LICENSE file, and the OpenModelDB API /
# Hugging Face model card for the community ones) at the time this script was
# written. Re-verify before relying on this for anything commercial.
ATTRIBUTIONS = {
    # realesrgan-x4/x2, realesr-general, realesrnet-x4, nomos2-dat2, realesrgan-anime
    # removed (T023/T024, benchmark-driven reduction to one implementation per
    # content type — docs/models/BENCHMARK_RESULTS.md); ultrasharp, animesharp,
    # nmkd-siax, nmkd-superscale removed earlier —
    # see docs/models/MODEL_LICENSES.md §1/§6 (rejected/unverified commercial licence).
    'nomos-webphoto': {'author': 'Philip Hofmann (Phhofm)', 'license': 'CC-BY-4.0',
                       'source': 'https://huggingface.co/Phips/4xNomosWebPhoto_RealPLKSR'},
    'hfa2k-span': {'author': 'Philip Hofmann (Phhofm)', 'license': 'CC-BY-4.0',
                  'source': 'https://huggingface.co/Phips/2xHFA2kSPAN'},
    'realesr-animevideo': {'author': 'Xintao Wang et al. (Real-ESRGAN)', 'license': 'BSD-3-Clause',
                           'source': 'https://github.com/xinntao/Real-ESRGAN'},
    'denoise': {'author': 'Philip Hofmann (Helaman)', 'license': 'CC-BY-4.0',
               'source': 'https://openmodeldb.info/models/1x-DeNoise-realplksr-otf'},
    'dejpg': {'author': 'Philip Hofmann (Helaman)', 'license': 'CC-BY-4.0',
             'source': 'https://openmodeldb.info/models/1x-DeJPG-realplksr-otf'},
    'hfa2k-avc': {'author': 'Philip Hofmann (Helaman)', 'license': 'CC-BY-4.0',
                 'source': 'https://openmodeldb.info/models/2x-HFA2kAVCCompact'},
}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print('$', ' '.join(cmd))
    return subprocess.run(cmd, check=True, **kwargs)


def ensure_release(repo: str, tag: str) -> None:
    exists = subprocess.run(['gh', 'release', 'view', tag, '--repo', repo],
                            capture_output=True).returncode == 0
    if not exists:
        run(['gh', 'release', 'create', tag, '--repo', repo,
            '--title', tag, '--notes', 'Espelho dos modelos usados pelo astros_upscale.'])


def mirror_models(repo: str, tag: str, only: list[str] | None, staging_dir: str) -> dict:
    names = only if only else sorted(MODELS)
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        raise SystemExit(f'Modelo(s) desconhecido(s): {", ".join(unknown)}')

    entries = []
    for name in names:
        entry = MODELS[name]
        attribution = ATTRIBUTIONS.get(name, {})
        files = []
        for url, pinned_sha in zip(entry['urls'], entry['sha256']):
            filename = os.path.basename(urlparse(url).path)
            print(f'\n== {name} :: {filename} ==')
            local_path = load_file_from_url(url, model_dir=staging_dir, sha256=pinned_sha)
            digest = sha256_of_file(local_path)
            if pinned_sha and digest.lower() != pinned_sha.lower():
                raise SystemExit(f'{filename}: hash não bate com o registrado em MODELS ({pinned_sha}); abortando.')

            run(['gh', 'release', 'upload', tag, local_path, '--repo', repo, '--clobber'])
            mirror_url = f'https://github.com/{repo}/releases/download/{tag}/{filename}'
            files.append({'filename': filename, 'sha256': digest, 'original_url': url, 'mirror_url': mirror_url})

        entries.append({
            'name': name,
            'category': entry['category'],
            'scale': entry['scale'],
            'description': entry['description'],
            'author': attribution.get('author', 'desconhecido — verifique a fonte original'),
            'license': attribution.get('license', 'desconhecida — verifique a fonte original'),
            'source': attribution.get('source', entry['urls'][0]),
            'files': files,
        })
    return {'release_tag': tag, 'repo': repo, 'models': entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', required=True, help='Repositório GitHub de destino, ex.: seu-usuario/astros_upscale')
    parser.add_argument('--tag', default='models-v1', help='Nome do release de destino (padrão: models-v1)')
    parser.add_argument('--only', nargs='+', default=None, help='Espelhar só estes modelos (padrão: todos)')
    parser.add_argument('--output', default='models.json', help='Onde salvar o mapa gerado (padrão: models.json)')
    args = parser.parse_args()

    try:
        gh_ok = subprocess.run(['gh', '--version'], capture_output=True).returncode == 0
    except FileNotFoundError:
        gh_ok = False
    if not gh_ok:
        raise SystemExit('GitHub CLI (gh) não encontrado. Instale-o e rode "gh auth login" antes de continuar: '
                         'https://cli.github.com/')

    ensure_release(args.repo, args.tag)
    with tempfile.TemporaryDirectory() as staging_dir:
        manifest = mirror_models(args.repo, args.tag, args.only, staging_dir)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'\nPronto! {len(manifest["models"])} modelo(s) espelhados em {args.repo} (release {args.tag}).')
    print(f'Mapa salvo em {args.output} — commite este arquivo (NÃO os .pth) no repositório.')


if __name__ == '__main__':
    main()
