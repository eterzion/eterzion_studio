from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_files, routes_identity, routes_jobs, routes_models, routes_preview, ws_progress
from app.config import settings
from app.core import install_identity, job_manager, secure_tempdir, worker_supervisor

app = FastAPI(title='Astros Upscale API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(routes_jobs.router, prefix='/jobs', tags=['jobs'])
app.include_router(routes_models.router, prefix='/models', tags=['models'])
app.include_router(routes_files.router, tags=['files'])
app.include_router(routes_identity.router, prefix='/identity', tags=['identity'])
app.include_router(routes_preview.router, prefix='/preview', tags=['preview'])
app.include_router(ws_progress.router, tags=['ws'])


@app.on_event('startup')
async def on_startup():
    # Recovery routine (Fase 1 — isolamento de processo): remove worker scratch
    # dirs left behind by a forced shutdown, crash, or power loss in a previous run.
    secure_tempdir.cleanup_stale()
    job_manager.start_worker()
    # Fase 2 — identidade criptográfica por instalação: gera na primeira execução,
    # reaproveita nas seguintes. Feito na inicialização para falhar cedo e alto se
    # o DPAPI não estiver disponível, em vez de silenciosamente na primeira ativação.
    install_identity.ensure_identity()


@app.on_event('shutdown')
async def on_shutdown():
    worker_supervisor.shutdown()


@app.get('/health')
def health():
    return {'status': 'ok'}
