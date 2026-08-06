# astros_upscale

Aumente a resolução de **imagens e vídeos** com inteligência artificial,
direto do terminal. O `astros_upscale` amplia fotos, ilustrações, anime e
vídeos em 2x ou 4x, recuperando detalhes e removendo ruído.

> Este README cobre só a **CLI**. Para a interface gráfica desktop (app
> Electron + API FastAPI, ou a GUI antiga em PySide6) veja
> [interface/README.md](interface/README.md).

**Requisitos**

- Python 3.9 ou mais novo. O extra opcional `[audio]` (melhoria de voz/áudio)
  instala normalmente — veja a seção de Melhoria de áudio
- Funciona em qualquer computador (CPU); se houver uma GPU NVIDIA com CUDA, ela
  é usada automaticamente e o processo fica muito mais rápido
- ~100 MB de espaço em disco para os modelos (baixados automaticamente)
- Para manter o **áudio** em vídeos: [ffmpeg](https://ffmpeg.org/download.html)
  instalado (opcional — sem ele o vídeo sai sem som)

---

## Instalação

Abra um terminal na pasta do projeto e rode:

```bash
# 1. (recomendado) crie um ambiente virtual
python -m venv .venv

# 2. ative o ambiente
#    Windows:
.venv\Scripts\activate
#    Linux/macOS:
source .venv/bin/activate

# 3. instale
pip install -e .
```

Pronto. Confira se funcionou:

```bash
astros-upscale --version
```

### Modelos

Você **não precisa baixar nada manualmente**: na primeira vez que usar cada
modelo, o arquivo é baixado sozinho — sempre diretamente da fonte oficial do
autor (GitHub/Hugging Face do próprio projeto do modelo, nunca de um espelho
de terceiros) — para a pasta `models/`. Para ver os modelos disponíveis (a
lista mostra quais já estão baixados e o tamanho de cada um):

```bash
astros-upscale models
```

Se preferir deixar tudo pronto para uso offline antes de começar:

```bash
astros-upscale models download --all          # baixa todos os modelos
astros-upscale models download realesrgan-x4  # ou só um específico
```

Para conferir se os arquivos já baixados continuam íntegros e re-baixar (da
fonte oficial) qualquer um que esteja corrompido, ausente ou desatualizado:

```bash
astros-upscale models update --all          # verifica e atualiza todos
astros-upscale models update realesrgan-x4  # ou só um específico
```

### Melhoria de áudio (opcional)

O comando `astros-upscale audio` (e a flag `--audio` do comando de vídeo, veja
abaixo) usam bibliotecas de terceiros que não vêm instaladas por padrão.

**1. Instale o FFmpeg** (necessário para os motores de áudio, e para manter o
som em vídeos):

- **Windows**: `winget install Gyan.FFmpeg` (ou `choco install ffmpeg`)
- **Linux (Debian/Ubuntu)**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`

Confirme que funcionou:

```bash
ffmpeg -version
```

**2. Instale o extra `[audio]`**:

```bash
pip install -e ".[audio]"
```

Isso instala os quatro motores (`denoise-voz`, `enhance-voz`, `super-voz`,
`audio-enhance`) de uma vez. Requer [git](https://git-scm.com/downloads)
instalado, usado para baixar o `audio-enhance`
([astros_audio_enhance](https://github.com/ericinacio/astros_audio_enhance),
um fork próprio do AudioSR modernizado para `torch>=2.6`/`numpy>=2.1` — sem o
travamento em `numpy<=1.23.5` do `audiosr` original, então não precisa mais
de instalação manual à parte). Sem esse passo, `image` e `video` continuam
funcionando normalmente — só o comando `audio`/a flag `--audio` avisam
pedindo essa instalação.

---

## Uso para imagens

Comando básico — amplia uma foto em 4x:

```bash
astros-upscale image -i inputs/0014.jpg -o results/0014_upscaled.png
```

Processar uma **pasta inteira** de imagens (cada resultado ganha o sufixo
`_upscaled`):

```bash
astros-upscale image -i inputs -o results -m realesr-general
```

Escolher a **escala final** da imagem (aqui, 2x) e um modelo mais rápido:

```bash
astros-upscale image -i inputs/0030.jpg -o results/0030_x2.png -s 2 -m realesr-general
```

**Limpar sem aumentar** — os modelos 1x removem ruído/artefatos JPEG mantendo o
tamanho original:

```bash
astros-upscale image -i inputs/0014.jpg -o results/0014_dejpg.png -m dejpg
```

**Limpar e ampliar de uma vez** — use `--pre` para rodar um modelo 1x de
limpeza antes do modelo principal:

```bash
astros-upscale image -i inputs/0014.jpg -o results/0014_chain.png --pre dejpg -m realesrgan-x4
```

Forçar o uso de CPU e precisão máxima:

```bash
astros-upscale image -i inputs/wolf_gray.jpg -o results/wolf.png --device cpu --fp32
```

### Todas as opções de imagem

| Opção | O que faz |
|---|---|
| `-i`, `--input` | Imagem ou pasta de imagens de entrada (obrigatório) |
| `-o`, `--output` | Arquivo de saída (para 1 imagem) ou pasta de saída. Padrão: `results/` |
| `-m`, `--model` | Modelo a usar (veja a lista abaixo) ou caminho de um `.pth` seu. Padrão: `realesrgan-x4` |
| `--pre` | Modelo 1x de limpeza aplicado antes do modelo principal (ex.: `--pre dejpg`) |
| `-s`, `--scale` | Escala final (ex.: `2`, `4`). Padrão: a escala nativa do modelo |
| `-t`, `--tile` | Processa em blocos deste tamanho para gastar menos memória (ex.: `400`). `0` desliga |
| `--device` | `cpu`, `cuda` ou `mps`. Padrão: detecta sozinho (GPU se houver) |
| `--fp32` | Usa precisão máxima (padrão é meia precisão na GPU, mais rápida) |
| `--denoise` | Força da remoção de ruído, de `0` a `1`. Só vale para o modelo `realesr-general` |
| `--model-dir` | Pasta onde os modelos ficam guardados. Padrão: `models/` |

**Formatos suportados**: jpg/jpeg, png, webp, bmp, tif/tiff — incluindo imagens
em tons de cinza, PNG com transparência e imagens de 16 bits.

---

## Uso para vídeos

Comando básico — amplia um vídeo em 2x:

```bash
astros-upscale video -i inputs/video/onepiece_demo.mp4 -o results/onepiece_upscaled.mp4 -m realesr-animevideo -s 2
```

**Como funciona**: o vídeo é processado quadro a quadro — cada frame passa pela
IA e é gravado num novo arquivo, mantendo o fps original (os frames vão sendo
processados em fluxo contínuo, sem acumular arquivos temporários em disco). No
final, se o `ffmpeg` estiver instalado no sistema, a trilha de áudio do vídeo
original é copiada para o resultado; sem ffmpeg, o vídeo é salvo sem som (um
aviso é mostrado). Se a resolução de saída calculada for ímpar, ela é
arredondada para o número par mais próximo automaticamente (a maioria dos
codecs de vídeo exige dimensões pares) — um aviso é mostrado quando isso
acontece.

Modelos leves e rápidos, feitos sob medida para vídeo (menos qualidade por
frame, mas viáveis para milhares de frames):

```bash
astros-upscale video -i clipe.mp4 -o clipe_upscaled.mp4 -m hfa2k-avc -s 2
```

**Melhorar o áudio junto com o vídeo** (requer `pip install -e ".[audio]"`):

```bash
astros-upscale video -i clipe.mp4 -o clipe_upscaled.mp4 --audio denoise-voz
```

Isso extrai a trilha de áudio original, roda o motor escolhido nela, e
remonta o vídeo final com o áudio já melhorado (em vez de apenas copiar o
áudio original). Se a dependência do motor não estiver instalada, um aviso é
mostrado e o vídeo sai com o áudio original, sem interromper o processamento.

⚠️ **Vídeo é bem mais pesado que imagem**: um vídeo é composto por milhares de
frames, e cada um é ampliado individualmente. Como referência, um clipe de 8
segundos em 640×480 (181 frames) levou cerca de 5 minutos em CPU com o modelo
padrão, e bem menos com `hfa2k-avc` (modelo menor). Com GPU o tempo cai
bastante. Para vídeos longos, prefira `realesr-animevideo`, `hfa2k-avc` ou
`realesr-general` (mais leves) e, se faltar memória, use `-t 400`.

### Opções específicas de vídeo

Além de todas as opções de imagem acima:

| Opção | O que faz |
|---|---|
| `--fps` | Força o fps do vídeo de saída. Padrão: igual ao original |
| `--codec` | Codec de gravação (padrão: `mp4v`) |
| `--audio` | Também melhora o áudio original com este motor (`denoise-voz`, `enhance-voz`, `audio-enhance`, `super-voz`) |
| `--denoise-only` | Com `--audio enhance-voz`: só remove ruído, sem restauração completa |

---

## Melhoria de áudio (arquivo separado)

Para melhorar só um arquivo de áudio (sem vídeo), requer
`pip install -e ".[audio]"`:

```bash
astros-upscale audio -i entrevista.wav -o entrevista_limpa.wav -m denoise-voz
```

| Opção | O que faz |
|---|---|
| `-i`, `--input` | Arquivo de áudio de entrada (wav/mp3/flac — outros formatos que o ffmpeg leia também funcionam) |
| `-o`, `--output` | Arquivo de saída. A extensão define o formato (`.wav`, `.mp3`, `.flac`) |
| `-m`, `--model` | Motor de áudio: `denoise-voz` (padrão), `enhance-voz`, `audio-enhance` ou `super-voz` |
| `--denoise-only` | Com `enhance-voz`: só remove ruído, sem a restauração/extensão de banda completa |

| Motor | Indicado para |
|---|---|
| `denoise-voz` | Remover ruído de fala rapidamente, roda bem em CPU |
| `enhance-voz` | Denoise + restauração de fala degradada (mais pesado, melhor qualidade) |
| `audio-enhance` | Super-resolução de áudio geral (música) para 48kHz |
| `super-voz` | Super-resolução de fala (bandwidth extension) para 48kHz |

---

## Otimização de arquivo (reduzir tamanho)

Diferente do upscale, `astros-upscale optimize` **não muda resolução/duração**
— só recomprime o arquivo (imagem, vídeo ou áudio) para ocupar menos espaço,
mantendo o mesmo formato de entrada e saída. Funciona sem o extra `[audio]`
(vídeo e áudio usam o `ffmpeg` do sistema, já necessário para manter som nos
vídeos; veja [Melhoria de áudio](#melhoria-de-áudio-opcional) para instalá-lo).

```bash
astros-upscale optimize -i foto.jpg -o foto_leve.jpg -q 60
astros-upscale optimize -i clipe.mp4 -o clipe_leve.mp4 -q 50 --codec libx265
astros-upscale optimize -i musica.mp3 -o musica_leve.mp3 -q 40
```

Também aceita uma **pasta de imagens** (mesmo padrão do comando `image`):

```bash
astros-upscale optimize -i fotos/ -o fotos_leves/ -q 60
```

| Opção | O que faz |
|---|---|
| `-i`, `--input` | Arquivo (ou pasta, só para imagens) de entrada |
| `-o`, `--output` | Arquivo ou pasta de saída. Padrão: `results/` |
| `-q`, `--quality` | Fidelidade alvo, de `0` (menor arquivo) a `100` (mais próximo do original). Padrão: `80` |
| `--codec` | Codec de vídeo (padrão: `libx264`; `libx265` comprime mais, mas é mais lento e menos compatível) |

**Formatos suportados**: imagens `jpg`/`png`/`webp`; vídeos `mp4`/`mkv`/`mov`/
`avi`/`webm`; áudio `mp3`/`m4a`/`aac`/`ogg`/`opus`/`flac`. Em imagem, `jpg`/
`webp` usam a `--quality` como qualidade de recompressão; `png` (sem perdas)
sempre usa a compressão máxima, ignorando `--quality`. Em vídeo, `--quality`
vira um CRF (`0`→CRF 40, `100`→CRF 18); o áudio original é copiado sem
reprocessar. Em áudio, `--quality` vira um bitrate (`0`→64kbps, `100`→320kbps)
para formatos com perdas; `flac` (sem perdas) sempre usa a compressão máxima.
`wav`/`bmp`/`tif` não têm compressão configurável nesses formatos e não são
suportados — converta para um formato comprimido primeiro se precisar reduzir
o tamanho.

---

## Exemplos completos de ponta a ponta

**Imagem** — ampliar a foto de exemplo `inputs/0014.jpg` (179×179) para 4x
(716×716):

```bash
astros-upscale image -i inputs/0014.jpg -o results/0014_upscaled.png
# upscale: 100%|██████████| 1/1
# Pronto! Resultado salvo em: results/0014_upscaled.png
```

**Vídeo** — ampliar o clipe de exemplo `inputs/video/onepiece_demo.mp4`
(640×480) para 2x (1280×960), mantendo o fps original:

```bash
astros-upscale video -i inputs/video/onepiece_demo.mp4 -o results/onepiece_upscaled.mp4 -m realesr-animevideo -s 2
# upscale: 100%|██████████| 181/181
# Pronto! Vídeo salvo em: results/onepiece_upscaled.mp4
```

---

## Solução de problemas (FAQ)

**Erro de falta de memória (RAM ou VRAM)**
Use o processamento em blocos com `-t 400` (ou um valor menor, como `-t 200`).
Se ainda faltar memória na GPU, rode na CPU com `--device cpu`.

**"Modelo desconhecido" ou modelo não encontrado**
Rode `astros-upscale models` para ver os nomes válidos. Os arquivos `.pth`
ficam na pasta `models/` (criada automaticamente). Se você tem um modelo
próprio, passe o caminho completo: `-m caminho/para/modelo.pth`.

**O vídeo de saída ficou sem áudio**
Instale o [ffmpeg](https://ffmpeg.org/download.html) e verifique se o comando
`ffmpeg` funciona no terminal. Sem ele, o áudio não pode ser copiado do vídeo
original. Depois de instalar, rode o comando de novo.

**Formato não suportado**
Imagens: use jpg, png, webp, bmp ou tiff. Vídeos: use formatos comuns (mp4,
mkv, avi, mov); em caso de erro na leitura, converta antes para mp4.

**Ficou lento demais**
Vídeo em CPU é pesado mesmo. Use um modelo leve (`realesr-general`,
`realesr-animevideo` ou `hfa2k-avc`), reduza a escala final (`-s 2`) ou rode
numa máquina com GPU NVIDIA.

**"precisa do pacote opcional ..." ao usar `audio`/`--audio`**
`pip install -e ".[audio]"` puxa quatro bibliotecas: `denoiser`
(`denoise-voz`), `voicefixer` (`enhance-voz`), `audiosronnx` (`super-voz`) e
`astros-audio-enhance` (`audio-enhance`). As três primeiras são pacotes
Python puros, sem etapa de compilação nativa (sem Rust, sem toolchain C++,
sem `deepspeed`) e sem numpy travado numa versão exata — o `audiosronnx`
nem usa `torch` em tempo de execução, roda em cima do `onnxruntime`. Todas
instalam normalmente junto com o resto do projeto.

`astros-audio-enhance` é o único caso à parte: não está publicado no PyPI,
então `pip install -e ".[audio]"` instala esse pacote direto do repositório
Git do autor (`git+https://github.com/ericinacio/astros_audio_enhance.git`),
exigindo `git` instalado. É um fork próprio do AudioSR original (Liu et al.)
reescrito contra `torch>=2.6`/`numpy>=2.1` — ao contrário do `audiosr`
upstream (que prendia `numpy<=1.23.5`, incompatível com o `numpy>=1.26` do
resto do projeto), não exige nenhuma instalação manual separada.

---

## Modelos disponíveis

Veja a lista sempre atualizada com `astros-upscale models`. Todo download é
verificado por checksum (SHA256) — um arquivo corrompido ou adulterado é
descartado automaticamente.

**Fotos**

| Modelo | Escala | Indicado para |
|---|---|---|
| `realesrgan-x4` *(padrão p/ imagens)* | 4x | Padrão para fotos reais, equilíbrio nitidez/naturalidade |
| `realesrgan-x2` | 2x | Quando 4x é exagero; só dobra a resolução |
| `realesr-general` | 4x | Leve e rápido, bom default geral; aceita `--denoise` |
| `realesrnet-x4` | 4x | Resultado mais suave e com menos artefatos |
| `ultrasharp` | 4x | Muito nítido; ótimo em JPEG comprimido |
| `nomos-webphoto` | 4x | Fotos reais degradadas da web (ruído, blur, recompressão) |
| `nomos2-dat2` | 4x | Transformer (DAT-2), o mais nítido — pesado, evite p/ vídeo/lote |

**Anime**

| Modelo | Escala | Indicado para |
|---|---|---|
| `realesrgan-anime` | 4x | Modelo leve otimizado para anime/ilustração |
| `animesharp` | 4x | Linhas limpas em ilustrações e texto |
| `hfa2k-span` | 2x | Qualidade parecida ao realesrgan-anime, bem mais rápido (SPAN) |
| `anime-video` *(padrão p/ vídeos)* | 4x | Vídeos de anime — leve e rápido |

**Vídeo/Anime** (leves, feitos para processar muitos frames)

| Modelo | Escala | Indicado para |
|---|---|---|
| `realesr-animevideo` *(padrão p/ vídeos)* | 4x | Oficial Real-ESRGAN, leve, feito para vídeo de anime |
| `hfa2k-avc` | 2x | Trata degradação h264 típica de vídeo comprimido/streaming |
| `nomosuni-span` | 2x | SPAN universal e leve, tolera múltiplos níveis de recompressão JPEG |

**Vídeo Real** (live-action, não-anime)

| Modelo | Escala | Indicado para |
|---|---|---|
| `liveaction-span` | 2x | Vídeo real (h264/h265/VP9), sem denoise agressivo — preserva grão/detalhe |

**Restauração**

| Modelo | Escala | Indicado para |
|---|---|---|
| `nmkd-siax` | 4x | Universal p/ imagens limpas ou pouco comprimidas |
| `nmkd-superscale` | 4x | Fotos reais com ruído e artefatos |

**Limpeza (1x — melhora sem aumentar)**

| Modelo | Escala | Indicado para |
|---|---|---|
| `denoise` | 1x | Remove ruído fotográfico; trata leve compressão JPEG |
| `dejpg` | 1x | Remove artefatos JPEG (fotos muito comprimidas) |
| `deh264` | 1x | Remove artefatos de compressão H264 (pré-limpeza antes de outro modelo) |

Os modelos 1x mantêm o tamanho original — use-os sozinhos (`-m dejpg`) ou como
etapa de limpeza antes de um upscale (`--pre dejpg -m realesrgan-x4`).

Dica: comece com o modelo padrão. Se o resultado tiver artefatos ou "exagero"
de nitidez, experimente `realesrnet-x4` (fotos) ou ajuste `--denoise`
(`realesr-general`). Os nomes antigos (`photo-x4`, `fast-x4`, `anime-x4`,
`anime-video`, `anime-video-x4`...) continuam funcionando como sinônimos.

### Origem, autoria e licença de cada modelo

Os modelos vêm de projetos e autores da comunidade — cada um com sua própria
licença. `astros_upscale` só os carrega para uso; a licença de cada arquivo
continua sendo a do autor original.

| Modelo(s) | Autor(es) | Licença | Fonte |
|---|---|---|---|
| `realesrgan-x4`, `realesrgan-x2`, `realesr-general`, `realesrnet-x4`, `realesrgan-anime`, `realesr-animevideo` | Xintao Wang e colaboradores (Real-ESRGAN) | BSD-3-Clause | [github.com/xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) |
| `ultrasharp` | Kim2091 | **CC-BY-NC-SA-4.0** (uso não comercial, com atribuição) | [openmodeldb.info/models/4x-UltraSharp](https://openmodeldb.info/models/4x-UltraSharp) |
| `animesharp` | Kim2091 | **CC-BY-NC-SA-4.0** (uso não comercial, com atribuição) | [openmodeldb.info/models/4x-AnimeSharp](https://openmodeldb.info/models/4x-AnimeSharp) |
| `nmkd-siax`, `nmkd-superscale` | Nmkd | WTFPL (uso livre) | [openmodeldb.info](https://openmodeldb.info/models/4x-NMKD-Siax-CX) |
| `denoise`, `dejpg`, `hfa2k-avc`, `deh264`, `hfa2k-span`, `nomosuni-span`, `nomos-webphoto`, `nomos2-dat2` | Philip Hofmann (Phhofm/Phips) | CC-BY-4.0 (uso livre, com atribuição) | [huggingface.co/Phips](https://huggingface.co/Phips) |
| `liveaction-span` | jcj83429 | **CC-BY-NC-SA-4.0** (uso não comercial, com atribuição) | [github.com/jcj83429/upscaling](https://github.com/jcj83429/upscaling) |

⚠️ `ultrasharp` e `animesharp` são **CC-BY-NC-SA 4.0**: não use os resultados
gerados por eles comercialmente sem verificar os termos, e mantenha a
atribuição ao Kim2091 se redistribuir. Essas informações vêm da API pública do
[OpenModelDB](https://openmodeldb.info/) e da página de cada modelo no
Hugging Face; confirme na fonte antes de qualquer uso comercial.

**Pendência**: o modelo `animejanai-compact` (2x, mencionado como candidato
para vídeo de anime) não foi incluído — os releases públicos do projeto
AnimeJaNai no GitHub contêm apenas pacotes do aplicativo mpv (engines
TensorRT, componentes RIFE), não o peso `.pth`/`.safetensors` isolado. Se você
tiver um link direto confiável para esse arquivo, ele pode ser adicionado ao
registro.

### Hospedando seus próprios modelos no GitHub (opcional, desativado por padrão)

**O padrão do projeto é baixar sempre da fonte oficial de cada modelo** —
`astros-upscale models download` e `astros-upscale models update` nunca usam
um espelho a não ser que você configure um explicitamente com o passo abaixo.
Se um dia preferir hospedar sua própria cópia (por exemplo, para não depender
da disponibilidade dessas fontes), rode o script de espelhamento **uma vez**,
apontando para o seu próprio repositório:

```bash
# requer o GitHub CLI instalado e autenticado: https://cli.github.com/
gh auth login
python scripts/mirror_models.py --repo seu-usuario/astros_upscale
```

Isso baixa cada modelo, confere o checksum, publica os arquivos como assets
de um [GitHub Release](https://docs.github.com/releases) chamado `models-v1`
no seu repositório, e gera um arquivo `models.json` na raiz do projeto — esse
arquivo (pequeno, só texto) deve ser commitado; os `.pth`/`.safetensors` em si
**não** vão para o git, só para o Release.

A partir daí, todo download tenta primeiro o seu espelho e cai automaticamente
para a URL original se o espelho estiver indisponível — nenhuma outra
configuração é necessária, e quem clonar o projeto sem rodar o script continua
funcionando normalmente (baixando das fontes originais).

Use `python scripts/mirror_models.py --help` para ver todas as opções
(espelhar só alguns modelos, mudar o nome do release, etc.).

---

## Licença

O código do `astros_upscale` é distribuído sob uma licença de **uso pessoal
e não comercial** (veja o texto completo em [LICENSE](LICENSE)). Em resumo:

- Permitido: usar e modificar o código para fins pessoais e não comerciais.
- Proibido: redistribuir o código (original ou modificado, gratuito ou
  pago), usá-lo comercialmente (venda, como parte de um produto/serviço a
  terceiros, ou qualquer uso que gere receita), ou sublicenciá-lo/cedê-lo a
  terceiros.

Essa licença cobre **apenas o código deste projeto**. Os modelos de IA
baixados em tempo de execução (pasta `models/`) têm autoria e licenças
próprias e independentes — várias delas têm suas próprias restrições
(`ultrasharp` e `animesharp` são CC-BY-NC-SA-4.0, por exemplo). Veja a tabela
completa em
[Origem, autoria e licença de cada modelo](#origem-autoria-e-licença-de-cada-modelo)
antes de usar qualquer resultado gerado por eles.
