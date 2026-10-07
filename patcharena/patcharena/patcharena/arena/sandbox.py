"""Run pytest on a throwaway copy of the repo.

SANDBOX=local  -> subprocess in a temp dir (fine for the preloaded samples, NOT isolated)
SANDBOX=docker -> one container per run, no network, memory/CPU limits
"""
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config

IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv")


@dataclass
class TestResult:
    returncode: int  # pytest: 0 ok, 1 tests failed, 2 collection/import error, 5 none, 124 timeout
    output: str
    seconds: float


def materialize(repo, files):
    """Copy the repo to a temp dir and write `files` (relpath -> content) on top."""
    root = Path(tempfile.mkdtemp(prefix="patcharena-"))
    work = root / "work"
    shutil.copytree(repo, work, ignore=IGNORE)
    for rel, content in files.items():
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return work


def cleanup(work):
    shutil.rmtree(Path(work).parent, ignore_errors=True)


def pytest(work, targets=()):
    if config.SANDBOX == "docker":
        cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "512m", "--cpus", "1",
               "-v", f"{work}:/work", "-w", "/work", config.SANDBOX_IMAGE,
               "python", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *targets]
    else:
        cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *targets]
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=config.TEST_TIMEOUT)
        return TestResult(p.returncode, p.stdout + p.stderr, time.time() - t)
    except subprocess.TimeoutExpired:
        return TestResult(124, "timeout", time.time() - t)
