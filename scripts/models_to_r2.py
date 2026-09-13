"""Espelha no CDN privado do Studio os arquivos de modelo que o app baixa.

Destino: `r2:eterzion-studio/models/<arquivo>`, servido por
`cdn.eterzion.com/studio/models/` só com a assinatura que o servidor de licenças
emite. O app tenta o espelho antes da fonte original (app/cdn.py).

Cada arquivo é baixado da FONTE ORIGINAL -- nunca do próprio espelho -- e só é
enviado se o SHA-256 bater com o fixado no código. O app confere o mesmo hash
ao baixar, então um arquivo errado no espelho seria recusado lá também; conferir
aqui evita publicá-lo.

A lista vem do próprio código do app (`MODELS`, `_YUNET_*`, `SPEECH_WEIGHTS`,
`_LAVASR_*` em api/eterzion_upscale/processing.py), lida pela AST: importar o
módulo exigiria torch, cv2 e spandrel só para ler constantes. O teste
test_models_to_r2.py confere que esta leitura bate com os valores de verdade.

Uso:
    python scripts/models_to_r2.py --listar       # só mostra o que seria enviado
    RCLONE=/caminho/rclone python scripts/models_to_r2.py
Remote `r2:` configurado por variáveis RCLONE_CONFIG_R2_* (ver models-to-r2.yml).

Substitui scripts/mirror_models.py, que importava módulos que não existem mais
e publicava num repositório do GitHub.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / 'api' / 'eterzion_upscale' / 'processing.py'
DESTINO = 'r2:eterzion-studio/models'


def _constantes(caminho: Path = FONTE) -> dict:
    """Atribuições de nível de módulo que são literais (ou f-strings só de
    literais já lidos). O que não for, fica de fora."""
    arvore = ast.parse(caminho.read_text(encoding='utf-8'))
    valores: dict = {}
    for no in arvore.body:
        alvo, valor = None, None
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            alvo, valor = no.targets[0].id, no.value
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name) and no.value is not None:
            alvo, valor = no.target.id, no.value
        if alvo is None:
            continue
        if isinstance(valor, ast.JoinedStr):
            partes = []
            for parte in valor.values:
                if isinstance(parte, ast.Constant):
                    partes.append(str(parte.value))
                elif (isinstance(parte, ast.FormattedValue) and isinstance(parte.value, ast.Name)
                      and parte.value.id in valores):
                    partes.append(str(valores[parte.value.id]))
                else:
                    partes = None
                    break
            if partes is not None:
                valores[alvo] = ''.join(partes)
            continue
        try:
            valores[alvo] = ast.literal_eval(valor)
        except ValueError:
            pass
    return valores


def manifesto(caminho: Path = FONTE) -> list[tuple[str, str, str]]:
    """(arquivo, sha256, url_de_origem) de tudo que o app baixa sob demanda."""
    c = _constantes(caminho)
    itens = []
    for entrada in c['MODELS'].values():
        for url, digest in zip(entrada['urls'], entrada['sha256']):
            itens.append((os.path.basename(urlparse(url).path), digest, url))
    itens.append(('face_detection_yunet_2023mar.onnx', c['_YUNET_SHA256'], c['_YUNET_URL']))
    for nome, digest in c['SPEECH_WEIGHTS'].items():
        itens.append((nome, digest, c['_LAVASR_ORIGIN'] + nome))
    nomes = [i[0] for i in itens]
    duplicados = {n for n in nomes if nomes.count(n) > 1}
    if duplicados:
        # O espelho é plano (models/<arquivo>): dois arquivos com o mesmo nome
        # se sobrescreveriam.
        raise SystemExit(f'nomes repetidos no manifesto: {sorted(duplicados)}')
    return itens


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n', 1)[0])
    parser.add_argument('--listar', action='store_true', help='só lista, não baixa nem envia')
    args = parser.parse_args()

    itens = manifesto()
    if args.listar:
        for nome, digest, url in itens:
            print(f'{nome}  {digest[:12]}  {url}')
        return 0

    rclone = os.environ.get('RCLONE', 'rclone')
    with tempfile.TemporaryDirectory() as tmp:
        for nome, digest, url in itens:
            local = Path(tmp) / nome
            req = urllib.request.Request(url, headers={'User-Agent': 'eterzion-models-to-r2'})
            with urllib.request.urlopen(req, timeout=300) as resp, open(local, 'wb') as f:  # noqa: S310
                while bloco := resp.read(1 << 20):
                    f.write(bloco)
            obtido = _sha256(local)
            if obtido != digest:
                print(f'ERRO {nome}: SHA-256 {obtido} != fixado {digest}; nada enviado.', file=sys.stderr)
                return 1
            subprocess.run([rclone, 'copyto', str(local), f'{DESTINO}/{nome}', '--retries', '3'], check=True)
            print(f'ok  {nome}  {local.stat().st_size} bytes  {digest[:12]}')
            local.unlink()
    subprocess.run([rclone, 'lsl', DESTINO], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
