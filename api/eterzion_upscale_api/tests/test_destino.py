"""O nucleo comum de exportacao (app/destino.py), contra arquivos de verdade.

As regras sao as da Imagem, por decisao de produto: nome original, sufixo so'
quando o destino cai no proprio original, e no conflito renomear (sufixo e
depois (1)), perguntar (antes do job) ou sobrescrever (com gravacao segura).
"""
from __future__ import annotations

import os

import pytest

from app import destino
from app.destino import ConflitoDeDestino


@pytest.fixture
def origem(tmp_path):
    caminho = tmp_path / 'foto.png'
    caminho.write_bytes(b'original')
    return str(caminho)


def resolver(origem, **kw):
    padrao = dict(pasta=None, nome=None, extensao='png', sufixo='_upscaled', conflito='rename')
    padrao.update(kw)
    return destino.resolver(origem, **padrao)


# ---------------------------------------------------------------- nome e pasta --


def test_nome_original_com_a_extensao_do_formato(origem, tmp_path):
    assert resolver(origem, extensao='webp') == str(tmp_path / 'foto.webp')


def test_pasta_escolhida(origem, tmp_path):
    outra = tmp_path / 'saida'
    assert resolver(origem, pasta=str(outra), extensao='jpg') == str(outra / 'foto.jpg')


def test_nome_digitado_ganha_a_extensao_do_formato(origem, tmp_path):
    assert resolver(origem, nome='capa.txt', extensao='jpg') == str(tmp_path / 'capa.jpg')


# ------------------------------------------------------------ o original nunca --


@pytest.mark.parametrize('conflito', ['rename', 'overwrite', 'ask'])
def test_o_destino_nunca_e_o_original(origem, tmp_path, conflito):
    # Mesmo formato, mesma pasta, mesmo nome: cai no original. Nem "sobrescrever"
    # o atinge (Principio XV) -- vira o nome com sufixo.
    assert resolver(origem, conflito=conflito) == str(tmp_path / 'foto_upscaled.png')


def test_o_original_e_reconhecido_mesmo_com_outra_caixa(origem, tmp_path):
    if os.name != 'nt':
        pytest.skip('so o Windows ignora caixa de letra no caminho')
    assert resolver(origem, nome='FOTO') == str(tmp_path / 'FOTO_upscaled.png')


# -------------------------------------------------------------------- conflito --


def test_renomear_usa_o_sufixo_e_depois_numera(origem, tmp_path):
    (tmp_path / 'foto.jpg').write_bytes(b'outro')
    assert resolver(origem, extensao='jpg') == str(tmp_path / 'foto_upscaled.jpg')
    (tmp_path / 'foto_upscaled.jpg').write_bytes(b'outro')
    assert resolver(origem, extensao='jpg') == str(tmp_path / 'foto_upscaled (1).jpg')


def test_sufixo_nao_dobra(origem, tmp_path):
    # Um padrao que ja' termina no sufixo nao vira '..._compressed_compressed'.
    (tmp_path / 'foto_compressed.jpg').write_bytes(b'x')
    r = resolver(origem, nome='foto_compressed', extensao='jpg', sufixo='_compressed')
    assert r == str(tmp_path / 'foto_compressed (1).jpg')


def test_perguntar_recusa_antes_do_job(origem, tmp_path):
    (tmp_path / 'foto.jpg').write_bytes(b'outro')
    with pytest.raises(ConflitoDeDestino) as erro:
        resolver(origem, extensao='jpg', conflito='ask')
    assert erro.value.caminho == str(tmp_path / 'foto.jpg')


def test_sobrescrever_mantem_o_destino(origem, tmp_path):
    (tmp_path / 'foto.jpg').write_bytes(b'outro')
    assert resolver(origem, extensao='jpg', conflito='overwrite') == str(tmp_path / 'foto.jpg')


def test_confirmar_antes_de_gravar_escolhe_de_novo_se_o_arquivo_apareceu(tmp_path):
    # Dois jobs na fila para o mesmo arquivo resolvem o mesmo nome livre.
    alvo = tmp_path / 'foto_edited.mp4'
    alvo.write_bytes(b'o primeiro ja gravou')
    assert destino.confirmar_antes_de_gravar(str(alvo), 'rename', '_edited') == \
        str(tmp_path / 'foto_edited (1).mp4')
    assert destino.confirmar_antes_de_gravar(str(alvo), 'overwrite', '_edited') == str(alvo)


def test_confirmar_de_novo_so_renumera_um_nome_ja_numerado(tmp_path):
    (tmp_path / 'foto_edited.mp4').write_bytes(b'x')
    alvo = tmp_path / 'foto_edited (1).mp4'
    alvo.write_bytes(b'o primeiro ja gravou')
    assert destino.confirmar_antes_de_gravar(str(alvo), 'rename', '_edited') ==         str(tmp_path / 'foto_edited (2).mp4')


# ------------------------------------------------------------ gravacao segura --


def test_no_sucesso_o_destino_aparece_de_uma_vez(tmp_path):
    alvo = tmp_path / 'saida' / 'foto.jpg'
    with destino.gravacao_segura(str(alvo)) as temp:
        assert os.path.dirname(temp) == str(alvo.parent)  # na pasta do destino
        assert not alvo.exists()
        with open(temp, 'wb') as f:
            f.write(b'novo')
    assert alvo.read_bytes() == b'novo'
    assert [p.name for p in alvo.parent.iterdir()] == ['foto.jpg']


def test_falha_no_meio_de_sobrescrever_preserva_o_arquivo_antigo(tmp_path):
    # O defeito da Imagem: gravando direto no destino, uma falha no meio de um
    # "sobrescrever" estragava o arquivo que ja' existia.
    alvo = tmp_path / 'foto.jpg'
    alvo.write_bytes(b'antigo intacto')
    with pytest.raises(RuntimeError), destino.gravacao_segura(str(alvo)) as temp:
        with open(temp, 'wb') as f:
            f.write(b'metade')
        raise RuntimeError('o encoder caiu')
    assert alvo.read_bytes() == b'antigo intacto'
    assert [p.name for p in tmp_path.iterdir()] == ['foto.jpg']


def test_o_marcador_vem_antes_da_extensao(tmp_path):
    # O ffmpeg deduz o formato pela extensao; '.webm.partial' falharia.
    with destino.gravacao_segura(str(tmp_path / 'clipe.webm')) as temp:
        assert temp.endswith('.partial.webm')
        open(temp, 'wb').close()


def test_terminar_sem_gravar_e_falha_com_motivo(tmp_path):
    # Um encoder que sai "com sucesso" sem produzir arquivo nao pode virar um
    # resultado -- nem um FileNotFoundError sem explicacao.
    alvo = tmp_path / 'foto.jpg'
    with pytest.raises(RuntimeError, match='sem gravar'), destino.gravacao_segura(str(alvo)):
        pass
    assert not alvo.exists()


def test_o_parcial_e_registrado_e_depois_esquecido(tmp_path):
    visto: list = []
    with destino.gravacao_segura(str(tmp_path / 'a.png'), registrar_parcial=visto.append) as temp:
        open(temp, 'wb').close()
    assert visto[0].endswith('.partial.png') and visto[-1] is None
