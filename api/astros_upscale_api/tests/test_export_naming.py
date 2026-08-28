"""Export file naming, and the guarantee that the source survives it.

The default output name is the source's own name. That is what people expect
and what they were renaming files by hand to get — but it also means the
default output path and the default input path are the same path, because the
default destination is the source's own folder. Principle XV calls that out by
name ("Output never lands on the input") and forbids resolving it by
overwriting, including when the caller explicitly asked for 'overwrite': that
instruction is about replacing some other file, not about destroying the
original being worked from.

The helpers are tested directly for the edge cases, and the guarantee itself is
tested through the real route — a test that stops at the helpers passes with the
guard deleted, which was the first version of this file.
"""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import routes
from app.routes import jobs_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


class TestSameFileDetection:
    def test_identical_path_is_the_same_file(self, tmp_path):
        source = tmp_path / 'foto.png'
        source.write_bytes(b'x')
        assert routes._is_same_file(str(source), str(source)) is True

    def test_a_different_name_in_the_same_folder_is_not(self, tmp_path):
        source = tmp_path / 'foto.png'
        source.write_bytes(b'x')
        assert routes._is_same_file(str(tmp_path / 'outra.png'), str(source)) is False

    def test_the_same_file_reached_by_a_messier_path_is_still_the_same_file(self, tmp_path):
        """`.` and `..` segments must not be a way past the check."""
        source = tmp_path / 'foto.png'
        source.write_bytes(b'x')
        detour = tmp_path / 'sub' / '..' / 'foto.png'
        (tmp_path / 'sub').mkdir()
        assert routes._is_same_file(str(detour), str(source)) is True

    def test_case_differences_are_the_same_file_on_a_case_insensitive_filesystem(self, tmp_path):
        """Windows: FOTO.png and foto.png are one file, and exporting to the
        other spelling would still land on the source."""
        source = tmp_path / 'foto.png'
        source.write_bytes(b'x')
        same = routes._is_same_file(str(tmp_path / 'FOTO.png'), str(source))
        assert same is (os.path.normcase('A') == os.path.normcase('a'))

    def test_a_path_that_does_not_exist_yet_is_compared_textually(self, tmp_path):
        """The normal case: the output has not been written, so samefile()
        cannot be asked and the textual comparison has to carry the check."""
        source = tmp_path / 'foto.png'
        source.write_bytes(b'x')
        assert routes._is_same_file(str(tmp_path / 'foto.png'), str(source)) is True


class TestSuffixing:
    def test_suffix_goes_before_the_extension(self):
        assert routes._suffixed(os.path.join('d', 'foto.png')) == os.path.join('d', 'foto_upscaled.png')

    def test_a_name_with_dots_keeps_only_the_real_extension(self):
        assert routes._suffixed('a.b.c.png').endswith('a.b.c_upscaled.png')

    def test_free_path_returns_the_name_itself_when_nothing_is_there(self, tmp_path):
        candidate = str(tmp_path / 'foto.png')
        assert routes._free_path(candidate) == candidate

    def test_free_path_counts_up_past_every_taken_name(self, tmp_path):
        (tmp_path / 'foto.png').write_bytes(b'x')
        (tmp_path / 'foto (1).png').write_bytes(b'x')
        (tmp_path / 'foto (2).png').write_bytes(b'x')
        assert routes._free_path(str(tmp_path / 'foto.png')) == str(tmp_path / 'foto (3).png')


class TestTheSourceIsNeverTheDestination:
    """Principle XV, through the real route.

    An earlier version of this class composed _is_same_file and _suffixed in a
    helper of its own and asserted on that. It passed with the guard deleted
    from routes.py — it was testing an imitation of the route, which protects
    nothing. These drive POST /jobs/{id}/export and read the filesystem
    afterwards.
    """

    @staticmethod
    def _done_job(client, jobs_module, fake_supervisor, input_path):
        import asyncio

        fake_supervisor.configure_result((10, 10), (20, 20))
        body = {
            'media_request': {
                'media_type': 'image', 'operation': 'enhance',
                'content_type_override': 'photo', 'scale': '4x',
                'input_path': input_path,
            }
        }
        job_id = client.post('/jobs/local', json=body).json()['id']
        jobs_module.jobs[job_id]['status'] = 'queued'
        asyncio.run(jobs_module._process_job(job_id))
        assert jobs_module.get_job(job_id)['status'] == 'done'
        return job_id

    def test_default_export_does_not_land_on_the_source(
        self, client, real_input_file, fake_supervisor
    ):
        """No filename and no output_dir: both default to the source's own,
        which is exactly the collision Principle XV is about."""
        from app import jobs as jobs_module

        before = open(real_input_file, 'rb').read()
        job_id = self._done_job(client, jobs_module, fake_supervisor, real_input_file)

        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'conflict': 'overwrite',
        })
        assert res.status_code == 200
        output_path = res.json()['output_path']

        assert not routes._is_same_file(output_path, real_input_file)
        assert output_path.endswith('_upscaled.png')
        assert open(real_input_file, 'rb').read() == before, 'a origem foi alterada'

    def test_explicit_overwrite_of_the_source_name_still_spares_the_source(
        self, client, real_input_file, fake_supervisor
    ):
        """Naming the source file outright, with conflict='overwrite'. The
        instruction is honoured for other files; it never gets to mean "destroy
        what I am working from"."""
        from app import jobs as jobs_module

        before = open(real_input_file, 'rb').read()
        job_id = self._done_job(client, jobs_module, fake_supervisor, real_input_file)

        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'conflict': 'overwrite',
            'output_dir': os.path.dirname(real_input_file),
            'filename': os.path.basename(real_input_file),
        })
        assert res.status_code == 200
        assert open(real_input_file, 'rb').read() == before, 'a origem foi sobrescrita'

    def test_a_different_folder_keeps_the_plain_source_name(
        self, client, real_input_file, fake_supervisor, tmp_path
    ):
        """The point is to avoid the file, not the name: somewhere else, the
        export is simply called what the source is called."""
        from app import jobs as jobs_module

        job_id = self._done_job(client, jobs_module, fake_supervisor, real_input_file)
        out_dir = tmp_path / 'out'
        out_dir.mkdir()

        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'conflict': 'rename',
            'output_dir': str(out_dir),
        })
        assert res.status_code == 200
        assert os.path.basename(res.json()['output_path']) == 'input.png'
