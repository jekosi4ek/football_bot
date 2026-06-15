"""
Balanced team division using a greedy strength-balancing algorithm.
"""
import logging

logger = logging.getLogger(__name__)


def _md(text: str) -> str:
    """Escape Markdown v1 special chars in user-provided strings."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def divide_players(players: list[dict], num_teams: int) -> list[dict]:
    if not players:
        return []
    num_teams = max(2, min(num_teams, len(players)))

    team_names = ["Команда A", "Команда B", "Команда C", "Команда D"]
    teams: list[dict] = [
        {"name": team_names[i], "player_ids": [], "total_strength": 0}
        for i in range(min(num_teams, len(team_names)))
    ]

    for player in sorted(players, key=lambda p: p["strength"], reverse=True):
        target = min(teams, key=lambda t: (t["total_strength"], len(t["player_ids"])))
        target["player_ids"].append(player["id"])
        target["total_strength"] += player["strength"]

    logger.info("Divided %d players into %d teams", len(players), num_teams)
    return teams


def format_teams_message(teams: list[dict], all_players: list[dict]) -> str:
    player_map = {p["id"]: p for p in all_players}
    strength_label = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐"}

    lines = ["👥 *Склад команд:*\n"]
    for team in teams:
        total = team.get("total_strength") or sum(
            player_map[pid]["strength"] for pid in team["player_ids"] if pid in player_map
        )
        lines.append(f"*{_md(team['name'])}* (сила: {total})")
        members = [player_map[pid] for pid in team["player_ids"] if pid in player_map]
        if members:
            for m in sorted(members, key=lambda p: p["strength"], reverse=True):
                lines.append(f"  • {_md(m['name'])} {strength_label[m['strength']]}")
        else:
            lines.append("  _(немає гравців)_")
        lines.append("")
    return "\n".join(lines).strip()
