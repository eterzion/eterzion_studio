"""Presets: os internos vêm da configuração, os do usuário do disco.

Três origens, e a distinção não é burocracia:

- `builtin` — os seis da configuração. **Somente leitura.** Uma atualização do
  produto pode ajustá-los, e é isso que evita a pergunta "por que meus presets
  mudaram sozinhos": os que mudam não são seus.
- `platform` — Discord, WhatsApp e afins. Guardam **limite de tamanho**, não
  configuração. O limite é o fato durável; as configurações que o atingem
  dependem do arquivo, e um preset com bitrate fixo estaria errado para metade
  dos vídeos.
- `user` — os seus. Sobrevivem ao reinício, e nada os altera sem você.

Um preset pertence a **um** tipo de mídia (FR-014). Oferecer um preset de imagem
quando a mídia ativa é vídeo produziria configurações que a outra mídia não tem
como aplicar.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from typing import Any

from . import config

_USER_PRESET_VERSION = 1
_lock = threading.Lock()


class PresetError(ValueError):
    """Carrega uma chave de motivo, nunca uma frase — a interface traduz."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# ------------------------------- internos ------------------------------- #

def builtin_presets(media_kind: str | None = None) -> list[dict[str, Any]]:
    resultado = []
    for kind, presets in config.BUILTIN_PRESETS.items():
        if media_kind and kind != media_kind:
            continue
        for preset_id, settings in presets.items():
            resultado.append({
                'id': f'builtin.{kind}.{preset_id}',
                'name_key': f'compression.preset.{preset_id}',
                'media_kind': kind,
                'origin': 'builtin',
                'settings': dict(settings),
            })
    return resultado


def platform_presets(media_kind: str | None = None) -> list[dict[str, Any]]:
    resultado = []
    for nome, spec in config.PLATFORM_PRESETS.items():
        for kind in spec['media_kinds']:
            if media_kind and kind != media_kind:
                continue
            resultado.append({
                'id': f'platform.{nome}.{kind}',
                'name_key': f'compression.platform.{nome}',
                'media_kind': kind,
                'origin': 'platform',
                # Só o alvo. As configurações saem do resolvedor de tamanho, que
                # conhece o arquivo — e um preset de plataforma que fixasse
                # bitrate estaria errado para metade deles.
                'settings': {'target_bytes': spec['target_bytes']},
            })
    return resultado


# ------------------------------- do usuário ------------------------------- #

def _store_path() -> str:
    from app.config import settings

    return os.path.join(settings.outputs_dir, 'compression-presets.json')


