"""Command-line interface: ``astros-upscale image``, ``video``, ``audio`` and ``models``."""
from __future__ import annotations

import argparse
import glob
import os
import sys

import cv2
from tqdm import tqdm

from . import __version__
from .audio import AUDIO_ENGINES, MissingAudioDependency, enhance_audio_file, is_engine_available
from .core import (DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL, MODELS, canonical_name, load_model,
                   model_download_status, model_needs_update, resolve_model, update_model)
from .optimize import IMAGE_EXTENSIONS as OPTIMIZE_IMAGE_EXTENSIONS
from .optimize import UnsupportedFormatError, optimize_file
from .utils.download import DownloadError
from .utils.image_io import imread, imwrite
from .utils.video_io import (VideoReader, VideoWriter, copy_audio, even, extract_audio, has_ffmpeg, mux_audio_file)

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff')


def _add_common_args(parser: argparse.ArgumentParser, default_model: str) -> None:
    parser.add_argument('-i', '--input', type=str, required=True, help='Arquivo (ou pasta, para imagens) de entrada')
    parser.add_argument('-o', '--output', type=str, default=None, help='Arquivo ou pasta de saída')
    parser.add_argument(
        '-m', '--model', type=str, default=default_model,
        help=f'Nome do modelo (veja "astros-upscale models") ou caminho de um arquivo .pth. Padrão: {default_model}')
    parser.add_argument('--model-dir', type=str, default='models', help='Pasta onde os modelos são baixados/lidos')
    parser.add_argument(
        '-s', '--scale', type=float, default=None,
        help='Escala final da saída (padrão: a escala nativa do modelo, em geral 4)')
    parser.add_argument(
        '-t', '--tile', type=int, default=0,
        help='Tamanho do bloco (tile) para economizar memória. 0 desliga. Ex.: 400')
    parser.add_argument('--tile-pad', type=int, default=10, help='Borda extra de cada bloco (padrão: 10)')
    parser.add_argument(
        '--device', type=str, default=None, choices=['cpu', 'cuda', 'mps'],
        help='Força o dispositivo (padrão: detecta automaticamente, GPU se houver)')
    parser.add_argument(
        '--fp32', action='store_true',
        help='Usa precisão fp32 (padrão: fp16 em GPU quando o modelo suporta)')
    parser.add_argument(
        '--denoise', type=float, default=0.5,
        help='Força da remoção de ruído, de 0 (mantém ruído) a 1 (remoção forte). Só vale p/ o modelo realesr-general')
    parser.add_argument(
        '--pre', type=str, default=None,
        help='Modelo 1x aplicado ANTES do modelo principal, para limpeza (ex.: --pre dejpg)')


def _build_upscaler(args: argparse.Namespace):
    return load_model(
        args.model,
        model_dir=args.model_dir,
        denoise_strength=args.denoise,
        tile=args.tile,
        tile_pad=args.tile_pad,
        pre_pad=0,
        half=not args.fp32,
        device=args.device)


def _build_pre_upscaler(args: argparse.Namespace):
    """Build the optional 1x pre-processing model (``--pre``)."""
    if args.pre is None:
        return None
    pre = load_model(
        args.pre,
        model_dir=args.model_dir,
        tile=args.tile,
        tile_pad=args.tile_pad,
        pre_pad=0,
        half=not args.fp32,
        device=args.device)
    if pre.scale != 1:
        print(f'Aviso: o modelo de --pre ({args.pre}) tem escala {pre.scale}x; '
              'o esperado é um modelo 1x de limpeza (ex.: dejpg, denoise).')
    return pre


def run_image(args: argparse.Namespace) -> None:
    upscaler = _build_upscaler(args)
    pre_upscaler = _build_pre_upscaler(args)
    outscale = args.scale if args.scale is not None else upscaler.scale

    if os.path.isfile(args.input):
        paths = [args.input]
        single_file = True
    elif os.path.isdir(args.input):
        paths = sorted(p for p in glob.glob(os.path.join(args.input, '*')) if p.lower().endswith(IMAGE_EXTENSIONS))
        single_file = False
        if not paths:
            sys.exit(f'Nenhuma imagem encontrada em: {args.input}')
    else:
        sys.exit(f'Entrada não encontrada: {args.input}')

    output = args.output if args.output is not None else 'results'
    # output is treated as a file path when processing a single file and it has an image extension
    output_is_file = single_file and output.lower().endswith(IMAGE_EXTENSIONS)

    for path in tqdm(paths, unit='img', desc='upscale'):
        img = imread(path)
        if pre_upscaler is not None:
            img, _ = pre_upscaler.enhance(img)
        result, img_mode = upscaler.enhance(img, outscale=outscale)
        if output_is_file:
            save_path = output
        else:
            name, ext = os.path.splitext(os.path.basename(path))
            if img_mode == 'RGBA':  # RGBA precisa de png
                ext = '.png'
            save_path = os.path.join(output, f'{name}_upscaled{ext}')
        imwrite(save_path, result)
    print(f'Pronto! Resultado salvo em: {output}')


