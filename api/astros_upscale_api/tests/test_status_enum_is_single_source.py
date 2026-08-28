"""T007 — os status do job existem em dois lugares, e têm que dizer a mesma coisa.

O backend define `JobStatusValue` em `schemas.py`; o renderer redefine o mesmo
conjunto em TypeScript porque não há geração de tipos entre os dois. Enquanto
essa duplicação existir, ela precisa de uma verificação: um status novo no
backend que não chegasse ao renderer viraria um estado que a interface recebe e
não sabe desenhar — o job pareceria travado sem que nada tivesse falhado.

O teste não pede que a duplicação acabe. Pede que ela nunca divirja em silêncio.
"""
from __future__ import annotations

import ast
import pathlib
import re
import typing

import pytest

from app import schemas

_RAIZ = pathlib.Path(__file__).resolve().parents[3]
_API_TS = _RAIZ / 'interface' / 'src' / 'renderer' / 'src' / 'services' / 'api.ts'


def _status_do_backend() -> set[str]:
    return set(typing.get_args(schemas.JobStatusValue))


def _status_do_renderer() -> set[str]:
    fonte = _API_TS.read_text(encoding='utf-8')
    corpo = re.search(
        r'export type JobStatusValue\s*=(.*?)(?=\nexport )', fonte, re.S)
    assert corpo, 'declaração de JobStatusValue não encontrada em api.ts'
    return set(re.findall(r"'([a-z_]+)'", corpo.group(1)))


def test_os_dois_conjuntos_sao_iguais():
    backend, renderer = _status_do_backend(), _status_do_renderer()
    assert backend == renderer, (
        f'só no backend: {sorted(backend - renderer)}; '
        f'só no renderer: {sorted(renderer - backend)}')


def test_analyzing_existe_dos_dois_lados():
    """O status que a Central acrescentou (spec 008), nomeado explicitamente
    para que removê-lo de um lado só quebre aqui e não em produção."""
    assert 'analyzing' in _status_do_backend()
    assert 'analyzing' in _status_do_renderer()


@pytest.mark.parametrize('modulo', ['jobs', 'routes'])
def test_nenhum_status_literal_desconhecido_no_backend(modulo):
    """Uma comparação com um status que não existe é sempre falsa, e uma
    comparação sempre falsa não falha — só deixa de acontecer.

    É o defeito que este teste existe para pegar: `status == 'analysing'` (com
    s) passaria por qualquer revisão e nunca dispararia.
    """
    caminho = pathlib.Path(schemas.__file__).with_name(f'{modulo}.py')
    arvore = ast.parse(caminho.read_text(encoding='utf-8'))
    validos = _status_do_backend()

    suspeitos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Compare):
            continue
        alvos = [no.left, *no.comparators]
        if not _compara_status(alvos):
            continue
        for termo in alvos:
            for texto in _strings(termo):
                if texto not in validos:
                    suspeitos.append(texto)

    assert not suspeitos, (
        f'{modulo}.py compara status com valores que não existem em '
        f'JobStatusValue: {sorted(set(suspeitos))}')


def _compara_status(termos: list[ast.expr]) -> bool:
    """Só olha comparações que envolvem algo chamado `status`.

    Sem este filtro o teste leria toda string comparada no módulo e viraria
    ruído — `operation == 'compression'` não é um status.
    """
    for termo in termos:
        if isinstance(termo, ast.Name) and termo.id == 'status':
            return True
        if isinstance(termo, ast.Attribute) and termo.attr == 'status':
            return True
        if (isinstance(termo, ast.Subscript) and isinstance(termo.slice, ast.Constant)
                and termo.slice.value == 'status'):
            return True
        if (isinstance(termo, ast.Call) and isinstance(termo.func, ast.Attribute)
                and termo.func.attr == 'get' and termo.args
                and isinstance(termo.args[0], ast.Constant)
                and termo.args[0].value == 'status'):
            return True
    return False


def _strings(no: ast.expr) -> list[str]:
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return [no.value]
    if isinstance(no, (ast.Tuple, ast.List, ast.Set)):
        return [e.value for e in no.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []
