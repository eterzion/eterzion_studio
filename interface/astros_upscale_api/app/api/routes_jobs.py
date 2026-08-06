import os

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.config import settings
from app.core import job_manager
from app.models.schemas import ExportRequest, JobParams, LocalJobRequest

router = APIRouter()

_INTERNAL_FIELDS = ('input_path', 'queue_order')


@router.post('')
async def create_job(file: UploadFile, params: str = Form(default='{}')):
    job_params = JobParams.model_validate_json(params)

    os.makedirs(settings.uploads_dir, exist_ok=True)
    dest_path = os.path.join(settings.uploads_dir, file.filename)
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Arquivo maior que o limite de {settings.max_upload_mb} MB.')
    with open(dest_path, 'wb') as fh:
        fh.write(content)

    job_id = job_manager.create_job(dest_path, file.filename, job_params.model_dump())
    return {'id': job_id}


@router.post('/local')
def create_job_local(payload: LocalJobRequest):
    """Same as POST /jobs, but for when the API and the client share a filesystem
    (the Electron desktop app): points the job straight at a path already on disk
    instead of uploading the file's bytes over HTTP."""
    if not os.path.isfile(payload.input_path):
        raise HTTPException(404, 'Arquivo não encontrado no caminho informado.')
    filename = os.path.basename(payload.input_path)
    job_id = job_manager.create_job(payload.input_path, filename, payload.params.model_dump())
    return {'id': job_id}


@router.get('')
def list_jobs():
    return {'jobs': [_public_view(job) for job in job_manager.list_jobs()]}


@router.get('/{job_id}')
def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    return _public_view(job)


@router.delete('/{job_id}')
def delete_job(job_id: str):
    if not job_manager.cancel_job(job_id):
        raise HTTPException(404, 'Job não encontrado.')
    return {'ok': True}


@router.patch('/{job_id}/params')
def update_job_params(job_id: str, params: dict):
    if not job_manager.update_params(job_id, params):
        raise HTTPException(409, 'Job não encontrado ou já iniciado.')
    return _public_view(job_manager.get_job(job_id))


@router.post('/{job_id}/process')
async def process_job(job_id: str):
    if not await job_manager.enqueue(job_id):
        raise HTTPException(409, 'Job não encontrado ou já processado.')
    return {'ok': True}


@router.post('/{job_id}/export')
def export_job(job_id: str, payload: ExportRequest):
    """Re-encodes a done job's already-upscaled result to the requested format,
    quality and destination. Never re-runs the model (see upscaler.py/job_manager.py)."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    if job['status'] != 'done':
        raise HTTPException(409, 'Job ainda não foi concluído.')

    ext = '.' + payload.format.lstrip('.')
    name = payload.filename or os.path.splitext(job['input_file'])[0] + '_upscaled' + ext
    if not name.lower().endswith(ext):
        name = os.path.splitext(name)[0] + ext
    output_dir = payload.output_dir or os.path.dirname(job['input_path']) or settings.outputs_dir
    output_path = os.path.join(output_dir, name)

    if os.path.exists(output_path):
        if payload.conflict == 'ask':
            raise HTTPException(409, {'reason': 'conflict', 'path': output_path})
        if payload.conflict == 'rename':
            base, ext2 = os.path.splitext(output_path)
            n = 1
            while os.path.exists(output_path):
                output_path = f'{base} ({n}){ext2}'
                n += 1
        # 'overwrite' falls through and just writes over it

    try:
        job_manager.export_job(job_id, output_path, payload.quality)
    except ValueError as error:
        raise HTTPException(409, str(error))
    return {'output_path': output_path}


def _public_view(job: dict) -> dict:
    view = {k: v for k, v in job.items() if k not in _INTERNAL_FIELDS}
    view['queue_position'] = job_manager.queue_position(job['id'])
    return view
