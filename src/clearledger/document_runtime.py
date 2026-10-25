"""Parser process limits and immutable local originals. No user-controlled paths."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from uuid import UUID

from clearledger.document_contract import MAX_DOCUMENT_BYTES, ExtractionError

WORKER_SLOTS = threading.BoundedSemaphore(2)


def parse_bounded(raw: bytes, mime: str) -> dict:
    return run_worker(
        "clearledger.document_worker",
        {
            "bytes": base64.b64encode(raw).decode("ascii"),
            "mime": mime,
        },
    )


def run_worker(module: str, payload: dict, timeout: float = 10) -> dict:
    if module not in {"clearledger.document_worker", "clearledger.gemini_worker"}:
        raise ExtractionError("WORKER_MODULE_NOT_ALLOWED")
    if not WORKER_SLOTS.acquire(blocking=False):
        raise ExtractionError("WORKER_BUSY")
    try:
        return _run_worker(module, payload, timeout)
    finally:
        WORKER_SLOTS.release()


def _run_worker(module: str, payload: dict, timeout: float) -> dict:
    # No .env, DB URL, API keys, home/profile or application configuration in this child.
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-I", "-B", "-m", module],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    job = None
    try:
        if os.name == "nt":
            job = windows_memory_job(process)
        body = json.dumps(payload).encode()
        output, _ = process.communicate(body, timeout=timeout)
        if process.returncode or len(output) > 1_000_000:
            raise ExtractionError("PARSER_RESOURCE_FAILURE")
        result = json.loads(output)
        if "error" in result and module == "clearledger.document_worker":
            raise ExtractionError(result["error"])
        return result
    except subprocess.TimeoutExpired:
        raise ExtractionError("PARSER_TIMEOUT") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        if job is not None:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(job)


def windows_memory_job(process):
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "read_ops",
                "write_ops",
                "other_ops",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", IO),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.windll.kernel32
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x100 | 0x200 | 0x2000 | 0x8  # MEMORY | KILL_ON_CLOSE | ACTIVE_PROCESS
    # Windows venv python.exe is a redirector: it launches the actual interpreter.
    limits.basic.active = 2
    limits.process_memory = 512 * 1024**2
    limits.job_memory = 512 * 1024**2
    handle = kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
    try:
        if (
            not job
            or not handle
            or not kernel.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            or not kernel.AssignProcessToJobObject(job, handle)
        ):
            if job:
                kernel.CloseHandle(job)
            raise ExtractionError("PARSER_SANDBOX_UNAVAILABLE")
    finally:
        if handle:
            kernel.CloseHandle(handle)
    return job


class LocalOriginals:
    def __init__(self, root: Path):
        self.root = root.absolute()

    def path(self, organization_id: UUID, sha: str) -> Path:
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ExtractionError("INVALID_STORAGE_KEY")
        path = self.root / str(organization_id) / sha
        if any(value.is_symlink() for value in (self.root, path.parent, path)):
            raise ExtractionError("UNSAFE_STORAGE_PATH")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ExtractionError("UNSAFE_STORAGE_PATH")
        return path

    def put(self, organization_id: UUID, raw: bytes) -> str:
        sha = hashlib.sha256(raw).hexdigest()
        path = self.path(organization_id, sha)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if self.get(organization_id, sha) != raw:
                raise ExtractionError("ORIGINAL_INTEGRITY_FAILURE") from None
            return sha
        with os.fdopen(descriptor, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        return sha

    def get(self, organization_id: UUID, sha: str) -> bytes:
        try:
            with self.path(organization_id, sha).open("rb") as file:
                raw = file.read(MAX_DOCUMENT_BYTES + 1)
        except OSError:
            raise ExtractionError("ORIGINAL_UNAVAILABLE") from None
        if len(raw) > MAX_DOCUMENT_BYTES or hashlib.sha256(raw).hexdigest() != sha:
            raise ExtractionError("ORIGINAL_INTEGRITY_FAILURE")
        return raw
