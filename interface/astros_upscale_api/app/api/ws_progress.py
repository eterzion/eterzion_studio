import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import job_manager

router = APIRouter()


@router.websocket('/ws/jobs/{job_id}')
async def job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()

    job = job_manager.get_job(job_id)
    if job is None:
        await websocket.close(code=4404)
        return

    await websocket.send_json(_public_view(job))

    queue = job_manager.subscribe(job_id)
    try:
        while True:
            update = await queue.get()
            await websocket.send_json(_public_view(update))
            if update['status'] in ('done', 'error', 'cancelled'):
                break
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        job_manager.unsubscribe(job_id, queue)


def _public_view(job: dict) -> dict:
    view = {k: v for k, v in job.items() if k not in ('input_path', 'queue_order')}
    view.setdefault('queue_position', job_manager.queue_position(job['id']))
    return view
