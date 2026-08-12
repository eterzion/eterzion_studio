# Quickstart: validação da reorganização api/ + interface/

Guia de validação ponta a ponta a rodar depois da implementação (`/speckit-implement`), antes de
considerar a feature concluída. Cada passo mapeia para um Success Criterion de `spec.md`.

## Pré-requisitos

- Repositório já reorganizado (`api/` e `interface/` na raiz, conforme `plan.md`).
- `.venv` na raiz com `api/astros_upscale` instalado em modo editável (`pip install -e ./api`, ou
  equivalente decidido em `tasks.md`).

## 1. Estrutura (SC-001)

```bash
ls /                     # deve mostrar apenas api/, interface/, models/, docs/, scripts/,
                          # specs/, .specify/, .github/, README.md, LICENSE, .gitignore — nenhuma
                          # outra pasta de código-fonte de aplicação
```

## 2. Suíte de testes (SC-002)

```bash
cd api/astros_upscale && pytest                    # 7 arquivos, testava astros_upscale direto
cd api/astros_upscale_api && pytest -m "not slow"   # 28 arquivos
cd api/astros_licensing_service && pytest           # 6 arquivos
```

Todos devem passar. Nenhuma contagem de teste deve ser menor que antes da migração.

## 3. Nenhuma referência ao caminho antigo (SC-003)

```bash
grep -rn "interface/astros_upscale_api" --include="*.py" --include="*.ts" --include="*.yml" .
grep -rn "interface/astros_licensing_service" --include="*.py" --include="*.ts" --include="*.yml" .
grep -rn "astros_upscale\.cli" --include="*.py" .
```

Cada comando deve retornar vazio (exceto ocorrências dentro de `specs/`/documentação histórica,
que são texto, não referência funcional).

## 4. Toda funcionalidade da CLI acessível via API (SC-004)

Referência: tabela "cli.py command handlers vs API routes" em `research.md`. Para cada linha,
chamar a rota HTTP correspondente (ex.: `POST /components/{id}/install` para o antigo `models
download`) e confirmar resposta 2xx equivalente ao resultado do comando de terminal original.

## 5. API inicializa a partir do novo caminho (parte de SC-005)

```bash
cd api/astros_upscale_api && python run.py     # deve subir em http://127.0.0.1:8765
cd api/astros_licensing_service && python run.py  # deve subir em http://127.0.0.1:8766, processo separado
```

## 6. Interface inicia e conecta à API (SC-005)

```bash
cd interface && pnpm install && pnpm dev   # ou o comando de dev já existente
```

Abrir o app Electron: a API local deve subir automaticamente (via `apiProcess.ts` resolvendo o
novo caminho), sem nenhuma configuração manual.

## 7. Nenhuma regressão visual/funcional (SC-006)

Percorrer manualmente, no app aberto no passo 6:
- Ativação de licença (fluxo completo, contra `api/astros_licensing_service` local).
- Importação de um arquivo de imagem/vídeo/áudio e processamento via fila.
- Exportação do resultado.
- Tela de Configurações e Créditos.

Nenhuma tela deve apresentar diferença visual ou de comportamento perceptível em relação ao estado
antes da migração.

## 8. Serviço de licenciamento como processo independente, sem perda de dados (SC-007)

```bash
cd api/astros_licensing_service && python run.py   # sozinho, sem a API local rodando
curl http://127.0.0.1:8766/health
```

Confirmar que o SQLite (`api/astros_licensing_service/storage/licensing.db`) contém os mesmos
registros de antes da migração (mesma contagem de linhas em `licenses`/`installations`/
`authorizations`/`packages`, comparando com um backup tirado antes da migração).

## 9. Nenhum import cruzado indevido (contrato estrutural)

```bash
grep -rn "^from app" interface/          # deve retornar vazio — interface nunca importa módulo Python
grep -rln "from astros_licensing_service\|import astros_licensing_service" api/astros_upscale_api/
                                          # deve retornar vazio — API local nunca importa o licensing service
```
