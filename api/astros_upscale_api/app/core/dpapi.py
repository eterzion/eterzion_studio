"""Thin ctypes wrapper around Windows DPAPI (crypt32.dll's CryptProtectData /
CryptUnprotectData) — no pywin32 dependency needed for this.

DPAPI ties the encrypted blob to the current Windows user profile: only the
same user account on the same machine can decrypt it (no password/key of ours
to manage or leak). Used by install_identity.py to keep the installation's
private key unreadable at rest without ever sending it anywhere — see
docs/processing-protection-architecture.md, Fase 2.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if sys.platform == 'win32':
    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def _to_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array]:
        buf = ctypes.create_string_buffer(data, len(data))
        blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        return blob, buf  # caller must keep buf alive for the call's duration

    def _from_blob(blob: _DATA_BLOB) -> bytes:
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            _kernel32.LocalFree(blob.pbData)

    def protect(data: bytes, entropy: bytes | None = None) -> bytes:
        """Encrypts data for the current Windows user only."""
        blob_in, buf_in = _to_blob(data)
        blob_out = _DATA_BLOB()
        entropy_blob = entropy_buf = None
        entropy_ptr = None
        if entropy is not None:
            entropy_blob, entropy_buf = _to_blob(entropy)
            entropy_ptr = ctypes.byref(entropy_blob)
        ok = _crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, entropy_ptr, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(f'CryptProtectData falhou: {ctypes.get_last_error()}')
        return _from_blob(blob_out)

    def unprotect(data: bytes, entropy: bytes | None = None) -> bytes:
        """Decrypts data previously encrypted by protect() under the same user."""
        blob_in, buf_in = _to_blob(data)
        blob_out = _DATA_BLOB()
        entropy_blob = entropy_buf = None
        entropy_ptr = None
        if entropy is not None:
            entropy_blob, entropy_buf = _to_blob(entropy)
            entropy_ptr = ctypes.byref(entropy_blob)
        ok = _crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, entropy_ptr, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(f'CryptUnprotectData falhou: {ctypes.get_last_error()}')
        return _from_blob(blob_out)

else:
    def protect(data: bytes, entropy: bytes | None = None) -> bytes:  # noqa: ARG001
        raise NotImplementedError('DPAPI só existe no Windows.')

    def unprotect(data: bytes, entropy: bytes | None = None) -> bytes:  # noqa: ARG001
        raise NotImplementedError('DPAPI só existe no Windows.')


def is_available() -> bool:
    return sys.platform == 'win32'
