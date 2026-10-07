"""Scripted replies so the full pipeline runs without a GPU (LLM_MOCK=1).

Only knows the preloaded samples/sqli_app task. It deliberately returns a mix of good and
bad patches so the tournament has something to reject. Real runs use the AMD-hosted model.
"""
import re

EXPLOIT = '''import sqlite3

from app import get_user, init_db


def test_sql_injection_returns_no_rows():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    assert get_user(conn, "x' OR '1'='1") == []
'''

HEAD = '''import sqlite3


def init_db(conn):
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.executemany(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        [("alice", "alice@example.com"), ("bob", "bob@example.com"),
         ("Mary Jane", "mj@example.com")],
    )
    conn.commit()


'''


def _app(body):
    return f"FILE: app.py\n```python\n{HEAD}{body}```"


PATCHES = [
    # 0: parameterized query, minimal (good)
    _app('''def get_user(conn, name):
    """Return rows for the user with this exact name."""
    query = "SELECT id, name, email FROM users WHERE name = ?"
    return conn.execute(query, (name,)).fetchall()
'''),
    # 1: strips non-alphanumerics: blocks the exploit but breaks "Mary Jane"
    _app('''def get_user(conn, name):
    name = "".join(c for c in name if c.isalnum())
    query = "SELECT id, name, email FROM users WHERE name = '%s'" % name
    return conn.execute(query).fetchall()
'''),
    # 2: tries to edit the tests (cheating)
    "FILE: tests/test_app.py\n```python\ndef test_nothing():\n    assert True\n```",
    # 3: syntax error
    _app('''def get_user(conn, name)
    return conn.execute("SELECT 1").fetchall()
'''),
    # 4: parameterized with extra refactor (good, larger diff)
    _app('''SELECT_USER = "SELECT id, name, email FROM users WHERE name = ?"


def _validate(name):
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    return name


def get_user(conn, name):
    """Return rows for the user with this exact name (parameterized)."""
    cursor = conn.execute(SELECT_USER, (_validate(name),))
    return cursor.fetchall()
'''),
    # 5: cosmetic change only, vulnerability remains
    _app('''def get_user(conn, name):
    """Look up a user by exact name."""
    query = "SELECT id, name, email FROM users WHERE name = '%s'" % name
    return conn.execute(query).fetchall()
'''),
]


def reply(messages):
    text = messages[-1]["content"]
    if "ROLE: red" in text:
        return f"```python\n{EXPLOIT}```"
    if "ROLE: summary" in text:
        return ("The query was built by string formatting, so a crafted name could change the SQL. "
                "The patch passes the name as a bound parameter instead.")
    m = re.search(r"CANDIDATE_INDEX: (\d+)", text)
    i = int(m.group(1)) if m else 0
    return PATCHES[i % len(PATCHES)]