def _default_output_path(input_path: str, output: str | None, suffix: str, ext: str = '.mp4') -> str:
    if output is not None:
        return output
    name = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join('results', f'{name}_{suffix}{ext}')


def _process_video_frames(args: argparse.Namespace, upscaler, pre_upscaler, tmp_video: str) -> None:
    outscale = args.scale if args.scale is not None else upscaler.scale
    reader = VideoReader(args.input)
    fps = args.fps if args.fps is not None else reader.fps
    out_width = int(reader.width * outscale)
    out_height = int(reader.height * outscale)
    even_width, even_height = even(out_width), even(out_height)
    if (even_width, even_height) != (out_width, out_height):
        print(f'Aviso: resolução de saída {out_width}x{out_height} é ímpar; '
              f'ajustando para {even_width}x{even_height} (exigido por muitos codecs de vídeo).')
    out_width, out_height = even_width, even_height

    writer = VideoWriter(tmp_video, fps=fps, width=out_width, height=out_height, codec=args.codec)
    try:
        for frame in tqdm(reader, total=len(reader), unit='frame', desc='upscale'):
            if pre_upscaler is not None:
                frame, _ = pre_upscaler.enhance(frame)
            result, _ = upscaler.enhance(frame, outscale=outscale)
            if result.shape[1] != out_width or result.shape[0] != out_height:
                result = cv2.resize(result, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
            writer.write(result)
    finally:
        reader.close()
        writer.close()


def run_video(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.input):
        sys.exit(f'Entrada não encontrada: {args.input}')
    upscaler = _build_upscaler(args)
    pre_upscaler = _build_pre_upscaler(args)
    output = _default_output_path(args.input, args.output, 'upscaled')
    tmp_video = output + '.noaudio.mp4'

    _process_video_frames(args, upscaler, pre_upscaler, tmp_video)

    if args.audio is not None:
        _finish_video_with_enhanced_audio(args, tmp_video, output)
    elif copy_audio(args.input, tmp_video, output):
        os.remove(tmp_video)
    else:
        os.replace(tmp_video, output)
        if not has_ffmpeg():
            print('Aviso: ffmpeg não encontrado — o vídeo foi salvo sem a trilha de áudio original.')
    print(f'Pronto! Vídeo salvo em: {output}')


def _finish_video_with_enhanced_audio(args: argparse.Namespace, tmp_video: str, output: str) -> None:
    """Extract the original audio, run it through an --audio engine, and mux it back in."""
    tmp_audio_in = tmp_video + '.in.wav'
    tmp_audio_out = tmp_video + '.out.wav'
    try:
        if not extract_audio(args.input, tmp_audio_in):
            print('Aviso: não foi possível extrair áudio do vídeo original (sem trilha de áudio, ou ffmpeg '
                  'ausente); o vídeo será salvo sem melhorar áudio.')
            os.replace(tmp_video, output)
            return
        try:
            enhance_audio_file(tmp_audio_in, tmp_audio_out, engine=args.audio, denoise_only=args.denoise_only)
        except MissingAudioDependency as error:
            print(f'Aviso: {error}\nO vídeo será salvo com o áudio original, sem melhoria.')
            if not mux_audio_file(tmp_video, tmp_audio_in, output):
                os.replace(tmp_video, output)
            return
        if not mux_audio_file(tmp_video, tmp_audio_out, output):
            print('Aviso: falha ao remixar o áudio melhorado; salvando vídeo sem áudio.')
            os.replace(tmp_video, output)
    finally:
        if os.path.exists(tmp_video):
            os.remove(tmp_video)
        for tmp in (tmp_audio_in, tmp_audio_out):
            if os.path.exists(tmp):
                os.remove(tmp)


def run_audio(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.input):
        sys.exit(f'Entrada não encontrada: {args.input}')
    output = args.output if args.output is not None else _default_output_path(args.input, None, 'enhanced', '.wav')
    try:
        enhance_audio_file(args.input, output, engine=args.model, denoise_only=args.denoise_only)
    except MissingAudioDependency as error:
        sys.exit(str(error))
    except (RuntimeError, ValueError) as error:
        sys.exit(f'Erro: {error}')
    print(f'Pronto! Áudio salvo em: {output}')


def run_optimize(args: argparse.Namespace) -> None:
    if os.path.isfile(args.input):
        if args.output is None:
            name, ext = os.path.splitext(os.path.basename(args.input))
            output = os.path.join('results', f'{name}_otimizado{ext}')
        elif os.path.isdir(args.output) or args.output.endswith(('/', '\\')):
            output = os.path.join(args.output, os.path.basename(args.input))
        else:
            output = args.output
        try:
            optimize_file(args.input, output, quality=args.quality, codec=args.codec)
        except (UnsupportedFormatError, RuntimeError) as error:
            sys.exit(f'Erro: {error}')
        print(f'Pronto! Arquivo otimizado salvo em: {output}')
    elif os.path.isdir(args.input):
        paths = sorted(
            p for p in glob.glob(os.path.join(args.input, '*')) if p.lower().endswith(OPTIMIZE_IMAGE_EXTENSIONS))
        if not paths:
            sys.exit(f'Nenhuma imagem encontrada em: {args.input} (pastas só são suportadas para imagens)')
        output_dir = args.output if args.output is not None else 'results'
        failures = []
        for path in tqdm(paths, unit='img', desc='otimizar'):
            name, ext = os.path.splitext(os.path.basename(path))
            save_path = os.path.join(output_dir, f'{name}_otimizado{ext}')
            try:
                optimize_file(path, save_path, quality=args.quality)
            except (UnsupportedFormatError, RuntimeError) as error:
                print(f'{path}: FALHOU — {error}')
                failures.append(path)
        if failures:
            sys.exit(f'\n{len(failures)} arquivo(s) falharam: {", ".join(failures)}')
        print(f'Pronto! Resultado salvo em: {output_dir}')
    else:
        sys.exit(f'Entrada não encontrada: {args.input}')


def _model_status_label(name: str, model_dir: str) -> str:
    downloaded, size = model_download_status(name, model_dir=model_dir)
    return f'[OK] {size / 1e6:.0f} MB' if downloaded else '[--] não baixado'


def run_models(args: argparse.Namespace) -> None:
    print('Modelos de imagem/vídeo disponíveis:\n')
    by_category: dict[str, list[tuple[str, dict]]] = {}
    for name, info in MODELS.items():
        by_category.setdefault(info['category'], []).append((name, info))
    for category in sorted(by_category):
        print(f'{category}:')
        for name, info in sorted(by_category[category]):
            status = _model_status_label(name, args.model_dir)
            print(f'  {name:<18} {info["scale"]}x  {status:<12} {info["description"]}')
        print()

    print('Motores de áudio disponíveis (extra opcional, "pip install astros_upscale[audio]"):\n')
    audio_by_category: dict[str, list[tuple[str, dict]]] = {}
    for name, info in AUDIO_ENGINES.items():
        audio_by_category.setdefault(info['category'], []).append((name, info))
    for category in sorted(audio_by_category):
        print(f'{category}:')
        for name, info in sorted(audio_by_category[category]):
            status = '[OK] instalado' if is_engine_available(name) else '[--] não instalado'
            print(f'  {name:<18} {status:<15} {info["description"]}')
        print()

    print('Os modelos de imagem/vídeo são baixados automaticamente na primeira vez (pasta models/).')
    print('Use "astros-upscale models download <nome>" ou "--all" para baixar com antecedência.')
    print('Use "astros-upscale models update <nome>" ou "--all" para atualizar modelos já baixados.')
    print('Modelos 1x (Limpeza) não aumentam a resolução — use-os sozinhos ou como --pre de outro modelo.')


def run_models_download(args: argparse.Namespace) -> None:
    if not args.all and args.name is None:
        sys.exit('Especifique o nome de um modelo ou use --all. Veja: astros-upscale models')
    if not args.all and canonical_name(args.name) not in MODELS:
        sys.exit(f'Modelo desconhecido: {args.name!r}. Veja as opções com: astros-upscale models')
    names = sorted(MODELS) if args.all else [args.name]
    failures = []
    for name in names:
        downloaded, _ = model_download_status(name, model_dir=args.model_dir)
        if downloaded:
            print(f'{name}: já baixado')
            continue
        try:
            resolve_model(name, model_dir=args.model_dir)
            print(f'{name}: baixado com sucesso')
        except (DownloadError, ValueError) as error:
            print(f'{name}: FALHOU — {error}')
            failures.append(name)
    if failures:
        sys.exit(f'\n{len(failures)} modelo(s) falharam: {", ".join(failures)}')
    print('\nPronto!')


def run_models_update(args: argparse.Namespace) -> None:
    """Re-download any model whose local file is missing or no longer matches the
    checksum currently pinned in the registry (e.g. after astros_upscale itself was
    updated to point at a newer mirror or a corrected weight file)."""
    if not args.all and args.name is None:
        sys.exit('Especifique o nome de um modelo ou use --all. Veja: astros-upscale models')
    if not args.all and canonical_name(args.name) not in MODELS:
        sys.exit(f'Modelo desconhecido: {args.name!r}. Veja as opções com: astros-upscale models')
    names = sorted(MODELS) if args.all else [args.name]
    failures = []
    updated_count = 0
    for name in names:
        if not model_needs_update(name, model_dir=args.model_dir):
            print(f'{name}: já atualizado')
            continue
        try:
            update_model(name, model_dir=args.model_dir)
            print(f'{name}: atualizado')
            updated_count += 1
        except (DownloadError, ValueError) as error:
            print(f'{name}: FALHOU — {error}')
            failures.append(name)
    if failures:
        sys.exit(f'\n{len(failures)} modelo(s) falharam: {", ".join(failures)}')
    print(f'\nPronto! {updated_count} modelo(s) atualizado(s).')


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='astros-upscale',
        description='Upscale de imagens e vídeos, e melhoria de áudio, com IA.')
    parser.add_argument('--version', action='version', version=f'astros-upscale {__version__}')
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_image = subparsers.add_parser('image', help='Aumenta a resolução de uma imagem ou pasta de imagens')
    _add_common_args(p_image, DEFAULT_IMAGE_MODEL)
    p_image.set_defaults(func=run_image)

    p_video = subparsers.add_parser('video', help='Aumenta a resolução de um vídeo, frame a frame')
    _add_common_args(p_video, DEFAULT_VIDEO_MODEL)
    p_video.add_argument('--fps', type=float, default=None, help='FPS do vídeo de saída (padrão: igual ao original)')
    p_video.add_argument('--codec', type=str, default='mp4v', help='Codec de saída do OpenCV (padrão: mp4v)')
    p_video.add_argument(
        '--audio', type=str, default=None, choices=sorted(AUDIO_ENGINES),
        help='Também melhora o áudio original com este motor antes de remontar o vídeo (requer extra [audio])')
    p_video.add_argument(
        '--denoise-only', action='store_true',
        help='Com --audio enhance-voz: só remove ruído, sem restauração/extensão de banda')
    p_video.set_defaults(func=run_video)

    p_audio = subparsers.add_parser('audio', help='Melhora a qualidade de um arquivo de áudio')
    p_audio.add_argument('-i', '--input', type=str, required=True, help='Arquivo de áudio de entrada (wav/mp3/flac)')
    p_audio.add_argument('-o', '--output', type=str, default=None, help='Arquivo de saída (padrão: results/)')
    p_audio.add_argument(
        '-m', '--model', type=str, default='denoise-voz', choices=sorted(AUDIO_ENGINES),
        help='Motor de áudio a usar. Padrão: denoise-voz')
    p_audio.add_argument(
        '--denoise-only', action='store_true', help='Com enhance-voz: só remove ruído, sem restauração completa')
    p_audio.set_defaults(func=run_audio)

    p_optimize = subparsers.add_parser(
        'optimize', help='Reduz o tamanho do arquivo (imagem, vídeo ou áudio), mantendo o formato original')
    p_optimize.add_argument('-i', '--input', type=str, required=True, help='Arquivo (ou pasta, para imagens)')
    p_optimize.add_argument('-o', '--output', type=str, default=None, help='Arquivo ou pasta de saída')
    p_optimize.add_argument(
        '-q', '--quality', type=int, default=80,
        help='Qualidade/fidelidade alvo, de 0 (menor arquivo) a 100 (mais próximo do original). Padrão: 80')
    p_optimize.add_argument(
        '--codec', type=str, default='libx264',
        help='Codec de vídeo (padrão: libx264; ex.: libx265 para arquivos ainda menores)')
    p_optimize.set_defaults(func=run_optimize)

    p_models = subparsers.add_parser('models', help='Lista, baixa ou verifica os modelos disponíveis')
    p_models.add_argument('--model-dir', type=str, default='models', help='Pasta onde os modelos são lidos')
    p_models.set_defaults(func=run_models)
    models_sub = p_models.add_subparsers(dest='models_command')

    p_download = models_sub.add_parser('download', help='Baixa um modelo (ou todos) para uso offline')
    p_download.add_argument('name', type=str, nargs='?', default=None, help='Nome do modelo a baixar')
    p_download.add_argument('--all', action='store_true', help='Baixa todos os modelos registrados')
    p_download.add_argument('--model-dir', type=str, default='models', help='Pasta onde os modelos são salvos')
    p_download.set_defaults(func=run_models_download)

    p_update = models_sub.add_parser(
        'update', help='Atualiza um modelo (ou todos) já baixado, refazendo o download se estiver desatualizado')
    p_update.add_argument('name', type=str, nargs='?', default=None, help='Nome do modelo a atualizar')
    p_update.add_argument('--all', action='store_true', help='Verifica e atualiza todos os modelos registrados')
    p_update.add_argument('--model-dir', type=str, default='models', help='Pasta onde os modelos são salvos')
    p_update.set_defaults(func=run_models_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
