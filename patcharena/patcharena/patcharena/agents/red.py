"""Red agent: write a pytest file that FAILS on the unpatched code (the exploit/repro test)."""
from dataclasses import dataclass

from .. import config, llm
from ..arena import sandbox
from .parsing import parse_block

SYSTEM = ("You are a security engineer writing a minimal pytest test that demonstrates a reported "
          "vulnerability or bug in the given code. Use only the standard library and pytest. "
          "Import from the repo modules exactly as they are. Do not access the network and do not "
          "write outside tmp_path. The test must FAIL on the current code because of the flaw. "
          "Reply with ONE fenced python block containing the whole test file.")


@dataclass
class Exploit:
    source: str
    before_output: str


def write_exploit(repo, issue, ctx, emit, attempts=3):
    feedback = ""
    for attempt in range(1, attempts + 1):
        emit("exploit_attempt", attempt=attempt)
        prompt = (f"ROLE: red\nISSUE:\n{issue}\n\nCODE:\n{ctx.render()}\n{feedback}")
        text = llm.chat([{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": prompt}], temperature=0.2 + 0.2 * attempt)
        src = parse_block(text)
        work = sandbox.materialize(repo, {config.EXPLOIT_PATH: src})
        try:
            r = sandbox.pytest(work, [config.EXPLOIT_PATH])
        finally:
            sandbox.cleanup(work)
        if r.returncode == 1:  # a real assertion failure, not an import error or a pass
            return Exploit(src, r.output)
        why = ("it passed, so it does not show the flaw" if r.returncode == 0
               else "it errored before running (import or syntax problem)")
        feedback = f"\nYour previous test was rejected: {why}. Output tail:\n{r.output[-800:]}\n"
    return None
