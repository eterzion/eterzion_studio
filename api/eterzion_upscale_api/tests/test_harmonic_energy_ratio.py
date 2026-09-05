"""Cobertura direta de `_harmonic_energy_ratio`, que substituiu o
`librosa.effects.hpss` dentro do `classify_audio`.

Os testes de `test_content_type_audio.py` cobrem esta função por tabela, através
da classificação — o que basta para dizer que a troca não regrediu, mas não diz
onde ela quebraria. Estes exercitam a separação em si, com sinais cujo conteúdo
harmônico/percussivo é conhecido por construção, e não depende de nenhum modelo
nem de arquivo baixado (por isso rodam na suíte rápida, sem `hardware`).

O que a função promete: uma senoide sustentada é quase toda harmônica, um trem
de impulsos é quase todo percussivo, e ruído branco fica no meio. Se alguma
dessas três deixar de valer, o classificador de fala/música vai errar antes de
qualquer teste de ponta a ponta acusar.
"""
from __future__ import annotations

import numpy as np
import pytest

from eterzion_upscale.processing import _harmonic_energy_ratio

SR = 22050


def _seconds(n: float) -> np.ndarray:
    return np.arange(int(SR * n)) / SR


class TestSeparacaoPorConteudo:
    def test_senoide_sustentada_e_quase_toda_harmonica(self):
        """Uma nota sustentada ocupa a mesma raia de frequência em todos os
        frames — o filtro de mediana ao longo do tempo a preserva inteira."""
        sinal = (0.3 * np.sin(2 * np.pi * 440 * _seconds(3))).astype(np.float32)
        assert _harmonic_energy_ratio(sinal) > 0.95

    def test_trem_de_impulsos_e_quase_todo_percussivo(self):
        """Um clique espalha energia por todo o espectro num frame só — é o
        oposto exato do caso acima, e o filtro de mediana ao longo da
        frequência é quem o captura."""
        sinal = np.zeros(SR * 3, dtype=np.float32)
        sinal[::SR // 8] = 1.0
        assert _harmonic_energy_ratio(sinal) < 0.15

    def test_ruido_branco_fica_no_meio(self):
        """Ruído não é estável em nenhum dos dois eixos, então as duas máscaras
        repartem a energia de forma parecida. Serve de âncora: se este valor
        sair do meio, a normalização das máscaras está errada."""
        rng = np.random.default_rng(0)
        sinal = (0.1 * rng.standard_normal(SR * 3)).astype(np.float32)
        assert 0.35 < _harmonic_energy_ratio(sinal) < 0.65


class TestCasosDegenerados:
    def test_silencio_devolve_o_valor_neutro(self):
        """Sem energia nenhuma a razão seria 0/0. O contrato é devolver 0.5 —
        o mesmo neutro que o código anterior usava — e não NaN, que se
        propagaria silenciosamente até o score final da classificação."""
        assert _harmonic_energy_ratio(np.zeros(SR, dtype=np.float32)) == 0.5

    def test_sinal_mais_curto_que_a_janela_nao_estoura(self):
        """`classify_audio` recorta 30s do meio, mas nada impede um arquivo
        menor que uma única janela de STFT (2048 amostras)."""
        r = _harmonic_energy_ratio(np.zeros(512, dtype=np.float32) + 0.01)
        assert 0.0 <= r <= 1.0

    @pytest.mark.parametrize('n', [0, 1])
    def test_sinal_vazio_ou_de_uma_amostra(self, n):
        r = _harmonic_energy_ratio(np.zeros(n, dtype=np.float32))
        assert 0.0 <= r <= 1.0


def test_a_razao_e_sempre_uma_fracao_valida():
    """Invariante do contrato: quem chama usa o resultado em
    `min(harmonic_ratio / 0.7, 1.0)`, que só faz sentido dentro de [0, 1]."""
    rng = np.random.default_rng(1)
    for _ in range(5):
        sinal = rng.standard_normal(SR).astype(np.float32)
        assert 0.0 <= _harmonic_energy_ratio(sinal) <= 1.0
