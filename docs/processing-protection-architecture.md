# Arquitetura de proteção do código de processamento — documento de fases

Status: **Fases 1-5 implementadas e testadas com os serviços reais rodando** (não apenas revisão de código). Fase 6 (hardware opcional) segue não implementada, por decisão do próprio documento — ver §8.
Escopo: cobre a especificação completa recebida (defesa em profundidade para o pipeline de upscale), decompõe em fases executáveis e adiciona medidas complementares além da especificação original.

---

## Status de implementação

| Fase | Status | Onde está o código |
|---|---|---|
| Fase 1 — Isolamento de processo | ✅ Implementada e testada | `api/astros_upscale_api/app/jobs.py` (as seções de worker supervisor e isolated worker) e `app/security.py` (secure tempdir) |
| Fase 2 — Identidade por instalação | ✅ Implementada e testada | `api/astros_upscale_api/app/security.py` (DPAPI + install identity) e a rota de identidade em `app/routes.py` |
| Fase 3 — Contas, licenciamento, cobrança | ✅ Implementada e testada (webhooks, ativação, autorização) — **não conectada a uma conta real de pagamento** | `api/astros_licensing_service/` (serviço novo e separado) |
| Fase 4 — Pacote protegido da lógica de orquestração | ✅ Implementada e testada — empacota código-fonte cifrado+assinado, não binário nativo (ver ressalva abaixo) | `api/astros_licensing_service/app/packages.py` (a seção de encriptação de pacote) e `app/routes.py` (serviço) + `api/astros_upscale_api/app/security.py` (a seção de protected loader, API) |
| Fase 5 — Runtime/anti-adulteração | ✅ Implementada e testada | `api/astros_upscale_api/app/security.py` (a seção de self-integrity check e a de protected loader) e `api/astros_licensing_service/app/licensing.py` (a seção de authorizations) |
| Fase 6 — Hardware opcional (TPM, VBS, atestação) | ⬜ Não implementada — o próprio documento (§3) já recomendava tratar como melhoria futura, não bloqueador |

### O que foi testado de verdade (não só revisado)

- Fase 1: job completo via processo isolado; cancelamento matando o subprocesso de fato (PID some na hora); worker novo sobe sozinho depois; recuperação de resíduo órfão na inicialização.
- Fase 2: chave privada no disco tem a assinatura de um blob DPAPI real (não é um no-op); mesma identidade sobrevive a reinício; assinatura/verificação funciona; payload adulterado é rejeitado.
- Fase 3: webhook do Stripe assinado de verdade (HMAC idêntico ao real) é aceito; payload adulterado e segredo errado são rejeitados; retry idempotente não duplica licença; limite de ativações simultâneas respeitado; autorização assinada verificada com a chave pública do serviço; anti-replay confirmado; revogação corta autorizações novas na hora.
- Fase 4: job real processado pela classe `Upscaler` carregada dinamicamente do pacote cifrado (não do import estático) — confirmado pelos logs do serviço (4 chamadas reais: versão → autorização → pacote → chave pública) e pela imagem de saída correta.
- Fase 5: worker recusa iniciar com `app/processing.py` (onde a classe `Upscaler` vive hoje) adulterado; volta a funcionar depois de restaurar e regenerar o manifesto; pedido de autorização para versão antiga é rejeitado (409).
- Regressão: com o serviço de licenciamento desligado (modo padrão, o que todo usuário real roda hoje), tudo continua funcionando exatamente como antes — job completo e cancelamento real.

### Dois bugs reais encontrados e corrigidos durante os próprios testes (não hipotéticos)

1. O processo isolado não tinha `LOCALAPPDATA`/`APPDATA`/`USERPROFILE` no ambiente restrito — não conseguia localizar a própria identidade quando o carregamento protegido (Fase 4) precisou dela.
2. `_accept_with_timeout` nunca expirava de verdade: `with ThreadPoolExecutor() as pool:` bloqueia no `shutdown()` esperando uma thread presa num `accept()` que nunca retornaria — um job ficava travado para sempre em vez de falhar em 45s. Corrigido fechando o listener no timeout (o que desbloqueia a thread) e usando `shutdown(wait=False)`.

