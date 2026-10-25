PHASES = ("auto", "transition", "shift1", "shift2", "shift3", "shift4", "endgame")


def phase_at(timestamp, config):
    if not config or not config.get("timing_confirmed") or timestamp < config["auto_start"]:
        return "unmapped"
    if timestamp < config["teleop_start"]:
        return "auto"
    elapsed = timestamp - config["teleop_start"]
    for boundary, phase in ((10, "transition"), (35, "shift1"), (60, "shift2"), (85, "shift3"), (110, "shift4"), (143, "endgame")):
        if elapsed < boundary:
            return phase
    return "unmapped"


def summarize(match, observations, config=None):
    aligned = bool(config and config.get("timing_confirmed"))
    accepted = [o for o in observations if o["status"] == "accepted"]
    team = match["focus_team"]
    mine = [o for o in accepted if o["team"] == team]
    makes = sum(o["count"] for o in mine if o["kind"] == "fuel_made")
    misses = sum(o["count"] for o in mine if o["kind"] == "fuel_missed")
    fuel_observed = any(o["kind"] in ("fuel_made", "fuel_missed") for o in mine)
    result = {"team": team, "reviewed_makes": makes if fuel_observed else None,
              "reviewed_misses": misses if fuel_observed else None,
              "accuracy": makes / (makes + misses) if makes + misses else None,
              "pending": sum(o["status"] == "pending" for o in observations),
              "accepted": len(accepted), "rejected": sum(o["status"] == "rejected" for o in observations),
              "comparison": [], "tower_outcome": None}
    for color in ("red", "blue"):
        official = (match.get("official") or {}).get(color, {})
        if team in match["alliances"][color]["teams"]:
            station = match["alliances"][color]["teams"].index(team) + 1
            result["tower_outcome"] = official.get(f"tower_robot{station}")
        for phase in PHASES:
            rows = [o for o in accepted if o["alliance"] == color and o["kind"] == "fuel_made" and phase_at(o["timestamp"], config) == phase]
            count = sum(o["count"] for o in rows)
            reference = official.get(phase)
            result["comparison"].append({"alliance": color, "phase": phase, "reviewed": count if aligned else None,
                                         "official": reference, "difference": count - reference if aligned and reference is not None else None})
    return result
