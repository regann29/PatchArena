import sqlite3


def init_db(conn):
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.executemany(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        [("alice", "alice@example.com"), ("bob", "bob@example.com"),
         ("Mary Jane", "mj@example.com")],
    )
    conn.commit()


def get_user(conn, name):
    """Return rows for the user with this exact name."""
    query = "SELECT id, name, email FROM users WHERE name = '%s'" % name
    return conn.execute(query).fetchall()