### O que fica honestamente de fora, mesmo com as 5 fases prontas

- **"Compilação nativa" (Fase 4)** — o que foi implementado é código-fonte Python cifrado e assinado, carregado e executado em memória. Isso já entrega: nunca fica em claro em disco, verificação de assinatura antes de executar, vínculo criptográfico real com a instalação. O que NÃO entrega: opacidade de um binário nativo de verdade (um atacante com acesso ao processo em execução ainda consegue inspecionar bytecode Python em memória). Compilar de verdade (Nuitka ou reescrita em Rust) continua sendo um projeto de tooling à parte.
- **Revogação com fallback silencioso** — hoje, se a autorização falhar (licença revogada, por exemplo), o worker isolado cai de volta para o import estático local em vez de bloquear o processamento — porque o código estático ainda existe no repositório (é um repo de desenvolvimento). Numa build de produção real que não embarcasse mais `app/processing.py`, isso viraria bloqueio de verdade automaticamente. Essa é uma decisão de política (degradar vs. bloquear) que só faz sentido fechar quando houver uma build de produção real para testar contra.
- **Conta real de pagamento** — a verificação de assinatura HMAC do Stripe e do Mercado Pago foi testada com segredos e payloads gerados localmente, usando exatamente o mesmo algoritmo documentado por cada provedor. Nunca foi exercitada contra uma conta viva, porque não existe uma.
- **Hospedagem** — nada disso está publicado em lugar nenhum. `api/astros_licensing_service` roda local, com SQLite, pronto para virar um serviço de verdade quando houver onde hospedar.
- **Medidas complementares do §6** (inferência dividida — já descartada, watermark forense, diversificação binária, detecção de anomalia, camada contratual) — continuam só documentadas, nenhuma foi implementada.
- ~~**Integração com a interface do Electron** — o app ainda não tem nenhuma tela para inserir a chave de licença, ativar/gerenciar instalações, ou mostrar status de licença.~~ **Feito.** `interface/src/renderer/src/views/LicenseActivationView.vue` (tela de ativação/status) e `components/LicenseWidget.vue` (indicador compacto), sobre `store/license.ts` (wrapper fino em cima das rotas `/license/*` da API local descritas no §4.2 acima).

---

## 0. Achado crítico — leia antes de decidir investir nisso

Antes de desenhar qualquer proteção, verifiquei o que `api/astros_upscale/processing.py` realmente executa hoje. **Os 19 modelos registrados em `MODELS` são todos pesos públicos de terceiros**, baixados diretamente de URLs públicas do GitHub e do HuggingFace:

```
https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth
https://huggingface.co/Phips/4xNomos2_hq_dat2/resolve/main/4xNomos2_hq_dat2.safetensors
... (mais 16 modelos, todos com URL pública)
```

**Implicação direta**: qualquer pessoa no mundo já pode baixar exatamente esses arquivos `.pth`/`.safetensors`, sem precisar tocar no seu aplicativo, sem engenharia reversa nenhuma. Embrulhar esses pesos específicos em criptografia por instalação, executor assinado de curta duração, TPM etc. **não protege nada que já não seja público** — o "segredo" que estaria sendo defendido não existe nesses arquivos.

Isso não invalida a especificação — ela continua correta como arquitetura genérica de proteção de software. Mas para que o investimento (que é grande: dezenas de sistemas novos, um servidor de licenciamento, infraestrutura de assinatura) valha a pena, o ativo protegido precisa ser um destes:

