"""
Database layer — supports both PostgreSQL (Railway) and SQLite (local dev).

Detection: if DATABASE_URL env var is set → PostgreSQL via psycopg2.
           Otherwise                       → SQLite via sqlite3.

The public API (add_player, get_players, …) is identical for both backends.
All queries use {ph} as the placeholder token and are formatted at call time.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

DATABASE_URL: str | None = os.getenv("DATABASE_URL")   # set automatically by Railway Postgres plugin
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "football.db")


# ── Connection factory ────────────────────────────────────────────────────────

def _is_pg() -> bool:
    return bool(DATABASE_URL)


def _ph() -> str:
    """SQL placeholder token."""
    return "%s" if _is_pg() else "?"


def get_connection():
    if _is_pg():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _row(row) -> dict | None:
    """Normalise a DB row to a plain dict regardless of backend."""
    if row is None:
        return None
    return dict(row)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    if _is_pg():
        _init_pg()
    else:
        _init_sqlite()
    logger.info("Database initialised (%s)", "PostgreSQL" if _is_pg() else "SQLite")


def _init_sqlite():
    import sqlite3
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                strength   INTEGER NOT NULL DEFAULT 2
                                   CHECK(strength BETWEEN 1 AND 3),
                chat_id    INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                player_ids TEXT    NOT NULL DEFAULT '[]',
                chat_id    INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tournament_matches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                match_order INTEGER NOT NULL,
                team1_name  TEXT    NOT NULL,
                team2_name  TEXT    NOT NULL,
                team1_score INTEGER DEFAULT NULL,
                team2_score INTEGER DEFAULT NULL,
                played      INTEGER NOT NULL DEFAULT 0
            )
        """)


