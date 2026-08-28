"""Histórico local das compressões, com o **snapshot** do que foi usado.

FR-062 e FR-063. A parte que exige explicação é o snapshot, porque a alternativa
óbvia — guardar o `preset_id` e reler o preset ao repetir — parece equivalente e
falha exatamente quando alguém confia nela.

Um preset é editável. Alguém comprime cinquenta fotos com "Web leve", ajusta o
preset na semana seguinte, e clica em "repetir" numa entrada de antes. Lendo o
preset atual, o resultado sai diferente do que a entrada mostra — e a entrada
continua exibindo os números da execução original. Não há erro visível: só uma
tela que afirma uma coisa e produz outra.

Por isso a entrada guarda `settings_snapshot`, e é dele que "repetir" parte. O
`preset_id` fica junto para dizer de onde veio, e nunca para reler.

**O caminho de origem não é guardado.** Uma entrada de histórico é um registro do
que foi feito, e não um atalho para o arquivo — que pode ter sido movido, ou ter
sido de um pendrive. O que fica é o nome de exibição, já saneado.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any

# Um limite alto o bastante para cobrir meses de uso e baixo o bastante para o
# arquivo continuar sendo lido de uma vez. Sem limite, o histórico de um estúdio
# viraria um JSON de dezenas de MB carregado a cada início.
MAX_ENTRIES = 500

_lock = threading.Lock()


def _store_path() -> str:
    # Ao lado do arquivo de presets, e pelo mesmo motivo: é onde o produto já
    # guarda o que pertence à pessoa e sobrevive ao reinício.
    from app.config import settings

    return os.path.join(settings.outputs_dir, 'compression-history.json')


def _load() -> list[dict[str, Any]]:
    try:
        with open(_store_path(), encoding='utf-8') as fh:
            dados = json.load(fh)
    except (OSError, json.JSONDecodeError):
        # Um histórico ilegível não pode impedir o produto de abrir. Ele é
        # conveniência; perdê-lo custa memória, não trabalho.
        return []
    return dados if isinstance(dados, list) else []


def _save(entradas: list[dict[str, Any]]) -> None:
    """Escrita atômica: grava ao lado e substitui.

    Escrever por cima do arquivo bom deixaria um histórico truncado se a energia
    caísse no meio — e um JSON truncado é um histórico perdido inteiro, não pela
    metade.
    """
    caminho = _store_path()
    os.makedirs(os.path.dirname(caminho) or '.', exist_ok=True)
    fd, temporario = tempfile.mkstemp(dir=os.path.dirname(caminho) or '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(entradas, fh, ensure_ascii=False, indent=2)
        os.replace(temporario, caminho)
    except BaseException:
        if os.path.exists(temporario):
            os.unlink(temporario)
        raise


def record(*, entry_id: str, display_name: str, media_kind: str,
           settings_snapshot: dict[str, Any], result: dict[str, Any],
           preset_id: str | None = None, output_path: str | None = None,
           finished_at: str | None = None) -> dict[str, Any]:
    """Registra uma compressão concluída.

    `settings_snapshot` é uma **cópia**, e não a referência que o chamador tem
    em mãos: o dicionário do job continua vivo depois daqui, e guardar a
    referência faria uma edição posterior reescrever o passado.
    """
    entrada = {
        'id': entry_id,
        'display_name': display_name,
        'media_kind': media_kind,
        'settings_snapshot': json.loads(json.dumps(settings_snapshot)),
        'preset_id': preset_id,
        'result': json.loads(json.dumps(result)),
        'output_path': output_path,
        'finished_at': finished_at,
    }
    with _lock:
        entradas = _load()
        # Mais recente primeiro: é a ordem em que se procura no histórico.
        entradas.insert(0, entrada)
        del entradas[MAX_ENTRIES:]
        _save(entradas)
    return entrada


def all_entries(media_kind: str | None = None) -> list[dict[str, Any]]:
    with _lock:
        entradas = _load()
    if media_kind:
        return [e for e in entradas if e.get('media_kind') == media_kind]
    return entradas


def get(entry_id: str) -> dict[str, Any] | None:
    return next((e for e in all_entries() if e.get('id') == entry_id), None)


def settings_to_repeat(entry_id: str) -> dict[str, Any] | None:
    """As configurações que "repetir compressão" deve usar (FR-063).

    Sempre o snapshot. Reler o preset seria o defeito que este módulo existe para
    impedir: o preset pode ter mudado desde a execução, e o resultado sairia
    diferente do que a entrada exibe.
    """
    entrada = get(entry_id)
    return dict(entrada['settings_snapshot']) if entrada else None


def remove(entry_id: str) -> bool:
    with _lock:
        entradas = _load()
        restantes = [e for e in entradas if e.get('id') != entry_id]
        if len(restantes) == len(entradas):
            return False
        _save(restantes)
    return True


def clear() -> None:
    with _lock:
        _save([])
