"""T086 — o histórico guarda o que foi usado, não de onde veio.

O teste central é `test_repetir_usa_o_snapshot_e_nao_o_preset_alterado`. Ele
existe porque a implementação errada é a natural: guardar `preset_id` e reler o
preset ao repetir é menos código, ocupa menos espaço, e parece equivalente.

Falha exatamente quando alguém confia nela. Uma pessoa comprime cinquenta fotos
com "Web leve", ajusta o preset na semana seguinte, e clica em "repetir" numa
entrada de antes. O resultado sai diferente do que a entrada mostra — e a entrada
continua exibindo os números da execução original. Não há erro visível: só uma
tela que afirma uma coisa e produz outra.
"""
from __future__ import annotations

import json
import os

import pytest

from app.compression import history, presets


@pytest.fixture(autouse=True)
def historico_isolado(tmp_path, monkeypatch):
    """Um arquivo por teste. Sem isto, um teste leria o histórico de outro — e a
    ordem de execução decidiria o resultado."""
    caminho = tmp_path / 'compression-history.json'
    monkeypatch.setattr(history, '_store_path', lambda: str(caminho))
    yield caminho


def _gravar(entry_id: str, **extra) -> dict:
    base = {
        'entry_id': entry_id,
        'display_name': f'{entry_id}.png',
        'media_kind': 'image',
        'settings_snapshot': {'output_format': 'jpeg', 'quality': 70},
        'result': {'original_bytes': 1000, 'output_size_bytes': 400,
                   'saving_bytes': 600, 'grew': False},
    }
    base.update(extra)
    return history.record(**base)


# ------------------------- o snapshot ------------------------- #

def test_repetir_usa_o_snapshot_e_nao_o_preset_alterado(tmp_path, monkeypatch):
    """O teste que justifica o módulo inteiro."""
    loja = tmp_path / 'presets.json'
    monkeypatch.setattr(presets, '_store_path', lambda: str(loja))

    preset = presets.create('Web leve', 'image', {'output_format': 'jpeg', 'quality': 60})
    _gravar('job_1', settings_snapshot=dict(preset['settings']), preset_id=preset['id'])

    # A pessoa muda de ideia sobre o preset, uma semana depois.
    presets.update(preset['id'], settings={'output_format': 'webp', 'quality': 95})

    repetir = history.settings_to_repeat('job_1')
    assert repetir == {'output_format': 'jpeg', 'quality': 60}, (
        'repetir leu o preset atual em vez do que foi de fato usado')

    # E o preset de verdade mudou — o teste acima não passa por acidente.
    atual = next(p for p in presets.user_presets() if p['id'] == preset['id'])
    assert atual['settings']['quality'] == 95


def test_o_snapshot_e_uma_copia_e_nao_a_referencia():
    """O dicionário do job continua vivo depois de gravar. Guardar a referência
    faria uma edição posterior reescrever o passado."""
    configuracoes = {'output_format': 'jpeg', 'quality': 70}
    _gravar('job_2', settings_snapshot=configuracoes)

    configuracoes['quality'] = 10
    assert history.settings_to_repeat('job_2')['quality'] == 70


def test_o_preset_id_fica_registrado_mas_nao_e_o_que_repete():
    """Saber de onde veio é útil; usar isso para repetir é o defeito."""
    _gravar('job_3', preset_id='user.abc',
            settings_snapshot={'output_format': 'png', 'quality': 100})
    entrada = history.get('job_3')
    assert entrada['preset_id'] == 'user.abc'
    assert history.settings_to_repeat('job_3')['output_format'] == 'png'


def test_repetir_uma_entrada_inexistente_devolve_nada():
    assert history.settings_to_repeat('job_que_nao_existe') is None


# ------------------------- persistência ------------------------- #

def test_o_historico_sobrevive_ao_reinicio(historico_isolado):
    _gravar('job_4')
    # Ler de novo do disco é o que um reinício faz.
    assert os.path.isfile(historico_isolado)
    dados = json.loads(historico_isolado.read_text(encoding='utf-8'))
    assert [e['id'] for e in dados] == ['job_4']


def test_o_mais_recente_vem_primeiro():
    """É a ordem em que se procura no histórico."""
    _gravar('job_a')
    _gravar('job_b')
    assert [e['id'] for e in history.all_entries()] == ['job_b', 'job_a']


def test_o_historico_tem_teto():
    """Sem limite, o histórico de um estúdio viraria um JSON de dezenas de MB
    carregado a cada início."""
    limite = history.MAX_ENTRIES
    for i in range(limite + 5):
        _gravar(f'job_{i}')
    entradas = history.all_entries()
    assert len(entradas) == limite
    # O que sobra é o mais recente, não o mais antigo.
    assert entradas[0]['id'] == f'job_{limite + 4}'


def test_um_arquivo_ilegivel_nao_impede_o_produto_de_abrir(historico_isolado):
    """O histórico é conveniência; perdê-lo custa memória, não trabalho."""
    historico_isolado.write_text('isto não é JSON', encoding='utf-8')
    assert history.all_entries() == []
    # E gravar por cima volta a funcionar.
    _gravar('job_5')
    assert [e['id'] for e in history.all_entries()] == ['job_5']


def test_nenhum_caminho_de_origem_e_guardado():
    """Uma entrada é o registro do que foi feito, não um atalho para um arquivo
    que pode ter sido movido."""
    entrada = _gravar('job_6')
    assert 'input_path' not in entrada
    assert 'source_path' not in entrada


# ------------------------- remoção ------------------------- #

def test_remover_uma_entrada_nao_toca_as_outras():
    _gravar('job_x')
    _gravar('job_y')
    assert history.remove('job_x') is True
    assert [e['id'] for e in history.all_entries()] == ['job_y']


def test_remover_o_que_nao_existe_diz_que_nao_existe():
    assert history.remove('job_fantasma') is False


def test_limpar_apaga_tudo_e_deixa_o_arquivo_valido(historico_isolado):
    _gravar('job_z')
    history.clear()
    assert history.all_entries() == []
    assert json.loads(historico_isolado.read_text(encoding='utf-8')) == []


def test_filtrar_por_tipo_de_midia():
    _gravar('job_img', media_kind='image')
    _gravar('job_vid', media_kind='video')
    assert [e['id'] for e in history.all_entries('video')] == ['job_vid']
    assert len(history.all_entries()) == 2
