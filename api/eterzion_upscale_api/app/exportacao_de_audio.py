"""A exportacao do Audio: formato, qualidade e entrega no destino.

O processamento (voz ou musica) grava um intermediario WAV na pasta interna --
sem perda. A entrega codifica **uma vez**, no formato e na qualidade pedidos,
direto num temporario na pasta do destino (app/destino.py). Antes o resultado
ficava so' na pasta interna, no formato do original, e a "restauracao" de
musica copiava um WAV para um arquivo com a extensao do original: uma musica
.mp3 saia chamada .mp3 com conteudo WAV.

A codificacao e' a da Compressao (app/compression/audio.py): os mesmos
formatos, os mesmos encoders detectados, a mesma regra de que formato sem perda
nao tem bitrate. A qualidade segue o perfil, como na exportacao do Video.
"""
from __future__ import annotations

import os
import shutil
from typing import Any

from app.compression import audio as compressao_audio
from app.compression import capabilities, config

# O perfil vira bitrate so' nos formatos com perda. Os degraus sao os que as
# pessoas usam de fato para musica e voz tratadas: abaixo de 192k o ganho do
# tratamento comeca a se perder na codificacao.
BITRATE_POR_PERFIL = {'fast': 192_000, 'balanced': 256_000, 'quality': 320_000}

# Para a conferencia de espaco: PCM 16 bits, 48 kHz, estereo. Um teto, nao uma
# medida -- o intermediario pode ter outra taxa, mas raramente passa disso.
_PCM_BYTES_POR_SEGUNDO = 48_000 * 2 * 2
_FLAC_FRACAO = 0.7


class RecusaDeAudio(Exception):
    """`reason` e' chave, nunca frase (Principio XIV)."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


def formato_de_saida(pedido: str | None, origem: str) -> str:
    """O formato que sera' gravado. `keep` (ou nada) = o do original."""
    formato = (pedido or 'keep').lower().lstrip('.')
    if formato == 'keep':
        formato = os.path.splitext(origem)[1].lstrip('.').lower()
    return formato


def com_perda(formato: str) -> bool:
    return not compressao_audio.lossless_format(formato)


def verificar(formato: str, *, duracao_segundos: float | None, perfil: str | None,
              pasta: str) -> None:
    """As recusas que cabem antes do job: formato que nao existe, formato que
    esta maquina nao grava, e falta de espaco no destino."""
    codecs = config.AUDIO_FORMATS.get(formato)
    if not codecs:
        raise RecusaDeAudio('format_unavailable', f'Formato de áudio não suportado: {formato}.',
                            {'format': formato})
    if not any(capabilities.audio_codec_encoder(c) for c in codecs):
        raise RecusaDeAudio('encoder_unavailable', 'Este computador não grava este formato.',
                            {'format': formato})
    necessario = estimar_bytes(formato, duracao_segundos, perfil)
    if necessario is None:
        return
    try:
        livre = shutil.disk_usage(pasta).free
    except OSError:
        return  # nao medivel nao e' o mesmo que insuficiente
    if livre < necessario:
        raise RecusaDeAudio('insufficient_disk', 'Não há espaço em disco para o resultado.',
                            {'required_bytes': necessario, 'free_bytes': livre})


def estimar_bytes(formato: str, duracao_segundos: float | None, perfil: str | None) -> int | None:
    if not duracao_segundos:
        return None
    if formato == 'wav':
        return int(duracao_segundos * _PCM_BYTES_POR_SEGUNDO)
    if formato == 'flac':
        return int(duracao_segundos * _PCM_BYTES_POR_SEGUNDO * _FLAC_FRACAO)
    return int(duracao_segundos * BITRATE_POR_PERFIL.get(perfil or 'balanced', 256_000) / 8)


def codificar(intermediario: str, saida: str, formato: str, perfil: str | None) -> None:
    """Do intermediario WAV para `saida`, no formato pedido. WAV para WAV so'
    muda de lugar -- recodificar PCM seria trabalho sem efeito."""
    if formato == 'wav' and intermediario.lower().endswith('.wav'):
        shutil.move(intermediario, saida)
        return
    settings = compressao_audio.AudioSettings(
        output_format=formato,
        bitrate_bps=BITRATE_POR_PERFIL.get(perfil or 'balanced') if com_perda(formato) else None,
    )
    compressao_audio.compress(intermediario, saida, settings)