1. **Modelos proprietários futuros** — pesos treinados ou fine-tunados internamente, ainda não publicados. Se isso está no roadmap, a arquitetura abaixo se aplica diretamente a eles.
2. **O pipeline de orquestração** (`processing.py`: lógica de tiling, seleção de modelo, pós-processamento, ajustes) — é código original seu, então é um ativo legítimo de proteger, mas por ser lógica (não um blob de pesos), a defesa mais eficaz é mantê-la **rodando no servidor**, não distribuí-la ofuscada no cliente (ver §6).
3. **A experiência/produto como serviço** (limitar quem pode rodar quantos jobs, monetização) — nesse caso o problema não é "esconder o código", é **controle de acesso e licenciamento**, que é uma arquitetura mais simples que DRM de binário.

**Recomendação**: antes da Fase 1, decida explicitamente qual desses três é o objetivo real. O restante deste documento assume o cenário mais exigente (existem ou existirão modelos/lógica genuinamente proprietários), mas cada fase indica o que pode ser pulado se o objetivo for só (3).

### 0.1 Decisão de escopo confirmada

Duas decisões já foram tomadas e o restante deste documento reflete elas:

1. **Os modelos (pesos) não precisam de proteção.** Confirmado — ficam exatamente como estão hoje: download público, sem criptografia, sem vínculo a instalação/licença. Isso elimina inteiramente a parte da especificação original sobre "modelo persistente" protegido, empacotamento de pesos por sessão, e a maior parte do custo da Fase 4 original.
2. **Só a lógica de orquestração precisa de proteção** — isto é, o código que decide *como* usar os modelos: estratégia de tiling e overlap (`tile_process()` em `api/astros_upscale/processing.py`), o limiar de tile e callback de progresso (`Upscaler` em `api/astros_upscale_api/app/processing.py`), e a aplicação de ajustes (denoise/sharpen/face recovery).
3. **O processamento continua rodando na GPU do usuário** — decisão explícita de manter a velocidade e não assumir custo de GPU em servidor. Isso significa que a inferência dividida (§6.1, a proteção mais forte do documento) **não é aplicável aqui**: se o cálculo pesado precisa acontecer na máquina do usuário, a lógica que o comanda também precisa estar presente ali, ainda que protegida. Nenhuma arquitetura torna isso 100% opaco — apenas eleva o custo e reduz a janela de exposição, conforme o §1.

Com isso, o escopo efetivo do projeto é: **Fase 1, Fase 2, uma Fase 4 bem mais enxuta (só a lógica, não pesos) e Fase 5**, mais uma **Fase 3 completa**, já que a decisão seguinte (§0.2) confirmou que vocês também querem controle de acesso por licença, não só proteção contra engenharia reversa.

### 0.2 Decisão de licenciamento/cobrança confirmada

Três decisões adicionais foram tomadas:

1. **Modelo de cobrança: licença perpétua (compra única).** Paga uma vez, usa para sempre — sem cobrança recorrente, sem gestão de ciclo de assinatura.
2. **Limite não é por imagem/job processado — é por licença.** Ou seja, não existe medidor de consumo (megapixel, job, modelo usado). O que a licença controla é **quem pode processar**, tipicamente por número de instalações simultâneas ativadas naquela licença — não volume de uso. Isso simplifica bastante a Fase 3: não precisa de um medidor de consumo por job, só de um controle de ativação/instalação.
3. **Pagamento via Stripe e/ou Mercado Pago.** Ambos suportam cobrança única (checkout hospedado, sem seu servidor tocar em dado de cartão). Stripe cobre cartão internacional com boa maturidade de webhooks; Mercado Pago cobre Pix e boleto, relevantes se o público for majoritariamente brasileiro. O desenho abaixo (§3, Fase 3) usa um adaptador para não prender o serviço de licenciamento a um provedor específico — dá para começar com só um dos dois e adicionar o outro depois.

Isso está detalhado na Fase 3 completa, abaixo.

---

## 1. Threat model e o que esta arquitetura realmente entrega

