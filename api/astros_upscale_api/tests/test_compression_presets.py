"""T019 — presets: origem, propriedade e o que cada tipo de mídia aceita."""
from __future__ import annotations

import pytest

from app.compression import config, presets


@pytest.fixture(autouse=True)
def limpo(tmp_path, monkeypatch):
    """Cada teste com o seu armazenamento — presets do usuário persistem em
    disco, e um teste que sujasse o do próximo seria pior que inútil."""
    monkeypatch.setattr(presets, '_store_path',
                        lambda: str(tmp_path / 'compression-presets.json'))
    yield


# ------------------------------- internos ------------------------------- #

def test_os_internos_cobrem_as_quatro_midias():
    for kind in ('image', 'video', 'audio', 'animation'):
        ids = {p['id'].split('.')[-1] for p in presets.builtin_presets(kind)}
        assert ids == set(config.PRESET_IDS) - {'custom'}


def test_custom_nao_tem_valores():
    """`custom` é o que a pessoa ajustou. Listá-lo com números seria um sexto
    preset disfarçado, e o primeiro a divergir do que a tela mostra."""
    for kind in config.BUILTIN_PRESETS:
        assert 'custom' not in config.BUILTIN_PRESETS[kind]


def test_o_nome_dos_internos_e_chave_e_o_do_usuario_e_texto():
    """Um preset interno se traduz; o nome que a pessoa escolheu, não."""
    interno = presets.builtin_presets('image')[0]
    assert 'name_key' in interno and 'name' not in interno

    meu = presets.create('Meu ajuste', 'image', {'quality': 70})
    assert 'name' in meu and 'name_key' not in meu


def test_a_qualidade_cai_do_melhor_preset_para_o_mais_comprimido():
    q = config.BUILTIN_PRESETS['image']
    assert (q['max_quality']['quality'] > q['high_quality']['quality']
            > q['balanced']['quality'] > q['small_file']['quality']
            > q['max_compression']['quality'])


def test_no_video_o_crf_sobe_quando_a_qualidade_cai():
    """CRF é invertido — número maior significa mais compressão. Um preset
    "qualidade máxima" com CRF alto seria o erro exato que este teste pega."""
    v = config.BUILTIN_PRESETS['video']
    assert (v['max_quality']['crf'] < v['balanced']['crf']
            < v['max_compression']['crf'])


# ------------------------------- plataforma ------------------------------- #

def test_presets_de_plataforma_guardam_limite_e_nao_configuracao():
    """O limite é o fato durável; as configurações que o atingem dependem do
    arquivo. Um preset de Discord com bitrate fixo estaria errado para metade
    dos vídeos."""
    for preset in presets.platform_presets():
        assert set(preset['settings']) == {'target_bytes'}
        assert preset['settings']['target_bytes'] > 0


def test_plataforma_so_aparece_para_as_midias_que_declara():
    web = [p for p in presets.platform_presets() if p['id'].startswith('platform.web.')]
    assert {p['media_kind'] for p in web} == set(config.PLATFORM_PRESETS['web']['media_kinds'])


# ------------------------------- do usuário ------------------------------- #

def test_um_preset_criado_sobrevive_a_releitura():
    criado = presets.create('Web 85', 'image', {'quality': 85, 'output_format': 'webp'})
    guardados = presets.user_presets('image')
    assert any(p['id'] == criado['id'] and p['name'] == 'Web 85' for p in guardados)


def test_renomear_e_reconfigurar():
    criado = presets.create('Antigo', 'image', {'quality': 70})
    presets.update(criado['id'], name='Novo')
    presets.update(criado['id'], settings={'quality': 40})
    guardado = presets.user_presets('image')[0]
    assert guardado['name'] == 'Novo' and guardado['settings']['quality'] == 40


def test_excluir_remove_so_o_pedido():
    a = presets.create('A', 'image', {'quality': 70})
    presets.create('B', 'image', {'quality': 80})
    presets.delete(a['id'])
    assert {p['name'] for p in presets.user_presets('image')} == {'B'}


def test_duplicar_um_interno_produz_um_do_usuario():
    """É como um preset interno vira ponto de partida sem deixar de ser somente
    leitura."""
    interno = presets.builtin_presets('image')[0]
    copia = presets.duplicate(interno['id'], 'Minha versão')
    assert copia['origin'] == 'user'
    assert copia['settings'] == interno['settings']
    assert copia['media_kind'] == interno['media_kind']


def test_restaurar_padroes_apaga_so_os_do_usuario():
    presets.create('Meu', 'image', {'quality': 50})
    presets.clear_user_presets()
    assert presets.user_presets() == []
    assert presets.builtin_presets('image')  # os internos continuam


# ------------------------------- propriedade ------------------------------- #

def test_um_interno_nao_pode_ser_alterado():
    """Uma atualização do produto pode ajustá-los, e é isso que evita a pergunta
    "por que meus presets mudaram sozinhos": os que mudam não são seus."""
    interno = presets.builtin_presets('image')[0]
    with pytest.raises(presets.PresetError) as erro:
        presets.update(interno['id'], name='Meu')
    assert erro.value.reason == 'readonly_preset'


def test_um_de_plataforma_nao_pode_ser_excluido():
    plataforma = presets.platform_presets('image')[0]
    with pytest.raises(presets.PresetError) as erro:
        presets.delete(plataforma['id'])
    assert erro.value.reason == 'readonly_preset'


# ------------------------------- tipo de mídia ------------------------------- #

def test_um_preset_pertence_a_uma_midia_so():
    """FR-014. Oferecer um preset de imagem quando a mídia é vídeo produziria
    configurações que a outra não tem como aplicar."""
    presets.create('Só imagem', 'image', {'quality': 70})
    assert presets.user_presets('video') == []
    assert len(presets.user_presets('image')) == 1


def test_configuracao_que_nao_pertence_a_midia_e_recusada():
    """`crf` não existe em imagem. Aceitá-lo faria a configuração ser ignorada
    em silêncio na hora de aplicar — pior que recusar."""
    with pytest.raises(presets.PresetError) as erro:
        presets.create('Errado', 'image', {'crf': 20})
    assert erro.value.reason == 'incompatible_settings'


def test_nome_vazio_e_recusado():
    with pytest.raises(presets.PresetError) as erro:
        presets.create('   ', 'image', {'quality': 70})
    assert erro.value.reason == 'invalid_name'


def test_midia_desconhecida_e_recusada():
    with pytest.raises(presets.PresetError) as erro:
        presets.create('X', 'holograma', {'quality': 70})
    assert erro.value.reason == 'invalid_media_kind'


# ------------------------------- resiliência ------------------------------- #

def test_um_arquivo_corrompido_nao_impede_a_central_de_abrir(tmp_path):
    """Perder presets é ruim; não abrir é pior. O arquivo é reescrito no próximo
    salvamento."""
    caminho = tmp_path / 'compression-presets.json'
    caminho.write_text('{ isto nao e json', encoding='utf-8')
    assert presets.user_presets() == []
    assert presets.create('Novo', 'image', {'quality': 60})['id']
