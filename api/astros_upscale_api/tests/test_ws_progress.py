"""Tests for ws_progress.py — the WebSocket job progress stream. Uses
TestClient's real websocket_connect (a real WebSocket handshake and protocol
exchange over the ASGI test transport, not a mock)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ws_progress
from app.core import job_manager


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ws_progress.router)
    return TestClient(app)


class TestJobProgressWebSocket:
    def test_closes_with_4404_for_unknown_job(self, client):
        with pytest.raises(Exception):  # starlette raises WebSocketDisconnect on the client side
            with client.websocket_connect('/ws/jobs/job_ghost') as ws:
                ws.receive_json()

    def test_sends_initial_state_immediately(self, client, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'
        job_manager.jobs[job_id]['queue_order'] = 1

        with client.websocket_connect(f'/ws/jobs/{job_id}') as ws:
            first = ws.receive_json()
            assert first['id'] == job_id
            assert first['status'] == 'queued'

    def test_initial_state_excludes_internal_fields(self, client, real_input_file, default_job_params):
        """Same privacy boundary as the REST /jobs/{id} response — the local
        filesystem input_path must not leak over the websocket either."""
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())

        with client.websocket_connect(f'/ws/jobs/{job_id}') as ws:
            first = ws.receive_json()
            assert 'input_path' not in first
            assert 'queue_order' not in first

    def test_relays_a_progress_update_pushed_via_notify(self, client, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())

        with client.websocket_connect(f'/ws/jobs/{job_id}') as ws:
            ws.receive_json()  # initial state
            job_manager.jobs[job_id]['status'] = 'processing'
            job_manager.jobs[job_id]['progress'] = 42
            job_manager._notify(job_id)

            update = ws.receive_json()
            assert update['status'] == 'processing'
            assert update['progress'] == 42

    def test_closes_the_stream_after_a_terminal_status(self, client, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())

        with client.websocket_connect(f'/ws/jobs/{job_id}') as ws:
            ws.receive_json()  # initial state
            job_manager.jobs[job_id]['status'] = 'done'
            job_manager._notify(job_id)
            final = ws.receive_json()
            assert final['status'] == 'done'

            # the server closes right after a terminal status — no further
            # message follows, and the subscriber must have been cleaned up.
            assert job_manager._listeners.get(job_id, []) == [] or job_id not in job_manager._listeners

    def test_unsubscribes_on_client_disconnect(self, client, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())

        with client.websocket_connect(f'/ws/jobs/{job_id}') as ws:
            ws.receive_json()

        # after the `with` block closes the connection, the server-side
        # subscriber queue must not still be registered — otherwise it's a
        # leak that grows with every reconnect.
        assert job_manager._listeners.get(job_id, []) == []