Conforme a própria especificação reconhece na "Regra de arquitetura": nenhuma proteção local impede um atacante com controle administrativo total, debugger de kernel ou máquina virtual instrumentada. O que esta arquitetura entrega é:

- Elevar o custo de extração casual (um usuário comum não consegue copiar o modelo/executor com um `cp`).
- Impedir reuso trivial entre instalações (pacote de uma máquina não abre em outra).
- Tornar o vazamento **atribuível** (com as medidas do §6, um vazamento pode ser rastreado até a licença de origem).
- Reduzir a janela de exposição (executor só existe em claro durante o job, não permanentemente em disco).
- Permitir revogação rápida (uma licença comprometida pode ser cortada em minutos, não em uma nova versão do app).

O que ela **não** entrega, e não deve ser vendido como entregando:
- Impossibilidade de engenharia reversa por um atacante dedicado com a máquina em mãos.
- Proteção contra um usuário com privilégios de administrador que usa um debugger de kernel/hypervisor para dump de memória durante a execução (o momento em que o executor está descriptografado em RAM é, por definição, o momento em que ele é legível).

---

## 2. Separação dos três componentes

```
┌─────────────────────────┐      ┌──────────────────────────────┐      ┌────────────────────────────┐
│  Aplicativo público      │      │  Executor local protegido      │      │  Serviço remoto novo        │
│  (Electron, hoje existe) │◄────►│  (processo nativo isolado, novo)│◄────►│  - contas/licenças/ativações│
│  - UI, fila, export      │ IPC  │  - contém SÓ a lógica de tiling/│ HTTPS│  - webhook de pagamento     │
│  - comunicação com API   │local │    ajustes/orquestração         │      │    (Stripe / Mercado Pago)  │
│  - baixa modelos públicos │      │  - carrega o modelo público via │      │  - emissão de autorização/  │
│    normalmente, sem DRM  │      │    o mesmo caminho de hoje      │      │    chave de sessão          │
└─────────────────────────┘      └──────────────────────────────┘      │  - assinatura do pacote da  │
                                                                          │    lógica + revogação       │
                                                                          └────────────────────────────┘
```

Ponto importante de escopo: **o `astros_upscale_api` atual (FastAPI local) não deve virar o serviço remoto**. Ele continua sendo a camada de orquestração local (fila, progresso, export) e passa a delegar só a execução do modelo ao processo isolado. O serviço remoto (Fase 3, §3) é um serviço novo e separado, com seu próprio banco de dados de licenças/instalações/transações — misturar com o `astros_upscale_api` quebraria a premissa de que segredos reais (chave de assinatura, dados de licença) nunca tocam a máquina do usuário.

---

## 3. Fases de implementação

Cada fase é entregável isoladamente e não depende de fases posteriores para ter valor.

### Fase 1 — Isolamento de processo (sem depender de servidor novo)
**O que entra:** mover a execução do modelo (hoje dentro do processo do `astros_upscale_api`) para um processo separado, filho, com IPC restrito (named pipe/socket local + token efêmero por sessão), sem shell, sem variáveis de ambiente completas, sem acesso arbitrário a disco. Diretório temporário privado com ACL restrita e nome aleatório para qualquer artefato que precise tocar disco. Limpeza determinística ao final/erro/cancelamento (a rotina de limpeza do job atual já existe parcialmente em `app/jobs.py` — esta fase estende ela).
**Por que primeiro:** não depende de nenhuma infraestrutura nova, é puramente engenharia local, e já reduz superfície de ataque (um bug no parsing de imagem não compromete o processo principal).
**Esforço relativo:** médio. **Depende de servidor de licenciamento:** não.

### Fase 2 — Identidade criptográfica por instalação
**O que entra:** geração de par de chaves na ativação, chave privada protegida por DPAPI/CNG (e TPM quando disponível), nunca enviada ao servidor. Isso é pré-requisito para tudo que envolve "vincular pacote à instalação" nas fases seguintes.
**Esforço relativo:** médio. **Depende de servidor:** parcialmente — precisa que exista *algum* endpoint remoto para registrar a chave pública da instalação (não precisa do sistema de licenciamento completo ainda).

