"""Run pytest on a throwaway copy of the repo.

SANDBOX=local  -> subprocess in a temp dir (fine for the preloaded samples, NOT isolated)
SANDBOX=docker -> one container per run, no network, memory/CPU limits
"""
import json
import os
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


class ImportIsolationError(RuntimeError):
    pass


def _python_env(work):
    work = Path(work).resolve()
    paths = []
    source = work / "src"
    if source.is_dir():
        paths.append(str(source))
    paths.append(str(work))
    inherited = os.environ.get("PYTHONPATH")
    if inherited:
        paths.append(inherited)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _import_names(work):
    work = Path(work)
    source = work / "src"
    root = source if source.is_dir() else work
    names = []
    for path in root.iterdir():
        if path.is_file():
            if (
                path.suffix == ".py"
                and path.stem.isidentifier()
                and path.stem
                not in {"__init__", "conftest", "setup", "sitecustomize", "test", "tests"}
                and not path.stem.startswith("test_")
            ):
                names.append(path.stem)
        elif (
            path.is_dir()
            and path.name.isidentifier()
            and path.name not in {"tests", "test", "docs", "examples"}
            and any(path.rglob("*.py"))
        ):
            names.append(path.name)
    return sorted(set(names))


def verify_import_isolation(work):
    """Confirm importable top-level code resolves from this checkout."""
    work = Path(work).resolve()
    names = _import_names(work)
    if not names:
        raise ImportIsolationError(f"no importable Python modules found in {work}")

    env = _python_env(work)
    script = (
        "import importlib, json, sys\n"
        "module = importlib.import_module(sys.argv[1])\n"
        "paths = [module.__file__] if getattr(module, '__file__', None) else "
        "list(getattr(module, '__path__', []))\n"
        "print(json.dumps(paths))\n"
    )
    verified = {}
    for name in names:
        try:
            result = subprocess.run(
                [sys.executable, "-c", script, name],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=config.TEST_TIMEOUT,
            )
        except subprocess.TimeoutExpired as error:
            raise ImportIsolationError(f"import of {name!r} timed out") from error
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise ImportIsolationError(f"could not import {name!r}: {detail}")
        try:
            paths = json.loads(result.stdout.splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as error:
            raise ImportIsolationError(f"could not read the import path for {name!r}") from error
        if not paths:
            raise ImportIsolationError(f"module {name!r} has no filesystem import path")
        for value in paths:
            path = Path(value).resolve()
            try:
                path.relative_to(work)
            except ValueError as error:
                raise ImportIsolationError(
                    f"module {name!r} resolved outside the case copy: {path}"
                ) from error
        verified[name] = str(Path(paths[0]).resolve())
    return verified


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
        env = None
    else:
        cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *targets]
        try:
            verify_import_isolation(work)
        except ImportIsolationError as error:
            return TestResult(2, f"import isolation failed: {error}", 0.0)
        env = _python_env(work)
    t = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            timeout=config.TEST_TIMEOUT,
        )
        return TestResult(p.returncode, p.stdout + p.stderr, time.time() - t)
    except subprocess.TimeoutExpired:
        return TestResult(124, "timeout", time.time() - t)
