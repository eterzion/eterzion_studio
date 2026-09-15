"""Presets e "Repetir" no modo Basico.

Os presets de video e de animacao sao feitos so' de campos tecnicos (crf,
encoding_preset, max_colors, dither), e o modo Basico nao pode envia-los --
condicao 2 da excecao do Principio V, conferida no backend. Enquanto a tela
copiava o preset para o pedido, esses campos saiam e o preset virava nada: os
dez presets de video e animacao nao faziam efeito no Basico. E os cinco de
plataforma (Discord, WhatsApp...) nao faziam em modo nenhum, porque o
`target_bytes` deles ia dentro de settings e ninguem o lia ali.

Agora o backend resolve o preset (e o registro do historico) e usa como base.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import jobs, media_handles, routes
from app.compression import config as compression_config
from app.compression import history
from app.compression.runner import CompressionRefused
from app.main import app


def efetivas(media_kind, settings=None, *, preset_id=None, history_id=None, advanced=False):
    return routes._configuracoes_efetivas(media_kind, settings or {}, preset_id, history_id,
                                          advanced=advanced)


# ------------------------------------------------------------ modo Basico --


@pytest.mark.parametrize('nome', list(compression_config.BUILTIN_PRESETS['video']))
def test_preset_de_video_faz_efeito_no_basico(nome):
    esperado = compression_config.BUILTIN_PRESETS['video'][nome]
    settings, _ = efetivas('video', preset_id=f'builtin.video.{nome}')
    for campo, valor in esperado.items():
        assert settings[campo] == valor


@pytest.mark.parametrize('nome', list(compression_config.BUILTIN_PRESETS['animation']))
def test_preset_de_animacao_faz_efeito_no_basico(nome):
    esperado = compression_config.BUILTIN_PRESETS['animation'][nome]
    settings, _ = efetivas('animation', preset_id=f'builtin.animation.{nome}')
    for campo, valor in esperado.items():
        assert settings[campo] == valor


def test_o_cliente_continua_sem_poder_mandar_campo_tecnico_no_basico():
    # O preset traz os campos tecnicos pelo servidor. O cliente, nao: a regra
    # constitucional segue valendo, com ou sem preset.
    with pytest.raises(CompressionRefused) as erro:
        efetivas('video', {'crf': 18}, preset_id='builtin.video.balanced')
    assert erro.value.reason == 'invalid_settings'


def test_o_que_a_pessoa_mudou_vence_o_preset():
    base = compression_config.BUILTIN_PRESETS['image']['balanced']
    outra = 55 if base.get('quality') != 55 else 56
    settings, _ = efetivas('image', {'quality': outra}, preset_id='builtin.image.balanced')
    assert settings['quality'] == outra


# ---------------------------------------------------------- modo Avancado --


def test_no_avancado_o_preset_nao_e_reaplicado_por_baixo():
    # La' a tela manda tudo explicito. Um campo que a pessoa voltou para
    # "automatico" sai do pedido de proposito; reaplicar o preset desfaria isso.
    settings, _ = efetivas('video', {'encoding_preset': 'medium'},
                           preset_id='builtin.video.max_quality', advanced=True)
    assert 'crf' not in settings
    assert settings == {'encoding_preset': 'medium'}


# ------------------------------------------------------ presets de plataforma --


@pytest.mark.parametrize('advanced', [False, True])
def test_preset_de_plataforma_vira_o_alvo_de_tamanho(advanced):
    alvo_discord = compression_config.PLATFORM_PRESETS['discord']['target_bytes']
    settings, alvo = efetivas('image', preset_id='platform.discord.image', advanced=advanced)
    assert alvo == alvo_discord
    assert 'target_bytes' not in settings


def test_no_avancado_o_alvo_tambem_chega_pelo_painel():
    # No Avancado a tela copia o preset para o painel, e o target_bytes vem
    # junto nas settings.
    settings, alvo = efetivas('image', {'target_bytes': 16_000_000}, advanced=True)
    assert alvo == 16_000_000
    assert 'target_bytes' not in settings


# ------------------------------------------------------------ Repetir --


@pytest.fixture
def historico(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'outputs_dir', str(tmp_path))
    history.clear()
    yield
    history.clear()


def test_repetir_no_basico_reaplica_os_campos_tecnicos_do_registro(historico):
    snapshot = {'crf': 30, 'encoding_preset': 'slow', 'quality': 80}
    history.record(entry_id='h1', display_name='v.mp4', media_kind='video',
                   settings_snapshot=snapshot, result={})
    settings, _ = efetivas('video', history_id='h1')
    assert settings == snapshot


def test_registro_de_outra_midia_e_recusado(historico):
    history.record(entry_id='h2', display_name='f.png', media_kind='image',
                   settings_snapshot={'quality': 80}, result={})
    with pytest.raises(CompressionRefused) as erro:
        efetivas('video', history_id='h2')
    assert erro.value.reason == 'invalid_settings'


# -------------------------------------------------------------- recusas --


def test_preset_inexistente_e_recusado():
    with pytest.raises(CompressionRefused) as erro:
        efetivas('video', preset_id='builtin.video.nao_existe')
    assert erro.value.reason == 'not_found'


def test_preset_de_outra_midia_e_recusado():
    with pytest.raises(CompressionRefused) as erro:
        efetivas('video', preset_id='builtin.image.balanced')
    assert erro.value.reason == 'invalid_settings'


def test_preset_e_historico_juntos_sao_recusados(historico):
    history.record(entry_id='h3', display_name='v.mp4', media_kind='video',
                   settings_snapshot={}, result={})
    with pytest.raises(CompressionRefused) as erro:
        efetivas('video', preset_id='builtin.video.balanced', history_id='h3')
    assert erro.value.reason == 'invalid_settings'


# ------------------------------------------------------ pela rota de verdade --


@pytest.fixture
def client():
    media_handles.clear()
    jobs.jobs.clear()
    with TestClient(app) as c:
        yield c
    media_handles.clear()
    jobs.jobs.clear()


@pytest.fixture
def imagem(tmp_path):
    caminho = tmp_path / 'foto.png'
    Image.new('RGB', (64, 48), (120, 80, 40)).save(caminho)
    return str(caminho)


def test_a_estimativa_parte_das_mesmas_configuracoes_que_a_compressao(client, imagem):
    # Sem isto a estimativa mostraria um numero que a compressao nao produz.
    handle = media_handles.register_media(imagem)
    sem = client.post('/compression/estimate',
                      json={'handle_id': handle, 'media_kind': 'image', 'settings': {}})
    com = client.post('/compression/estimate',
                      json={'handle_id': handle, 'media_kind': 'image', 'settings': {},
                            'preset_id': 'platform.web.image'})
    assert sem.status_code == 200 and com.status_code == 200
    assert com.json() != sem.json()


def test_preset_inexistente_na_estimativa_vira_404_e_nao_500(client, imagem):
    handle = media_handles.register_media(imagem)
    r = client.post('/compression/estimate',
                    json={'handle_id': handle, 'media_kind': 'image', 'settings': {},
                          'preset_id': 'builtin.image.nao_existe'})
    assert r.status_code in (404, 422)
    assert r.json()['detail']['reason'] == 'not_found'