### Fase 3 — Contas, licenciamento perpétuo e cobrança
**O que entra:** um serviço backend novo (fora do `astros_upscale_api`) com três responsabilidades:

1. **Cobrança.** Checkout de compra única via Stripe Checkout e/ou Mercado Pago Checkout Pro (hospedados pelo provedor — nenhum dado de cartão passa pelo seu servidor). Um adaptador (`PaymentProvider`) abstrai o evento "pagamento aprovado" do provedor específico, para não prender o schema de licença a um só gateway. Ao receber o webhook de pagamento aprovado, o serviço emite uma licença nova.
2. **Licenciamento.** Cada licença tem: id único, e-mail do titular, data de compra, referência da transação de pagamento, status (`ativa` / `revogada` / `reembolsada`), e um limite de instalações simultâneas (padrão configurável, ex.: 2). A licença **não guarda contador de jobs/imagens processadas** — não há medição de uso, conforme §0.2.
3. **Ativação e autorização de sessão.** No primeiro uso, o app pede ao usuário a chave da licença (recebida por e-mail após a compra), gera a identidade de instalação (Fase 2) e envia ambos ao serviço. O serviço vincula a instalação à licença, respeitando o limite de ativações simultâneas — se o limite já foi atingido, o usuário precisa liberar uma instalação antiga antes de ativar uma nova (fluxo de "gerenciar meus dispositivos", simples, sem precisar de um app completo de conta). A partir daí, toda emissão de autorização de curta duração (a mesma mecânica da especificação original — id único, expiração, modelo/versão/operação permitidos, instalação autorizada, limite de reuso, assinatura, proteção contra replay) passa a checar se a instalação solicitante está vinculada a uma licença `ativa`.
4. **Revogação.** Reembolso ou chargeback muda o status da licença para `revogada`/`reembolsada`; todas as instalações vinculadas perdem autorização na próxima renovação de sessão (a autorização já expira sozinha em curto prazo, então a propagação do corte é rápida — minutos, não uma nova versão do app).

**O que fica de fora deliberadamente**, por causa do §0.2: planos/tiers, ciclo de cobrança recorrente, medidor de consumo por job/megapixel, portal de assinatura. Se algum dia a cobrança evoluir para recorrente, o schema de licença (id, status, limite de instalações) já comporta isso sem redesenho — só passa a ter uma data de expiração além do status.

**Esforço relativo:** alto — é um serviço backend novo com banco de dados de licenças/instalações/transações, integração com pelo menos um provedor de pagamento e seus webhooks, e um fluxo de UI no app para inserir a chave de licença e gerenciar ativações.

### Fase 4 — Pacote temporário só da lógica de orquestração
**O que entra:** compilar/empacotar apenas o módulo de orquestração (tiling, blending, aplicação de ajustes — não o modelo, não os pesos) para código nativo (Nuitka, ou reescrita do hot path em Rust chamando a mesma lib de inferência via FFI), assinatura digital do pacote, criptografia vinculada à chave pública da instalação (Fase 2) e à autorização (Fase 3). Como o que está sendo empacotado é só a lógica (dezenas a poucas centenas de KB de código, não centenas de MB de pesos), o pacote é pequeno e rápido de emitir/baixar a cada sessão — isso é uma vantagem direta da decisão do §0.1.
**Esforço relativo:** alto, mas bem menor que a versão original da Fase 4 (que precisava lidar com empacotar pesos de modelo também).
**Depende de:** Fases 2 e 3 completas.

### Fase 5 — Proteção em runtime e anti-adulteração
**O que entra:** verificação de assinatura/hash/versão/revogação antes de executar, execução em memória sem cópia em claro em disco quando a plataforma permitir, apagamento criptográfico ao final (a chave de sessão é descartada, não o arquivo sobrescrito — coerente com a limitação de SSDs citada na especificação), watchdog no processo principal para matar executores órfãos.
**Esforço relativo:** alto, mas incremental sobre a Fase 1.

