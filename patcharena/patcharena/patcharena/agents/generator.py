"""Patch generator: one candidate per call, with a different strategy hint each."""
from .. import llm
from ..models import Candidate
from .parsing import parse_files

STRATEGIES = [
    "make the smallest possible change that fixes the root cause",
    "validate and sanitize input at the trust boundary",
    "replace the unsafe API or pattern with its safe equivalent",
    "restructure the code so the unsafe pattern cannot occur",
]

SYSTEM = ("You are a senior engineer fixing a security bug. Do not edit tests. Keep existing "
          "behavior for valid input. Reply ONLY with the changed files, each as a line "
          "'FILE: relative/path.py' followed by a fenced python block with the COMPLETE new file.")


def generate_one(index, issue, ctx, exploit_src):
    strategy = STRATEGIES[index % len(STRATEGIES)]
    prompt = (f"ROLE: patch\nCANDIDATE_INDEX: {index}\nSTRATEGY: {strategy}\n\nISSUE:\n{issue}\n\n"
              f"FAILING TEST (must pass after your fix):\n```python\n{exploit_src}\n```\n\n"
              f"CODE:\n{ctx.render()}")
    text = llm.chat([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
                    temperature=min(1.0, 0.3 + 0.1 * (index % 8)))
    return Candidate(index=index, strategy=strategy, files=parse_files(text), raw=text)