def _init_pg():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT    NOT NULL,
                    strength   INTEGER NOT NULL DEFAULT 2
                                       CHECK(strength BETWEEN 1 AND 3),
                    chat_id    BIGINT  NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT    NOT NULL,
                    player_ids TEXT    NOT NULL DEFAULT '[]',
                    chat_id    BIGINT  NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id          SERIAL PRIMARY KEY,
                    start_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration    INTEGER NOT NULL,
                    half_number INTEGER NOT NULL DEFAULT 1,
                    chat_id     BIGINT  NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tournament_matches (
                    id          SERIAL PRIMARY KEY,
                    chat_id     BIGINT  NOT NULL,
                    match_order INTEGER NOT NULL,
                    team1_name  TEXT    NOT NULL,
                    team2_name  TEXT    NOT NULL,
                    team1_score INTEGER DEFAULT NULL,
                    team2_score INTEGER DEFAULT NULL,
                    played      INTEGER NOT NULL DEFAULT 0
                )
            """)
    conn.close()


# ── Players ───────────────────────────────────────────────────────────────────

def add_player(name: str, chat_id: int, strength: int = 2) -> int:
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor() if _is_pg() else conn
            if _is_pg():
                cur.execute(
                    f"INSERT INTO players (name, strength, chat_id) VALUES ({ph}, {ph}, {ph}) RETURNING id",
                    (name.strip(), strength, chat_id),
                )
                return cur.fetchone()["id"]
            else:
                c = conn.execute(
                    f"INSERT INTO players (name, strength, chat_id) VALUES ({ph}, {ph}, {ph})",
                    (name.strip(), strength, chat_id),
                )
                return c.lastrowid
    finally:
        conn.close()


def get_players(chat_id: int) -> list[dict]:
    ph = _ph()
    conn = get_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM players WHERE chat_id = {ph} ORDER BY name",
                    (chat_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        else:
            rows = conn.execute(
                f"SELECT * FROM players WHERE chat_id = {ph} ORDER BY name COLLATE NOCASE",
                (chat_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def get_player(player_id: int, chat_id: int) -> dict | None:
    ph = _ph()
    conn = get_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM players WHERE id = {ph} AND chat_id = {ph}",
                    (player_id, chat_id),
                )
                return _row(cur.fetchone())
        else:
            row = conn.execute(
                f"SELECT * FROM players WHERE id = {ph} AND chat_id = {ph}",
                (player_id, chat_id),
            ).fetchone()
            return _row(row)
    finally:
        conn.close()


def player_exists(name: str, chat_id: int) -> bool:
    ph = _ph()
    conn = get_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM players WHERE LOWER(name) = LOWER({ph}) AND chat_id = {ph}",
                    (name.strip(), chat_id),
                )
                return cur.fetchone() is not None
        else:
            row = conn.execute(
                f"SELECT 1 FROM players WHERE LOWER(name) = LOWER({ph}) AND chat_id = {ph}",
                (name.strip(), chat_id),
            ).fetchone()
            return row is not None
    finally:
        conn.close()


def remove_player(player_id: int, chat_id: int) -> bool:
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM players WHERE id = {ph} AND chat_id = {ph}",
                        (player_id, chat_id),
                    )
                    return cur.rowcount > 0
            else:
                cur = conn.execute(
                    f"DELETE FROM players WHERE id = {ph} AND chat_id = {ph}",
                    (player_id, chat_id),
                )
                return cur.rowcount > 0
    finally:
        conn.close()


def update_player_strength(player_id: int, strength: int, chat_id: int) -> bool:
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE players SET strength = {ph} WHERE id = {ph} AND chat_id = {ph}",
                        (strength, player_id, chat_id),
                    )
                    return cur.rowcount > 0
            else:
                cur = conn.execute(
                    f"UPDATE players SET strength = {ph} WHERE id = {ph} AND chat_id = {ph}",
                    (strength, player_id, chat_id),
                )
                return cur.rowcount > 0
    finally:
        conn.close()


# ── Teams ─────────────────────────────────────────────────────────────────────

def save_teams(teams: list[dict], chat_id: int):
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM teams WHERE chat_id = {ph}", (chat_id,))
                    for team in teams:
                        cur.execute(
                            f"INSERT INTO teams (name, player_ids, chat_id) VALUES ({ph}, {ph}, {ph})",
                            (team["name"], json.dumps(team["player_ids"]), chat_id),
                        )
            else:
                conn.execute(f"DELETE FROM teams WHERE chat_id = {ph}", (chat_id,))
                for team in teams:
                    conn.execute(
                        f"INSERT INTO teams (name, player_ids, chat_id) VALUES ({ph}, {ph}, {ph})",
                        (team["name"], json.dumps(team["player_ids"]), chat_id),
                    )
    finally:
        conn.close()


def get_teams(chat_id: int) -> list[dict]:
    ph = _ph()
    conn = get_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM teams WHERE chat_id = {ph} ORDER BY name",
                    (chat_id,),
                )
                rows = cur.fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM teams WHERE chat_id = {ph} ORDER BY name",
                (chat_id,),
            ).fetchall()

        result = []
        for row in rows:
            t = dict(row)
            t["player_ids"] = json.loads(t["player_ids"])
            result.append(t)
        return result
    finally:
        conn.close()


def delete_teams(chat_id: int):
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM teams WHERE chat_id = {ph}", (chat_id,))
            else:
                conn.execute(f"DELETE FROM teams WHERE chat_id = {ph}", (chat_id,))
    finally:
        conn.close()


# ── Matches ───────────────────────────────────────────────────────────────────

def save_match(duration: int, chat_id: int, half_number: int = 1) -> int:
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO matches (duration, chat_id, half_number) VALUES ({ph}, {ph}, {ph}) RETURNING id",
                        (duration, chat_id, half_number),
                    )
                    return cur.fetchone()["id"]
            else:
                cur = conn.execute(
                    f"INSERT INTO matches (duration, chat_id, half_number) VALUES ({ph}, {ph}, {ph})",
                    (duration, chat_id, half_number),
                )
                return cur.lastrowid
    finally:
        conn.close()


# ── Tournament matches ────────────────────────────────────────────────────────

def save_tournament(matches: list[dict], chat_id: int):
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM tournament_matches WHERE chat_id = {ph}", (chat_id,))
                    for m in matches:
                        cur.execute(
                            f"INSERT INTO tournament_matches "
                            f"(chat_id, match_order, team1_name, team2_name) "
                            f"VALUES ({ph}, {ph}, {ph}, {ph})",
                            (chat_id, m["match_order"], m["team1_name"], m["team2_name"]),
                        )
            else:
                conn.execute(f"DELETE FROM tournament_matches WHERE chat_id = {ph}", (chat_id,))
                for m in matches:
                    conn.execute(
                        f"INSERT INTO tournament_matches "
                        f"(chat_id, match_order, team1_name, team2_name) "
                        f"VALUES ({ph}, {ph}, {ph}, {ph})",
                        (chat_id, m["match_order"], m["team1_name"], m["team2_name"]),
                    )
    finally:
        conn.close()


def get_tournament(chat_id: int) -> list[dict]:
    ph = _ph()
    conn = get_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM tournament_matches WHERE chat_id = {ph} ORDER BY match_order",
                    (chat_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        else:
            rows = conn.execute(
                f"SELECT * FROM tournament_matches WHERE chat_id = {ph} ORDER BY match_order",
                (chat_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def update_match_score(match_id: int, team1_score: int, team2_score: int, chat_id: int) -> bool:
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE tournament_matches SET team1_score={ph}, team2_score={ph}, played=1 "
                        f"WHERE id={ph} AND chat_id={ph}",
                        (team1_score, team2_score, match_id, chat_id),
                    )
                    return cur.rowcount > 0
            else:
                cur = conn.execute(
                    f"UPDATE tournament_matches SET team1_score={ph}, team2_score={ph}, played=1 "
                    f"WHERE id={ph} AND chat_id={ph}",
                    (team1_score, team2_score, match_id, chat_id),
                )
                return cur.rowcount > 0
    finally:
        conn.close()


def rename_team(chat_id: int, old_name: str, new_name: str):
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE teams SET name={ph} WHERE chat_id={ph} AND name={ph}", (new_name, chat_id, old_name))
                    cur.execute(f"UPDATE tournament_matches SET team1_name={ph} WHERE chat_id={ph} AND team1_name={ph}", (new_name, chat_id, old_name))
                    cur.execute(f"UPDATE tournament_matches SET team2_name={ph} WHERE chat_id={ph} AND team2_name={ph}", (new_name, chat_id, old_name))
            else:
                conn.execute(f"UPDATE teams SET name={ph} WHERE chat_id={ph} AND name={ph}", (new_name, chat_id, old_name))
                conn.execute(f"UPDATE tournament_matches SET team1_name={ph} WHERE chat_id={ph} AND team1_name={ph}", (new_name, chat_id, old_name))
                conn.execute(f"UPDATE tournament_matches SET team2_name={ph} WHERE chat_id={ph} AND team2_name={ph}", (new_name, chat_id, old_name))
    finally:
        conn.close()


def delete_tournament(chat_id: int):
    ph = _ph()
    conn = get_connection()
    try:
        with conn:
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM tournament_matches WHERE chat_id = {ph}", (chat_id,))
            else:
                conn.execute(f"DELETE FROM tournament_matches WHERE chat_id = {ph}", (chat_id,))
    finally:
        conn.close()
