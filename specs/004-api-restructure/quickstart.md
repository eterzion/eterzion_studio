# Quickstart: validação da consolidação estrutural de api/

Guia de validação a rodar depois da implementação (`/speckit-implement`), antes de considerar a
feature concluída. Cada passo mapeia para um Success Criterion de `spec.md`.

## 1. Contagem de arquivos por subprojeto (SC-001, SC-002, SC-003)

```bash
cd api
find astros_upscale_api/app -name "*.py" ! -name "__init__.py" | wc -l   # <= 8 (main, config,
                                                                            # routes, processing,
                                                                            # jobs, licensing,
                                                                            # security, schemas)
find astros_licensing_service/app -name "*.py" ! -name "__init__.py" | wc -l  # <= 7 (main,
                                                                                 # config,
                                                                                 # database,
                                                                                 # licensing,
                                                                                 # packages,
                                                                                 # payments,
                                                                                 # routes)
find astros_upscale -name "*.py" ! -name "__init__.py" -not -path "*/tests/*" | wc -l   # <= 3
                                                                                           # (processing,
                                                                                           # media,
                                                                                           # optimize)
find astros_upscale_api/app/api astros_upscale_api/app/core astros_upscale_api/app/models \
     astros_licensing_service/app/payments 2>/dev/null   # deve retornar "No such file or
                                                            # directory" para todos — diretórios
                                                            # removidos
```

## 2. Zero referência residual a caminho antigo (SC-006)

```bash
cd api
grep -rln "app\.core\.\|app\.api\.\|app\.models\.\|from app import core\|from app import api\|from app import models" \
  astros_upscale_api --include="*.py"   # deve retornar vazio
grep -rln "app\.db\b\|app\.package_crypto\|from app import db\b" \
  astros_licensing_service --include="*.py"   # deve retornar vazio
grep -rln "from astros_upscale\.core\|from astros_upscale\.audio\|from astros_upscale\.content_type\|from astros_upscale\.face_enhance\|from astros_upscale\.hardware\|from astros_upscale\.media_engine\|from astros_upscale\.utils\." \
  . --include="*.py"   # deve retornar vazio
```

## 3. Suíte de testes sem regressão (SC-004, SC-005)

```bash
cd api/astros_upscale && ../../.venv/Scripts/python.exe -m pytest --collect-only -q | tail -1
cd api/astros_upscale_api && ../../.venv/Scripts/python.exe -m pytest --collect-only -q | tail -1
cd api/astros_licensing_service && ../../.venv/Scripts/python.exe -m pytest --collect-only -q | tail -1
```

Comparar a contagem de testes coletados com a linha de base capturada antes da reorganização —
deve ser idêntica (nenhum teste removido). Depois, rodar a suíte completa — **sempre com
`-n auto`** (pytest-xdist, já uma dependência de `requirements-dev.txt` de ambas as APIs e já
usado por `.github/workflows/tests.yml`): sem paralelização, a suíte de `astros_upscale_api`
sozinha varia de ~40s a vários minutos dependendo do estado do ambiente (imports pesados de
torch, detecção real de hardware, chamadas reais a ffmpeg); com `-n auto` cai para ~30s
de forma consistente. **Nunca rodar sem `-n auto` — é isso que mantém a validação local dentro
de minutos, não do tempo variável e às vezes muito mais longo do modo serial.**

```bash
cd api
../.venv/Scripts/python.exe -m pytest astros_upscale_api/tests -m "not slow" -n auto --no-cov -q
../.venv/Scripts/python.exe -m pytest astros_upscale/tests astros_licensing_service/tests \
  -m "not slow" -n auto --no-cov -q
```

(as duas invocações ficam separadas porque `astros_upscale_api` e `astros_licensing_service`
têm, cada uma, seu próprio pacote Python chamado `app` — rodar as três subpastas em uma única
invocação `pytest` faz a coleta colidir entre os dois `sys.path`/`app`, uma limitação
arquitetural pré-existente e independente desta reorganização, documentada em
`research.md`/`tasks.md` T040.)

Resultado esperado: as duas invocações juntas somam 100% dos testes verdes em menos de um
minuto no total nesta máquina (32 núcleos); mesmo em hardware mais modesto, `-n auto` deve manter
o total bem abaixo de 5 minutos.

## 4. Import básico dos dois serviços (User Story 4)

```bash
cd api/astros_upscale_api && ../../.venv/Scripts/python.exe -c "import app.main"
cd api/astros_licensing_service && ../../.venv/Scripts/python.exe -c "import app.main"
```

Nenhum erro de import (circular ou de caminho) deve ocorrer — confirma que a ordem de
consolidação (`research.md` Decisões 2 e 3) foi respeitada.

## 5. Docker/PyInstaller (se disponível no ambiente)

```bash
docker build -t astros-upscale-api-test api/astros_upscale_api
docker build -t astros-licensing-service-test api/astros_licensing_service
```

Se Docker não estiver disponível no ambiente de validação, registrar essa limitação
explicitamente no relatório final em vez de omitir o passo.
