"""Onde um resultado e' gravado, com que nome, e como -- o mesmo para todos os
modos (Imagem, Video, Audio, Compressao).

Havia uma versao desta logica por modo, e cada uma errava num ponto diferente:
a Imagem gravava direto no destino (uma falha no meio de um "sobrescrever"
estragava o arquivo que existia), o Video decidia o destino na hora de rodar o
job (quando ja' nao da' para perguntar nada), e a Compressao gravava no
temporario do sistema e movia depois (em outro disco, o `move` vira copia e a
troca deixa de ser atomica).

**As regras sao as da Imagem**, por decisao de produto:

- a pasta e' a escolhida; sem escolha, a do original;
- o nome e' o do original (ou o que a pessoa digitou), com a extensao do
  formato de saida;
- se o destino cair no proprio original, ganha o sufixo do modo
  (`foto_upscaled.png`) -- o original nunca e' sobrescrito, nem com
  "sobrescrever" (Principio XV);
- se o destino ja' existir: "renomear" usa o sufixo e depois `(1)`, `(2)`...;
  "perguntar" recusa antes do job, para a pergunta vir antes de processar;
  "sobrescrever" grava por cima -- com gravacao segura, entao o arquivo antigo
  so' e' substituido quando o novo esta' pronto.
"""
from __future__ import annotations

import os
import re
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Literal

Conflito = Literal['rename', 'overwrite', 'ask']

# O sufixo diz o que foi feito ao arquivo. Fixos em ingles, como os que ja'
# existiam: um nome de arquivo traduzido mudaria com o idioma do app.
SUFIXOS = {
    'image': '_upscaled',
    'video_upscale': '_upscaled',
    'video_edit': '_edited',
    'audio': '_enhanced',
    'compression': '_compressed',
}


class ConflitoDeDestino(Exception):
    """O destino ja' existe e a pessoa pediu para ser perguntada."""

    def __init__(self, caminho: str):
        super().__init__(f'Já existe um arquivo em {caminho}')
        self.caminho = caminho


def mesmo_arquivo(a: str, b: str) -> bool:
    """Os dois caminhos apontam para o mesmo arquivo? Pelo sistema quando os
    dois existem (pega caixa de letra, links e caminhos 8.3 do Windows)."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


# O ' (n)' que `_livre` acrescenta.
_SERIE = re.compile(r' \(\d+\)$')


def _com_sufixo(caminho: str, sufixo: str) -> str:
    base, ext = os.path.splitext(caminho)
    # Nao dobra: um padrao de nome que ja' termina no sufixo ('{filename}_compressed')
    # nao vira 'foto_compressed_compressed'.
    return caminho if base.endswith(sufixo) else f'{base}{sufixo}{ext}'


def _livre(caminho: str) -> str:
    """O primeiro da serie `nome`, `nome (1)`, `nome (2)`... que esta' livre."""
    if not os.path.exists(caminho):
        return caminho
    base, ext = os.path.splitext(caminho)
    n = 1
    while os.path.exists(f'{base} ({n}){ext}'):
        n += 1
    return f'{base} ({n}){ext}'


def resolver(origem: str, *, pasta: str | None, nome: str | None, extensao: str,
             sufixo: str, conflito: Conflito, pasta_padrao: str | None = None) -> str:
    """O caminho final do resultado. Levanta `ConflitoDeDestino` quando o
    destino existe e `conflito == 'ask'` -- chamado antes de criar o job, e'
    isso que faz a pergunta vir antes de processar."""
    ext = '.' + extensao.lstrip('.').lower()
    diretorio = pasta or os.path.dirname(origem) or pasta_padrao or os.getcwd()
    base = os.path.splitext(nome)[0] if nome else os.path.splitext(os.path.basename(origem))[0]
    caminho = os.path.join(diretorio, base + ext)

    if mesmo_arquivo(caminho, origem):
        caminho = _com_sufixo(caminho, sufixo)

    if os.path.exists(caminho):
        if conflito == 'ask':
            raise ConflitoDeDestino(caminho)
        if conflito == 'rename':
            caminho = _livre(_com_sufixo(caminho, sufixo))
        # 'overwrite': por cima, com gravacao segura
    return caminho


def confirmar_antes_de_gravar(caminho: str, conflito: Conflito, sufixo: str) -> str:
    """Revisa o destino na hora de gravar.

    O destino e' resolvido quando o job e' criado, mas o job pode esperar na
    fila: dois pedidos para o mesmo arquivo resolvem o mesmo nome livre, e o
    segundo gravaria por cima do primeiro. Com "renomear", escolhe de novo.
    Com "perguntar", a pessoa ja' respondeu quando o job foi criado; se o
    arquivo apareceu depois, vale o mesmo que renomear -- nunca apaga o que
    ela nao viu."""
    if os.path.exists(caminho) and conflito != 'overwrite':
        # Parte do nome sem o numero: 'foto_edited (1).mp4' ocupado vira
        # 'foto_edited (2).mp4', e nao 'foto_edited (1)_edited.mp4'.
        base, ext = os.path.splitext(caminho)
        return _livre(_com_sufixo(_SERIE.sub('', base) + ext, sufixo))
    return caminho


@contextmanager
def gravacao_segura(destino: str, *,
                    registrar_parcial: Callable[[str | None], None] | None = None) -> Iterator[str]:
    """Da' um caminho temporario **na pasta do destino**; no sucesso, troca-o
    pelo destino de uma vez (`os.replace`, atomico no mesmo volume); em falha
    ou cancelamento, apaga-o.

    Na mesma pasta, e nao no temporario do sistema: em outro disco o `replace`
    vira copia, e a troca deixa de ser atomica -- um "sobrescrever" que falhasse
    no meio da copia estragaria o arquivo antigo.

    O marcador vem ANTES da extensao (`foto.a1b2c3.partial.png`): o ffmpeg deduz
    o formato pela extensao, e `.png.partial` falha com "Invalid argument". O
    trecho aleatorio evita apagar um arquivo da pessoa que por acaso se chame
    `foto.partial.png`.

    `registrar_parcial` recebe o temporario (e depois None) para quem precisar
    apagar o parcial no encerramento do app (jobs.shutdown)."""
    pasta = os.path.dirname(os.path.abspath(destino))
    os.makedirs(pasta, exist_ok=True)
    base, ext = os.path.splitext(destino)
    temporario = f'{base}.{secrets.token_hex(3)}.partial{ext}'
    if registrar_parcial:
        registrar_parcial(temporario)
    try:
        yield temporario
        if not os.path.isfile(temporario):
            # O gravador terminou "com sucesso" sem produzir arquivo. E' falha --
            # mas o FileNotFoundError do replace nao diria isso a ninguem.
            raise RuntimeError('O processamento terminou sem gravar o resultado.')
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass  # preso pelo encoder: o encerramento do app tenta de novo
        if registrar_parcial:
            registrar_parcial(None)