### Fase 6 — Hardware opcional (TPM, VBS, atestação remota)
**O que entra:** só quando disponível; degrada graciosamente para as fases anteriores em hardware sem suporte. Não deve ser prometido como "sempre ativo".
**Esforço relativo:** alto, e o retorno é marginal frente às Fases 1-5 — tratar como melhoria futura, não como bloqueador de lançamento.

---

## 4. Fluxos

### 4.1 Compra e ativação (uma vez, ou quando trocar de máquina)

1. Usuário compra no checkout hospedado (Stripe ou Mercado Pago) fora do app — pode ser uma página de vendas simples.
2. Webhook de pagamento aprovado chega ao serviço remoto → serviço cria a licença (`ativa`, e-mail do titular, limite de instalações padrão) e envia a chave de licença por e-mail.
3. No primeiro uso do app, usuário informa a chave de licença. App gera a identidade de instalação (Fase 2) e envia ao serviço junto com a chave.
4. Serviço vincula a instalação à licença, se o limite de ativações simultâneas não tiver sido atingido; caso contrário, pede que o usuário libere uma instalação antiga antes.

### 4.2 Sessão de processamento (a cada job)

1. App informa ao serviço remoto o id da instalação (já ativada) e pede autorização para rodar `{modelo, versão, operação}` específicos.
2. Serviço verifica: a instalação está vinculada a uma licença `ativa`? A versão é permitida? Não há revogação pendente? Se sim a tudo, emite autorização assinada de curto prazo + libera uma chave de sessão criptografada para a chave pública da instalação.
3. App baixa (se ainda não tiver em cache local criptografado) o pacote da lógica de orquestração para aquele modelo/versão/plataforma.
4. Processo isolado (Fase 1) descriptografa o pacote em memória usando a chave de sessão, valida assinatura/hash, executa o job usando apenas o descritor de arquivo/parâmetros que o processo principal repassou por IPC — o modelo em si é carregado normalmente, do caminho público de sempre.
5. Ao concluir (sucesso, erro ou cancelamento): processo isolado é encerrado, chave de sessão é destruída, quaisquer artefatos temporários são removidos, autorização é marcada como consumida localmente.
6. Watchdog do processo principal confirma que nada ficou órfão; na próxima inicialização, uma rotina varre e limpa resíduos de quedas anteriores.

Note que a licença é verificada uma vez por sessão de processamento (passo 2), não por imagem/job dentro da sessão — coerente com a decisão do §0.2 de não medir consumo.

---

## 5. O que muda no que já existe

| Componente atual | O que muda |
|---|---|
| `astros_upscale_api` (FastAPI local) | Deixa de rodar a lógica de tiling/ajustes no próprio processo; passa a orquestrar o processo isolado (Fase 1) e a se comunicar com o serviço remoto mínimo (Fase 3 simplificada) para obter a autorização/chave de sessão a cada job. |
| `api/astros_upscale/processing.py` | `tile_process()` e a lógica de blending/ajustes migram para o módulo protegido que roda dentro do executor isolado. O download e carregamento do peso do modelo em si **não muda** — continua público, sem DRM, exatamente como hoje. |
| Download de modelos (`MODELS` dict) | Sem alteração — continua público, sem criptografia, sem vínculo a instalação (confirmado no §0.1). |
| `app/jobs.py` | Ganha os hooks de limpeza determinística (chaves, processo, artefatos) e o registro do watchdog. |

---

## 6. Medidas complementares além da especificação original

Você pediu explicitamente outras formas de reduzir ainda mais o risco, além do que a especificação já cobre. Como o processamento foi confirmado como local (§0.1), a opção mais forte do conjunto original — inferência dividida no servidor — não é aplicável (exigiria mover o cálculo pesado para fora da máquina do usuário, o que foi descartado). As que seguem valendo, em ordem de custo-benefício:

