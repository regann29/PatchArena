from dataclasses import dataclass, field, asdict


@dataclass
class Candidate:
    index: int
    strategy: str
    files: dict  # relative path -> full new file content
    raw: str = ""


@dataclass
class Verdict:
    index: int
    strategy: str
    files: list = field(default_factory=list)
    gates: dict = field(default_factory=lambda: {"applies": None, "exploit": None, "suite": None})
    passed: bool = False
    reason: str = ""
    diff: str = ""
    diff_lines: int = 0

    def to_dict(self, with_diff=False):
        d = asdict(self)
        if not with_diff:
            d.pop("diff")
        return d
