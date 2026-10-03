"""
database.py
===========
Our persistence layer, using Python's built-in `sqlite3` module.

WHY SQLite (and why no ORM)?
  - SQLite is a full SQL database that lives in ONE file (data/outlets.db).
    Zero servers to install -> the project runs anywhere instantly.
  - We write raw SQL on purpose. In an interview you can read this file top
    to bottom and explain every query. (In production you might reach for
    PostgreSQL + SQLAlchemy; the function names here would stay the same,
    only their bodies would change -- that's good layering.)

Each function opens a short-lived connection, does its work, and closes it.
That keeps things simple and avoids threading issues with FastAPI's workers.
"""

import sqlite3
import os
from typing import List, Dict, Any

# Store the DB file in the project's data/ folder, next to the backend.
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "outlets.db")


def _connect() -> sqlite3.Connection:
    """Open a connection and make rows behave like dictionaries."""
    os.makedirs(DB_DIR, exist_ok=True)       # ensure data/ exists
    conn = sqlite3.connect(DB_PATH)
    # row_factory = sqlite3.Row lets us access columns by name (row["name"]).
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create the `outlets` table if it doesn't exist yet.
    Called once when the API starts up.
    """
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outlets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL,
            address   TEXT    DEFAULT '',
            latitude  REAL    NOT NULL,
            longitude REAL    NOT NULL,
            is_depot  INTEGER NOT NULL DEFAULT 0   -- SQLite has no bool; 0/1
        )
        """
    )
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a DB row into a plain dict with a proper Python bool for is_depot."""
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "is_depot": bool(row["is_depot"]),
    }


def add_outlet(name: str, address: str, latitude: float,
               longitude: float, is_depot: bool = False) -> Dict[str, Any]:
    """INSERT one outlet and return it (now with its generated id)."""
    conn = _connect()
    cursor = conn.execute(
        "INSERT INTO outlets (name, address, latitude, longitude, is_depot) "
        "VALUES (?, ?, ?, ?, ?)",            # ? placeholders prevent SQL injection
        (name, address, latitude, longitude, 1 if is_depot else 0),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {
        "id": new_id, "name": name, "address": address,
        "latitude": latitude, "longitude": longitude, "is_depot": is_depot,
    }


def get_all_outlets() -> List[Dict[str, Any]]:
    """SELECT every outlet, ordered by id."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM outlets ORDER BY id").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_outlet(outlet_id: int) -> bool:
    """DELETE one outlet by id. Returns True if a row was actually removed."""
    conn = _connect()
    cursor = conn.execute("DELETE FROM outlets WHERE id = ?", (outlet_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def clear_all_outlets() -> None:
    """Remove every outlet. Handy for re-seeding demo data."""
    conn = _connect()
    conn.execute("DELETE FROM outlets")
    conn.commit()
    conn.close()


def count_outlets() -> int:
    """How many outlets exist right now."""
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) AS c FROM outlets").fetchone()["c"]
    conn.close()
    return n