1. **Detecção de anomalia no serviço remoto** — telemetria agregada (não conteúdo) de uso por instalação: a mesma identidade ativa em muitas máquinas/IPs simultâneos, volume fora do padrão, versão de executor inconsistente com o esperado. Isso pega compartilhamento e cracks *sem* depender de nenhuma proteção local ser perfeita — é o único controle que continua funcionando mesmo se o executor for totalmente quebrado.
2. **Marca d'água forense por instalação/execução** — embutir um identificador invisível (ou metadado esteganográfico) nas imagens processadas, amarrado à instalação que gerou o resultado. Não impede engenharia reversa, mas torna redistribuição do executor extraído rastreável até a origem — forte efeito dissuasório mesmo sem servidor de licenciamento completo.
3. **Diversificação binária (builds canário)** — gerar pequenas variações não funcionais entre pacotes de lógica emitidos para instalações diferentes (idêntico do lado de fora), permitindo atribuir um pacote vazado à instalação que o recebeu.
4. **Revogação rápida + janelas de validade curtas por padrão** — já está na especificação, mas vale reforçar como prioridade de implementação, não como opcional: é a defesa que mais rapidamente neutraliza um vazamento já ocorrido.
5. **Camada contratual (termos de uso)** — não é técnica, mas é barata e complementa tudo acima: sem ela, mesmo detectando abuso você não tem base para agir.
6. **Cadência de rotação** — trocar chaves/mecanismos de empacotamento com regularidade planejada. Não impede um crack pontual, mas encurta a vida útil de qualquer bypass encontrado, elevando o custo de manter um crack funcional ao longo do tempo.

Nenhuma dessas substitui as Fases 1-5; elas mudam o jogo de "impedir a cópia" (impossível de garantir 100%, como a própria especificação reconhece) para "tornar a cópia detectável, atribuível e rapidamente neutralizável" — que é uma garantia realista de se dar.

---

## 7. Próximo passo recomendado

Todo o escopo de produto está confirmado agora (§0.1 e §0.2): modelos públicos sem proteção, só a lógica de orquestração protegida, processamento na GPU do usuário, licença perpétua por compra única, controle por instalações ativadas (não por volume de uso), pagamento via Stripe e/ou Mercado Pago. A sequência de implementação recomendada, na ordem de menor risco/maior valor imediato:

1. **Fase 1 — Isolamento de processo.** Não depende de nada novo, já reduz superfície de ataque hoje, e é reaproveitada por todas as fases seguintes. Bom ponto de partida porque entrega valor mesmo se as fases seguintes atrasarem.
2. **Fase 2 — Identidade por instalação.** Pré-requisito técnico para a ativação de licença (§4.1) e para a Fase 4.
3. **Fase 3 — Serviço de contas/licenciamento/cobrança.** O item de maior esforço do conjunto — vale tratar como um projeto de backend à parte, com seu próprio levantamento de requisitos (schema de dados, escolha final entre Stripe/Mercado Pago/ambos, fluxo de e-mail de entrega da chave de licença, tela de "gerenciar meus dispositivos" no app). Vem depois das Fases 1-2 porque só faz sentido gatekeeping de licença sobre uma instalação que já tem identidade própria.
4. **Fase 4 — Pacote protegido da lógica de orquestração.** Depende de 2 e 3 estarem funcionando (precisa de instalação identificada e de autorização emitida para existir algo a proteger).
5. **Fase 5 — Runtime/anti-adulteração.** Fecha o ciclo, incremental sobre a Fase 1.

Cada fase, uma vez implementada, já entrega valor sozinha — não é necessário esperar o conjunto completo para começar. Quando quiser sair do documento e começar a implementar de fato, o próximo passo natural é decompor a Fase 1 em tarefas concretas.
