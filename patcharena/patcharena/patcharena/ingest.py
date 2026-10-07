import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config

SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


@dataclass
class Context:
    files: dict  # relative path -> source

    def render(self):
        return "\n\n".join(f"### {p}\n```python\n{s}\n```" for p, s in self.files.items())


def clone(url):
    dest = Path(tempfile.mkdtemp(prefix="patcharena-clone-"))
    subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True,
                   capture_output=True, text=True, timeout=120)
    return dest


def collect(repo, cap=None):
    """Read .py files, source files first, tests after, until the character cap."""
    cap = cap or config.CONTEXT_CHARS
    repo = Path(repo)
    paths = [p for p in repo.rglob("*.py") if not (set(p.relative_to(repo).parts) & SKIP)]
    paths.sort(key=lambda p: ("test" in p.name or "tests" in p.parts, str(p)))
    files, used = {}, 0
    for p in paths:
        text = p.read_text(errors="replace")
        if used + len(text) > cap:
            continue
        files[str(p.relative_to(repo))] = text
        used += len(text)
    return Context(files)
