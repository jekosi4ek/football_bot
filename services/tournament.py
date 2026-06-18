"""
Round-robin tournament generation, standings, and score parsing.
"""
import re
import logging
from itertools import combinations

logger = logging.getLogger(__name__)


def generate_round_robin(team_names: list[str], rounds: int = 1) -> list[dict]:
    """Generate round-robin fixtures. rounds > 1 repeats the whole fixture list."""
    base = list(combinations(team_names, 2))
    matches = []
    order = 1
    for _ in range(max(1, rounds)):
        for t1, t2 in base:
            matches.append({
                "match_order": order,
                "team1_name": t1,
                "team2_name": t2,
                "team1_score": None,
                "team2_score": None,
                "played": 0,
            })
            order += 1
    return matches


def calculate_standings(team_names: list[str], matches: list[dict]) -> list[dict]:
    standings = {
        name: {"team": name, "played": 0, "won": 0, "drawn": 0,
               "lost": 0, "gf": 0, "ga": 0, "points": 0}
        for name in team_names
    }
    for m in matches:
        if not m.get("played") or m["team1_score"] is None:
            continue
        t1, t2 = m["team1_name"], m["team2_name"]
        if t1 not in standings or t2 not in standings:
            continue
        s1, s2 = int(m["team1_score"]), int(m["team2_score"])
        standings[t1]["played"] += 1; standings[t1]["gf"] += s1; standings[t1]["ga"] += s2
        standings[t2]["played"] += 1; standings[t2]["gf"] += s2; standings[t2]["ga"] += s1
        if s1 > s2:
            standings[t1]["won"] += 1; standings[t1]["points"] += 3; standings[t2]["lost"] += 1
        elif s2 > s1:
            standings[t2]["won"] += 1; standings[t2]["points"] += 3; standings[t1]["lost"] += 1
        else:
            standings[t1]["drawn"] += 1; standings[t1]["points"] += 1
            standings[t2]["drawn"] += 1; standings[t2]["points"] += 1

    table = sorted(standings.values(),
                   key=lambda x: (-x["points"], -(x["gf"] - x["ga"]), -x["gf"]))
    for i, row in enumerate(table, start=1):
        row["rank"] = i
        row["gd"] = row["gf"] - row["ga"]
    return table


def format_schedule(matches: list[dict]) -> str:
    if not matches:
        return "Матчів немає."
    lines = ["📅 *Розклад матчів:*\n"]
    for m in matches:
        num = m["match_order"]
        t1, t2 = _md(m["team1_name"]), _md(m["team2_name"])
        if m.get("played") and m["team1_score"] is not None:
            score = f"*{m['team1_score']}:{m['team2_score']}* ✅"
        else:
            score = "⏳"
        lines.append(f"`{num}.` {t1} — {t2}  {score}")
    return "\n".join(lines)


def format_standings(team_names: list[str], matches: list[dict]) -> str:
    table = calculate_standings(team_names, matches)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 *Турнірна таблиця:*\n",
             "`    Команда         Г  В  Н  П  Г±    О`"]
    for row in table:
        pos = medals.get(row["rank"], f"{row['rank']} ")
        gd_str = (f"+{row['gd']}" if row["gd"] > 0 else str(row["gd"])).ljust(5)
        name = row["team"][:13].ljust(13)
        lines.append(
            f"`{pos} {name}  {row['played']}  {row['won']}  "
            f"{row['drawn']}  {row['lost']}  {gd_str} {row['points']}`"
        )
    return "\n".join(lines)


def _md(text: str) -> str:
    """Escape Markdown v1 special chars in user-provided strings."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


# ── Score parsing ─────────────────────────────────────────────────────────────

_UA_NUMS = {
    "нуль": 0, "нулі": 0, "нула": 0,
    "один": 1, "одна": 1, "одного": 1,
    "два": 2, "дві": 2,
    "три": 3,
    "чотири": 4,
    "п'ять": 5, "пять": 5,
    "шість": 6, "шисть": 6,
    "сім": 7,
    "вісім": 8,
    "дев'ять": 9, "девять": 9,
    "десять": 10,
}


def _replace_ua_nums(text: str) -> str:
    for word, digit in sorted(_UA_NUMS.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf'\b{re.escape(word)}\b', str(digit), text)
    return text


def parse_score(text: str) -> tuple[int, int] | None:
    """Parse '3 1', '3:1', '3-1', 'три один' → (3, 1). Returns None if not found."""
    if not text:
        return None
    t = _replace_ua_nums(text.lower().strip())
    nums = re.findall(r'\d+', t)
    if len(nums) >= 2:
        s1, s2 = int(nums[0]), int(nums[1])
        if 0 <= s1 <= 20 and 0 <= s2 <= 20:
            return s1, s2
    return None


def parse_match_and_score(text: str) -> tuple[int, int, int] | None:
    """
    Parse 'матч 1 три один' → (1, 3, 1).
    Returns (match_num, score1, score2) or None.
    """
    if not text:
        return None
    t = _replace_ua_nums(text.lower().strip())
    m = re.search(r'матч\s+(\d+)[^\d]*(\d+)[^\d]+(\d+)', t)
    if m:
        mn, s1, s2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= s1 <= 20 and 0 <= s2 <= 20:
            return mn, s1, s2
    return None
