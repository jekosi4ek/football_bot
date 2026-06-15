"""
Balanced team division using a greedy strength-balancing algorithm.

Algorithm:
  1. Sort players by strength descending (strongest first).
  2. Iterate: assign each player to the team with the lowest current total strength.
  3. On ties, assign to the team with fewer players.

This produces near-optimal balance without needing a full combinatorial search.
"""

import logging

logger = logging.getLogger(__name__)


def divide_players(players: list[dict], num_teams: int) -> list[dict]:
    """
    Returns a list of team dicts:
      { "name": "Команда 1", "player_ids": [...], "total_strength": int }
    """
    if not players:
        return []
    if num_teams < 2:
        num_teams = 2

    team_names = ["Команда A", "Команда B", "Команда C", "Команда D"]
    teams: list[dict] = [
        {"name": team_names[i], "player_ids": [], "total_strength": 0}
        for i in range(min(num_teams, len(team_names)))
    ]

    sorted_players = sorted(players, key=lambda p: p["strength"], reverse=True)

    for player in sorted_players:
        # Pick the team with the lowest total strength; break ties by fewest players
        target = min(teams, key=lambda t: (t["total_strength"], len(t["player_ids"])))
        target["player_ids"].append(player["id"])
        target["total_strength"] += player["strength"]

    logger.info(
        "Divided %d players into %d teams: %s",
        len(players),
        num_teams,
        [(t["name"], t["total_strength"]) for t in teams],
    )
    return teams


def format_teams_message(teams: list[dict], all_players: list[dict]) -> str:
    player_map = {p["id"]: p for p in all_players}
    strength_label = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐"}

    lines = ["👥 *Склад команд:*\n"]
    for team in teams:
        members = [player_map[pid] for pid in team["player_ids"] if pid in player_map]
        lines.append(f"*{team['name']}* (сила: {team['total_strength']})")
        if members:
            for m in sorted(members, key=lambda p: p["strength"], reverse=True):
                lines.append(f"  • {m['name']} {strength_label[m['strength']]}")
        else:
            lines.append("  _(немає гравців)_")
        lines.append("")
    return "\n".join(lines).strip()
