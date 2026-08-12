"""Tests for secure_tempdir.py — private, ACL-restricted scratch directories
for the isolated worker. Real filesystem operations (including the real
icacls call on Windows) against a temp root, not mocked."""
from __future__ import annotations

import os

import pytest

from app import security as secure_tempdir


@pytest.fixture(autouse=True)
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / 'astros-upscale-worker'
    monkeypatch.setattr(secure_tempdir, '_base_root', lambda: str(root))
    return root


class TestCreatePrivateDir:
    def test_creates_a_real_directory(self, isolated_root):
        path = secure_tempdir.create_private_dir()
        assert os.path.isdir(path)
        assert str(isolated_root) in path

    def test_each_call_returns_a_distinct_directory(self, isolated_root):
        a = secure_tempdir.create_private_dir()
        b = secure_tempdir.create_private_dir()
        assert a != b
        assert os.path.isdir(a)
        assert os.path.isdir(b)

    def test_restricts_permissions_without_raising(self, isolated_root):
        """restrict_to_current_user is best-effort (icacls on Windows) — a
        real call must complete without throwing, whether or not it actually
        succeeds in this sandboxed test environment."""
        path = secure_tempdir.create_private_dir()
        secure_tempdir.restrict_to_current_user(path)  # must not raise


class TestRemoveDir:
    def test_removes_an_existing_directory_and_its_contents(self, isolated_root):
        path = secure_tempdir.create_private_dir()
        with open(os.path.join(path, 'file.txt'), 'w', encoding='utf-8') as fh:
            fh.write('data')
        secure_tempdir.remove_dir(path)
        assert not os.path.exists(path)

    def test_is_a_no_op_for_a_missing_directory(self, tmp_path):
        secure_tempdir.remove_dir(str(tmp_path / 'does-not-exist'))  # must not raise


class TestCleanupStale:
    def test_removes_directories_older_than_max_age(self, isolated_root):
        path = secure_tempdir.create_private_dir()
        old_time = 0  # epoch — guaranteed to be "old" under any max_age
        os.utime(path, (old_time, old_time))

        removed = secure_tempdir.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert not os.path.exists(path)

    def test_keeps_recent_directories(self, isolated_root):
        path = secure_tempdir.create_private_dir()  # just created, mtime is now
        removed = secure_tempdir.cleanup_stale(max_age_seconds=3600)
        assert removed == 0
        assert os.path.exists(path)

    def test_removes_a_dir_with_a_dead_pid_regardless_of_age(self, isolated_root):
        """A worker.pid file pointing at a process that no longer exists is
        crash residue, even if it's only a few seconds old — real detection
        via a real (nonexistent) PID, not a mocked process table."""
        path = secure_tempdir.create_private_dir()
        with open(os.path.join(path, 'worker.pid'), 'w', encoding='utf-8') as fh:
            fh.write('999999999')  # a PID essentially guaranteed not to exist

        removed = secure_tempdir.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert not os.path.exists(path)

    def test_returns_zero_when_root_does_not_exist_yet(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secure_tempdir, '_base_root', lambda: str(tmp_path / 'never-created'))
        assert secure_tempdir.cleanup_stale() == 0

    def test_handles_multiple_stale_and_fresh_dirs_together(self, isolated_root):
        stale = secure_tempdir.create_private_dir()
        os.utime(stale, (0, 0))
        fresh = secure_tempdir.create_private_dir()

        removed = secure_tempdir.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert not os.path.exists(stale)
        assert os.path.exists(fresh)


class TestPidAlive:
    def test_current_process_is_alive(self):
        assert secure_tempdir._pid_alive(os.getpid()) is True

    def test_a_very_unlikely_pid_is_not_alive(self):
        assert secure_tempdir._pid_alive(999999999) is False
