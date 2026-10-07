"""Hard gates for a candidate patch. A candidate must clear all of them to be eligible."""
import difflib
import posixpath
from pathlib import Path

from .. import config
from ..models import Candidate, Verdict
from . import sandbox


def is_protected(path):
    name = posixpath.basename(path)
    return path.startswith(("tests/", ".github/")) or name.startswith("test_") or name == "conftest.py"


def safe_path(path):
    return not path.startswith("/") and ".." not in path.split("/") and path.endswith(".py")


def make_diff(repo, files):
    out = []
    for rel, new in sorted(files.items()):
        old_p = Path(repo) / rel
        old = old_p.read_text() if old_p.exists() else ""
        out += difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                    f"a/{rel}", f"b/{rel}")
    return "".join(out)


def count_changed(diff):
    return sum(1 for l in diff.splitlines()
               if l[:1] in "+-" and not l.startswith(("+++", "---")))


def _first_failure(output):
    for line in output.splitlines():
        if line.startswith("FAILED"):
            return line[7:].split(" - ")[0]
    return "a test failed"


def evaluate(repo, cand: Candidate, exploit_src: str) -> Verdict:
    v = Verdict(index=cand.index, strategy=cand.strategy, files=sorted(cand.files))
    if not cand.files:
        v.reason = "model returned no files"
        return v
    bad = [p for p in cand.files if not safe_path(p) or is_protected(p)]
    if bad:
        v.reason = f"touches protected or invalid path: {bad[0]}"
        return v
    v.diff = make_diff(repo, cand.files)
    v.diff_lines = count_changed(v.diff)
    if v.diff_lines == 0:
        v.reason = "patch changes nothing"
        return v
    work = sandbox.materialize(repo, {**cand.files, config.EXPLOIT_PATH: exploit_src})
    try:
        r = sandbox.pytest(work, [config.EXPLOIT_PATH])
        v.gates["applies"] = r.returncode not in (2, 5, 124)
        if not v.gates["applies"]:
            v.reason = "does not import or run (syntax or import error)"
            return v
        v.gates["exploit"] = r.returncode == 0
        if not v.gates["exploit"]:
            v.reason = "exploit still works"
            return v
        r = sandbox.pytest(work)
        v.gates["suite"] = r.returncode == 0
        if not v.gates["suite"]:
            v.reason = "breaks existing test: " + _first_failure(r.output)
            return v
        v.passed = True
        v.reason = "exploit blocked, full suite green"
        return v
    finally:
        sandbox.cleanup(work)
