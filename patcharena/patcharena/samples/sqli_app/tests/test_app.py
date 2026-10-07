import sqlite3

from app import get_user, init_db


def make_conn():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def test_finds_existing_user():
    assert get_user(make_conn(), "alice")[0][2] == "alice@example.com"


def test_missing_user_returns_empty():
    assert get_user(make_conn(), "nobody") == []


def test_name_with_space():
    assert len(get_user(make_conn(), "Mary Jane")) == 1
