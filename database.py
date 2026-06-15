import sqlite3
import json
import logging
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                strength    INTEGER NOT NULL DEFAULT 2
                                    CHECK(strength BETWEEN 1 AND 3),
                chat_id     INTEGER NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                player_ids  TEXT    NOT NULL DEFAULT '[]',
                chat_id     INTEGER NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration    INTEGER NOT NULL,
                half_number INTEGER NOT NULL DEFAULT 1,
                chat_id     INTEGER NOT NULL
            )
        """)
        conn.commit()
    logger.info("Database initialized")


# ── Players ───────────────────────────────────────────────────────────────────

def add_player(name: str, chat_id: int, strength: int = 2) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO players (name, strength, chat_id) VALUES (?, ?, ?)",
            (name.strip(), strength, chat_id),
        )
        conn.commit()
        return cur.lastrowid


def get_players(chat_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM players WHERE chat_id = ? ORDER BY name COLLATE NOCASE",
            (chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_player(player_id: int, chat_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM players WHERE id = ? AND chat_id = ?",
            (player_id, chat_id),
        ).fetchone()
        return dict(row) if row else None


def player_exists(name: str, chat_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM players WHERE LOWER(name) = LOWER(?) AND chat_id = ?",
            (name.strip(), chat_id),
        ).fetchone()
        return row is not None


def remove_player(player_id: int, chat_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM players WHERE id = ? AND chat_id = ?",
            (player_id, chat_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_player_strength(player_id: int, strength: int, chat_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE players SET strength = ? WHERE id = ? AND chat_id = ?",
            (strength, player_id, chat_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Teams ─────────────────────────────────────────────────────────────────────

def save_teams(teams: list[dict], chat_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM teams WHERE chat_id = ?", (chat_id,))
        for team in teams:
            conn.execute(
                "INSERT INTO teams (name, player_ids, chat_id) VALUES (?, ?, ?)",
                (team["name"], json.dumps(team["player_ids"]), chat_id),
            )
        conn.commit()


def get_teams(chat_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM teams WHERE chat_id = ? ORDER BY name",
            (chat_id,),
        ).fetchall()
        result = []
        for row in rows:
            t = dict(row)
            t["player_ids"] = json.loads(t["player_ids"])
            result.append(t)
        return result


def delete_teams(chat_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM teams WHERE chat_id = ?", (chat_id,))
        conn.commit()


# ── Matches ───────────────────────────────────────────────────────────────────

def save_match(duration: int, chat_id: int, half_number: int = 1) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO matches (duration, chat_id, half_number) VALUES (?, ?, ?)",
            (duration, chat_id, half_number),
        )
        conn.commit()
        return cur.lastrowid