def _load() -> dict[str, dict[str, Any]]:
    caminho = _store_path()
    if not os.path.isfile(caminho):
        return {}
    try:
        with open(caminho, encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        # Um arquivo corrompido não pode impedir a Central de abrir. Perder
        # presets é ruim; não abrir é pior, e o arquivo é reescrito no próximo
        # salvamento.
        return {}
    if dados.get('version') != _USER_PRESET_VERSION:
        return {}
    return dados.get('presets', {})


def _save(presets: dict[str, dict[str, Any]]) -> None:
    caminho = _store_path()
    os.makedirs(os.path.dirname(caminho) or '.', exist_ok=True)
    temporario = caminho + '.tmp'
    # Escrita atômica: um desligamento no meio de um `json.dump` direto deixaria
    # o arquivo truncado, e o próximo início perderia todos os presets.
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump({'version': _USER_PRESET_VERSION, 'presets': presets},
                  arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def user_presets(media_kind: str | None = None) -> list[dict[str, Any]]:
    with _lock:
        guardados = _load()
    return [p for p in guardados.values()
            if not media_kind or p['media_kind'] == media_kind]


def create(name: str, media_kind: str, settings: dict[str, Any]) -> dict[str, Any]:
    _validate(name, media_kind, settings)
    preset = {
        'id': f'user.{secrets.token_urlsafe(8)}',
        # `name`, não `name_key`: a pessoa escolheu esta palavra e ela não se
        # traduz.
        'name': name.strip(),
        'media_kind': media_kind,
        'origin': 'user',
        'settings': dict(settings),
    }
    with _lock:
        guardados = _load()
        guardados[preset['id']] = preset
        _save(guardados)
    return preset


def update(preset_id: str, *, name: str | None = None,
           settings: dict[str, Any] | None = None) -> dict[str, Any]:
    _refuse_readonly(preset_id)
    with _lock:
        guardados = _load()
        preset = guardados.get(preset_id)
        if preset is None:
            raise PresetError('not_found', 'Preset desconhecido.')
        if name is not None:
            _validate(name, preset['media_kind'], preset['settings'])
            preset['name'] = name.strip()
        if settings is not None:
            _validate(preset.get('name', 'x'), preset['media_kind'], settings)
            preset['settings'] = dict(settings)
        _save(guardados)
    return preset


def delete(preset_id: str) -> None:
    _refuse_readonly(preset_id)
    with _lock:
        guardados = _load()
        if preset_id not in guardados:
            raise PresetError('not_found', 'Preset desconhecido.')
        del guardados[preset_id]
        _save(guardados)


def duplicate(preset_id: str, name: str) -> dict[str, Any]:
    """Duplicar um `builtin` produz um `user` — é como um preset interno vira
    ponto de partida sem deixar de ser somente leitura."""
    origem = next((p for p in all_presets() if p['id'] == preset_id), None)
    if origem is None:
        raise PresetError('not_found', 'Preset desconhecido.')
    return create(name, origem['media_kind'], origem['settings'])


def _refuse_readonly(preset_id: str) -> None:
    if not preset_id.startswith('user.'):
        raise PresetError(
            'readonly_preset',
            'Presets internos e de plataforma não podem ser alterados; duplique-o.')


# Campos que fazem sentido em cada tipo de mídia. Um preset de imagem com `crf`
# não é um preset de imagem — e aceitá-lo faria a configuração ser ignorada em
# silêncio na hora de aplicar (FR-014).
_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    'image': frozenset({'quality', 'lossless', 'output_format', 'width', 'height',
                        'percent', 'preserve_aspect', 'prevent_upscale',
                        'metadata_policy', 'png_compress_level', 'chroma_subsampling',
                        'progressive', 'effort', 'speed', 'target_bytes'}),
    'video': frozenset({'container', 'video_codec', 'audio_codec', 'rate_mode', 'crf',
                        'video_bitrate_bps', 'max_bitrate_bps', 'cbr', 'width', 'height',
                        'frame_rate', 'encoding_preset', 'encoder_preference',
                        'audio_bitrate_bps', 'audio_mode', 'sample_rate', 'channels',
                        'target_bytes'}),
    'audio': frozenset({'output_format', 'codec', 'bitrate_mode', 'bitrate_bps',
                        'quality', 'sample_rate', 'channels', 'target_bytes'}),
    'animation': frozenset({'output_format', 'quality', 'width', 'height', 'frame_rate',
                            'max_colors', 'dither', 'optimize_frames', 'target_bytes'}),
}


def _validate(name: str, media_kind: str, settings: dict[str, Any]) -> None:
    if not name or not name.strip():
        raise PresetError('invalid_name', 'O preset precisa de um nome.')
    if media_kind not in _ALLOWED_FIELDS:
        raise PresetError('invalid_media_kind', f'Tipo de mídia desconhecido: {media_kind!r}')
    desconhecidos = set(settings) - _ALLOWED_FIELDS[media_kind]
    if desconhecidos:
        raise PresetError(
            'incompatible_settings',
            f'Configurações que não pertencem a {media_kind}: {sorted(desconhecidos)}')


# ------------------------------- fachada ------------------------------- #

def all_presets(media_kind: str | None = None) -> list[dict[str, Any]]:
    return (builtin_presets(media_kind) + platform_presets(media_kind)
            + user_presets(media_kind))


def clear_user_presets() -> None:
    """Restaurar os padrões (FR-013) — e o que os testes usam para isolar."""
    with _lock:
        _save({})
