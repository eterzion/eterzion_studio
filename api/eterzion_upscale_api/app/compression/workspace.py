"""Onde a compressão trabalha, e como esse lugar deixa de existir.

FR-053 e SC-005: nenhum temporário sobrevive a sucesso, erro, cancelamento ou
encerramento do aplicativo. As quatro palavras importam por igual, e a última é
a que costuma faltar — um `finally` cobre as três primeiras e não cobre um
processo que é morto.

**Por que temporário e não escrever direto no destino** (Princípio XV): uma
compressão interrompida na metade deixaria um arquivo truncado com o nome do
resultado. Quem o abrisse veria um arquivo corrompido onde esperava o seu; pior,
se o nome colidisse com um arquivo existente que a pessoa mandou substituir, o
bom já teria sido apagado para dar lugar ao pela metade.
"""
from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import tempfile
import threading
from typing import Iterator

_PREFIX = 'astros-compression-'

# Todo diretório vivo, para a varredura de encerramento. Um `finally` não roda
# quando o processo é morto, e é exatamente aí que o lixo se acumula.
_live: set[str] = set()
_lock = threading.Lock()


@contextlib.contextmanager
def workspace() -> Iterator[str]:
    """Um diretório de trabalho que some ao sair do bloco, aconteça o que for."""
    caminho = tempfile.mkdtemp(prefix=_PREFIX)
    with _lock:
        _live.add(caminho)
    try:
        yield caminho
    finally:
        _discard(caminho)


def _discard(caminho: str) -> None:
    with _lock:
        _live.discard(caminho)
    # `ignore_errors` porque o encerramento não é lugar de levantar: um arquivo
    # preso por antivírus não pode impedir o aplicativo de fechar. O que fica
    # para trás é apagado pela varredura de órfãos no próximo início.
    shutil.rmtree(caminho, ignore_errors=True)


def cleanup_all() -> None:
    """Apaga tudo que ainda está vivo. Registrado no encerramento."""
    for caminho in list(_live):
        _discard(caminho)


def sweep_orphans() -> int:
    """Apaga diretórios de execuções que **não** terminaram — travamento, queda
    de energia, processo morto.

    Roda no início. É a rede que pega o que nem o `finally` nem o `atexit`
    pegam, e sem ela um travamento por semana enche o disco em silêncio.
    """
    raiz = tempfile.gettempdir()
    removidos = 0
    try:
        entradas = os.listdir(raiz)
    except OSError:
        return 0
    for nome in entradas:
        if not nome.startswith(_PREFIX):
            continue
        caminho = os.path.join(raiz, nome)
        with _lock:
            if caminho in _live:
                continue  # é de uma execução em curso, não órfão
        shutil.rmtree(caminho, ignore_errors=True)
        removidos += 1
    return removidos


atexit.register(cleanup_all)
