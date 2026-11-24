import sqlite3

from shopping_assistant.db.session import DB_PATH


def find_customer(name: str) -> list[tuple[int, str, str]]:
    """Return (id, name, email) for customers whose name matches (case-insensitive, trimmed)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, email FROM customers WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
        (name,),
    ).fetchall()
    conn.close()
    return rows