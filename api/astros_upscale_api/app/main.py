from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import jobs, security
from app.config import settings
from app.routes import (components_router, files_router, identity_router, jobs_router, license_router,
                        preview_router, ws_router)

app = FastAPI(title='Astros Upscale API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(jobs_router, prefix='/jobs', tags=['jobs'])
app.include_router(components_router, prefix='/components', tags=['components'])
app.include_router(files_router, tags=['files'])
app.include_router(identity_router, prefix='/identity', tags=['identity'])
app.include_router(preview_router, prefix='/preview', tags=['preview'])
app.include_router(license_router, prefix='/license', tags=['license'])
app.include_router(ws_router, tags=['ws'])


@app.on_event('startup')
async def on_startup():
    # Recovery routine (Fase 1 — isolamento de processo): remove worker scratch
    # dirs left behind by a forced shutdown, crash, or power loss in a previous run.
    security.cleanup_stale()
    jobs.start_worker()
    # Fase 2 — identidade criptográfica por instalação: gera na primeira execução,
    # reaproveita nas seguintes. Feito na inicialização para falhar cedo e alto se
    # o DPAPI não estiver disponível, em vez de silenciosamente na primeira ativação.
    security.ensure_identity()


@app.on_event('shutdown')
async def on_shutdown():
    jobs.shutdown()


@app.get('/health')
def health():
    return {'status': 'ok'}
