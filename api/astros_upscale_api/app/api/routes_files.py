import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core import job_manager

router = APIRouter()


@router.get('/jobs/{job_id}/download')
def download_job_output(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    if job['status'] != 'done' or not job['output_path']:
        raise HTTPException(409, 'Job ainda não foi concluído.')
    if not os.path.isfile(job['output_path']):
        raise HTTPException(410, 'Arquivo de saída não existe mais.')
    return FileResponse(job['output_path'], filename=os.path.basename(job['output_path']))
