"""Standalone entry point for the audio-worker isolated process (SonicMaster).

Run as `<audio-worker-python> worker_main.py <pipe-address>` by
app/jobs.py's `get_audio_worker_supervisor()`. Deliberately has ZERO imports
from `eterzion_upscale_api`'s own `app` package — this script runs inside a
separate, isolated Python environment (audio_worker_requirements.txt) that
does not have that package installed. It only depends on the standard
library and this same `vendor/sonicmaster/` directory (`infer.py`).

Implements the same named-pipe IPC subset app/jobs.py's own worker uses
(Client, authkey from ASTROS_WORKER_AUTHKEY, a small message loop) so the
parent-side WorkerSupervisor mechanism works unmodified for both workers —
only the message *types* handled here differ (restore/restore_full_song
instead of process).
"""
from __future__ import annotations

import os
import sys
import traceback
from multiprocessing.connection import Client
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from infer import run_single_inference  # noqa: E402 — after sys.path fix, see above


def _handle_restore(msg: dict, send) -> None:
    output_path = run_single_inference(
        ckpt=msg['ckpt'],
        input_path=msg['input_path'],
        prompt=msg['prompt'],
        output_path=msg['output_path'],
        chunk_duration=msg.get('chunk_duration', 30),
        overlap_duration=msg.get('overlap_duration', 10),
        num_inference_steps=msg.get('num_inference_steps', 10),
        guidance_scale=msg.get('guidance_scale', 1.0),
        seed=msg.get('seed', 0),
        hf_token=msg.get('hf_token') or None,
    )
    send({'type': 'result', 'output_path': output_path})


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: worker_main.py <pipe-address>', file=sys.stderr)
        sys.exit(2)
    address = sys.argv[1]
    authkey = os.environ.get('ASTROS_WORKER_AUTHKEY', '')
    if not authkey:
        print('ASTROS_WORKER_AUTHKEY not set', file=sys.stderr)
        sys.exit(2)

    conn = Client(address, authkey=authkey.encode('utf-8'))
    try:
        while True:
            try:
                msg = conn.recv()
            except (EOFError, OSError):
                break
            msg_type = msg.get('type')
            if msg_type == 'shutdown':
                break
            if msg_type == 'ping':
                conn.send({'type': 'pong'})
                continue
            if msg_type == 'restore':
                try:
                    _handle_restore(msg, conn.send)
                except Exception:  # noqa: BLE001 - last-resort guard, worker must survive
                    traceback.print_exc(file=sys.stderr)
                    conn.send({'type': 'error', 'message': 'Falha interna do audio-worker.',
                               'error_class': 'AudioWorkerCrash'})
    finally:
        conn.close()


if __name__ == '__main__':
    main()
