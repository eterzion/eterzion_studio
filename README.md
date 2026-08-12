# astros_upscale

Aumente a resolução de **imagens e vídeos** com inteligência artificial. O
`astros_upscale` amplia fotos, ilustrações, anime e vídeos em 2x ou 4x,
recuperando detalhes e removendo ruído — via um **app desktop** (Electron +
Vue) que fala com uma **API local** (FastAPI + PyTorch) rodando na própria
máquina do usuário.

> Este README cobre a visão geral do projeto e a lista de modelos de IA
> disponíveis. Para instalar e rodar o app, veja
> [interface/README.md](interface/README.md).

**Requisitos**

- Funciona em qualquer computador (CPU); se houver uma GPU NVIDIA com CUDA, ela
  é usada automaticamente e o processamento fica muito mais rápido
- ~100 MB de espaço em disco para os modelos (baixados automaticamente na
  primeira vez que cada um é usado)
- Para manter o **áudio** em vídeos processados: [ffmpeg](https://ffmpeg.org/download.html)
  instalado (opcional — sem ele o vídeo sai sem som)

---

## Arquitetura

```
api/         # backend: API HTTP local (FastAPI), serviço de licenciamento, lógica de mídia (PyTorch)
interface/   # app desktop: Electron + Vue 3 + Vite (telas, componentes, stores, i18n)
```

`interface/` só fala com `api/` por HTTP/WebSocket — nunca importa módulo
interno da API diretamente. O processo principal do Electron sobe a API local
automaticamente ao abrir o app; nenhuma configuração manual é necessária no
dia a dia. Veja [interface/README.md](interface/README.md) para instalação,
desenvolvimento e empacotamento do instalador.

Além da API de processamento, o app tem uma tela de ativação/status de
licença que fala com `api/astros_licensing_service` — um segundo serviço
FastAPI, processo separado, dono do seu próprio banco de licenças/instalações
e integrado a Stripe/Mercado Pago para pagamentos.

Para rodar cada serviço isoladamente (desenvolvimento de backend, testes),
entender a divisão de responsabilidades ou ver as variáveis de ambiente
suportadas, veja [api/README.md](api/README.md).

---

## Modelos disponíveis

Todo download é feito diretamente da fonte oficial de cada modelo
(GitHub/Hugging Face do próprio autor, nunca de um espelho de terceiros) para
a pasta `models/`, e verificado por checksum (SHA256) — um arquivo corrompido
ou adulterado é descartado automaticamente. A lista completa e sempre
atualizada, com o que já está baixado e o tamanho de cada um, aparece na tela
de **Modelos** do app.

**Fotos**

| Modelo | Escala | Indicado para |
|---|---|---|
| `realesrgan-x4` *(padrão p/ imagens)* | 4x | Padrão para fotos reais, equilíbrio nitidez/naturalidade |
| `realesrgan-x2` | 2x | Quando 4x é exagero; só dobra a resolução |
| `realesr-general` | 4x | Leve e rápido, bom default geral |
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

Os modelos 1x mantêm o tamanho original — o app os aplica como etapa de
limpeza antes de um upscale, quando o filtro de denoise está habilitado.

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
Hugging Face; confirme na fonte antes de qualquer uso comercial. Veja também
[docs/models/MODEL_LICENSES.md](docs/models/MODEL_LICENSES.md) para o
levantamento completo (código de terceiros, engines de áudio, ffmpeg).

**Pendência**: o modelo `animejanai-compact` (2x, mencionado como candidato
para vídeo de anime) não foi incluído — os releases públicos do projeto
AnimeJaNai no GitHub contêm apenas pacotes do aplicativo mpv (engines
TensorRT, componentes RIFE), não o peso `.pth`/`.safetensors` isolado. Se você
tiver um link direto confiável para esse arquivo, ele pode ser adicionado ao
registro.

### Hospedando seus próprios modelos no GitHub (opcional, desativado por padrão)

**O padrão do projeto é baixar sempre da fonte oficial de cada modelo** — a
API nunca usa um espelho a não ser que você configure um explicitamente com o
passo abaixo. Se um dia preferir hospedar sua própria cópia (por exemplo, para
não depender da disponibilidade dessas fontes), rode o script de
espelhamento **uma vez**, apontando para o seu próprio repositório:

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

O código do `astros_upscale` (backend em `api/` e app desktop em `interface/`)
é distribuído sob uma licença de **uso pessoal e não comercial** (veja o texto
completo em [LICENSE](LICENSE)). Em resumo:

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
