import re

FILE_RE = re.compile(r"FILE:\s*(\S+)\s*\n```[a-zA-Z]*\n(.*?)```", re.DOTALL)
BLOCK_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


def parse_files(text):
    """Model output -> {relpath: full file content}. Format: 'FILE: path' then a fenced block."""
    return {m.group(1).strip(): m.group(2) for m in FILE_RE.finditer(text)}


def parse_block(text):
    m = BLOCK_RE.search(text)
    return (m.group(1) if m else text).strip() + "\n"
