from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_files, routes_jobs, routes_models, ws_progress
from app.config import settings
from app.core import job_manager

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
app.include_router(ws_progress.router, tags=['ws'])


@app.on_event('startup')
async def on_startup():
    job_manager.start_worker()


@app.get('/health')
def health():
    return {'status': 'ok'}
