# eterzion_upscale

Aumente a resolução de **imagens e vídeos** com inteligência artificial. O
`eterzion_upscale` amplia fotos, ilustrações, anime e vídeos em 2x ou 4x,
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
licença que fala com `api/eterzion_licensing_service` — um segundo serviço
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

O registro (`api/eterzion_upscale/processing.py`, `MODELS`) hoje tem **um único
modelo por `content_type`**, escolhido por um benchmark real de qualidade
perceptual (LPIPS/PSNR/SSIM — ver
[docs/models/BENCHMARK_RESULTS.md](docs/models/BENCHMARK_RESULTS.md)) entre
os candidatos com licença comercial aprovada, em vez de várias opções
concorrentes por categoria.

**Fotos**

| Modelo | Escala | Indicado para |
|---|---|---|
| `nomos-webphoto` *(padrão p/ imagens)* | 4x | Fotos reais degradadas da web (ruído, blur, recompressão) — vencedor do benchmark de perfis |

**Anime**

| Modelo | Escala | Indicado para |
|---|---|---|
| `hfa2k-span` | 2x | Qualidade parecida ao antigo `realesrgan-anime`, bem mais rápido (SPAN) — vencedor do benchmark |

**Vídeo/Anime** (leves, feitos para processar muitos frames)

| Modelo | Escala | Indicado para |
|---|---|---|
| `realesr-animevideo` *(padrão p/ vídeos)* | 4x | Oficial Real-ESRGAN, leve, feito para vídeo de anime |
| `hfa2k-avc` | 2x | Trata degradação h264 típica de vídeo comprimido/streaming |
| `nomosuni-span` | 2x | SPAN universal e leve, tolera múltiplos níveis de recompressão JPEG |

**Vídeo Real** (live-action, não-anime)

| Modelo | Escala | Indicado para |
|---|---|---|
| `realplksr-video-real` | 2x | Vídeo real (h264/h265/VP9), sem denoise agressivo — preserva grão/detalhe entre quadros |

**Limpeza (1x — melhora sem aumentar)**

| Modelo | Escala | Indicado para |
|---|---|---|
| `denoise` | 1x | Remove ruído fotográfico; trata leve compressão JPEG |
| `dejpg` | 1x | Remove artefatos JPEG (fotos muito comprimidas) |
| `deh264` | 1x | Remove artefatos de compressão H264 (pré-limpeza antes de outro modelo) |

Os modelos 1x mantêm o tamanho original — o app os aplica como etapa de
limpeza antes de um upscale, quando o filtro de denoise está habilitado.

### Modelos removidos do registro

Vários candidatos que já estiveram no app foram removidos do registro
`MODELS`. Um job antigo (ou link salvo) que ainda referencie um desses nomes
não trava com um erro genérico de "modelo desconhecido" — `resolve_model()`
reconhece o nome em `REMOVED_MODEL_IDENTIFIERS` e explica o motivo da
remoção, pedindo para reprocessar com um perfil atual:

| Modelo removido | Motivo |
|---|---|
| `realesrgan-x4`, `realesrgan-x2`, `realesr-general`, `realesrnet-x4`, `realesrgan-anime`, `nomos2-dat2` | Perderam para o vencedor do benchmark de perfis (mesma licença, qualidade perceptual inferior no teste) |
| `ultrasharp`, `animesharp`, `liveaction-span` | Licença não permite uso comercial (CC-BY-NC-SA-4.0) |
| `nmkd-siax`, `nmkd-superscale` | Licença nunca confirmada por fonte oficial de primeira mão (categoria "Restauração" inteira foi removida por esse motivo) |

### Origem, autoria e licença de cada modelo

Os modelos vêm de projetos e autores da comunidade — cada um com sua própria
licença. `eterzion_upscale` só os carrega para uso; a licença de cada arquivo
continua sendo a do autor original.

| Modelo(s) | Autor(es) | Licença | Fonte |
|---|---|---|---|
| `realesr-animevideo` | Xintao Wang e colaboradores (Real-ESRGAN) | BSD-3-Clause | [github.com/xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) |
| `nomos-webphoto`, `hfa2k-span`, `hfa2k-avc`, `nomosuni-span`, `denoise`, `dejpg`, `deh264` | Philip Hofmann (Phhofm/Phips) | CC-BY-4.0 (uso livre, com atribuição) | [huggingface.co/Phips](https://huggingface.co/Phips) |
| `realplksr-video-real` | Philip Hofmann (Phhofm) | **Apache-2.0** (código e pesos) — dataset 100% domínio público | [github.com/Phhofm/models](https://github.com/Phhofm/models/releases/tag/2xPublic_realplksr_dysample_layernorm_real) |

Todos os modelos ativos hoje têm licença comercial explícita, sem ressalva de
uso não comercial — os candidatos que só tinham licença CC-BY-NC-SA (não
comercial) foram removidos do registro (ver tabela acima). Essas informações
vêm da API pública do [OpenModelDB](https://openmodeldb.info/) e da página de
cada modelo no Hugging Face/GitHub; confirme na fonte antes de qualquer uso
comercial. Veja também
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
python scripts/mirror_models.py --repo seu-usuario/eterzion_upscale
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

O código do `eterzion_upscale` (backend em `api/` e app desktop em `interface/`)
é distribuído sob uma licença de **uso pessoal e não comercial** (veja o texto
completo em [LICENSE](LICENSE)). Em resumo:

- Permitido: usar e modificar o código para fins pessoais e não comerciais.
- Proibido: redistribuir o código (original ou modificado, gratuito ou
  pago), usá-lo comercialmente (venda, como parte de um produto/serviço a
  terceiros, ou qualquer uso que gere receita), ou sublicenciá-lo/cedê-lo a
  terceiros.

Essa licença cobre **apenas o código deste projeto**. Os modelos de IA
baixados em tempo de execução (pasta `models/`) têm autoria e licenças
próprias e independentes de terceiros — todos os modelos ativos hoje têm
licença comercial explícita (ver
[Origem, autoria e licença de cada modelo](#origem-autoria-e-licença-de-cada-modelo)),
mas confirme na fonte antes de qualquer uso comercial dos resultados.
