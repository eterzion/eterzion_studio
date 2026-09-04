"""T094 — nenhum controle da Central existe sem implementação (FR-068).

Por varredura, não por amostragem. Um controle que envia um campo que nenhuma
dataclass conhece passa por toda a pilha sem reclamar: a rota aceita, `from_dict`
descarta em silêncio, e o arquivo sai como sairia sem ele. A pessoa move o
controle, vê o resultado igual, e conclui que o produto está quebrado — o que é
razoável, porque está.

O teste lê os componentes de configuração e cruza o que eles emitem com o que as
dataclasses aceitam. Um controle novo entra na verificação sem ninguém lembrar de
estendê-la, que é a propriedade que uma lista escrita à mão não teria.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from app.compression import animation, audio, image, video

COMPONENTES = (pathlib.Path(__file__).resolve().parents[3]
               / 'interface' / 'src' / 'renderer' / 'src' / 'components' / 'compression')

CASOS = [
    ('image', 'ImageCompressionSettings.vue', image.ImageSettings),
    ('video', 'VideoCompressionSettings.vue', video.VideoSettings),
    ('audio', 'AudioCompressionSettings.vue', audio.AudioSettings),
    ('animation', 'AnimationCompressionSettings.vue', animation.AnimationSettings),
]


pytestmark = pytest.mark.skipif(
    not COMPONENTES.is_dir(), reason='componentes da interface não encontrados')


@pytest.mark.parametrize('media_kind,arquivo,dataclass_', CASOS)
def test_todo_campo_enviado_pela_tela_e_aceito(media_kind, arquivo, dataclass_):
    caminho = COMPONENTES / arquivo
    assert caminho.is_file(), f'{arquivo} não existe'

    enviados = set(re.findall(r"set\('([a-z_]+)'", caminho.read_text(encoding='utf-8')))
    assert enviados, f'{arquivo} não emite nenhum campo — a varredura ficaria vazia'

    aceitos = set(dataclass_.__dataclass_fields__)
    desconhecidos = sorted(enviados - aceitos)
    assert not desconhecidos, (
        f'{arquivo} envia campos que {dataclass_.__name__} descarta em silêncio: '
        f'{desconhecidos}')


def test_a_varredura_pega_um_campo_inventado(tmp_path):
    """A guarda da guarda: se a expressão parar de casar, os testes acima
    passariam vazios e ninguém notaria."""
    falso = tmp_path / 'Falso.vue'
    falso.write_text("set('campo_que_nao_existe', 1)", encoding='utf-8')
    enviados = set(re.findall(r"set\('([a-z_]+)'", falso.read_text(encoding='utf-8')))
    assert enviados == {'campo_que_nao_existe'}
    assert enviados - set(image.ImageSettings.__dataclass_fields__)
