"""Entrypoint for the packaged binary (see eterzion-studio-api.spec) and for running
the API directly with `python run.py` instead of `uvicorn app.main:app`.
"""
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()

    import logging

    import uvicorn

    from app.config import settings
    from app.main import app

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    uvicorn.run(app, host='127.0.0.1', port=settings.port, log_config=None)
