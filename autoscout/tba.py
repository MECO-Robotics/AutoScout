"""TBA API ingestion, with an explicitly labeled public-page fallback."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .store import now

BASE = "https://www.thebluealliance.com"
PAGE_FIELDS = {
    "Auto Fuel": "auto", "Transition Shift Fuel": "transition", "Shift 1 Fuel": "shift1",
    "Shift 2 Fuel": "shift2", "Shift 3 Fuel": "shift3", "Shift 4 Fuel": "shift4", "Endgame Fuel": "endgame",
    "Total Fuel Points": "fuel_points", "Teleop Fuel Points": "teleop_fuel_points",
    "Total Auto": "auto_points", "Total Teleop": "teleop_points", "Total Score": "total_points",
    "Foul Points": "foul_points", "Adjustments": "adjust_points", "Auto Tower Points": "auto_tower_points",
    "Endgame Tower Points": "endgame_tower_points", "Total Tower Points": "tower_points",
}


def integer(text):
    value = text.strip()
    return int(value) if re.fullmatch(r"-?\d+", value) else None


def parse_team_page(html, team, year):
    soup = BeautifulSoup(html, "html.parser")
    matches = {}
    for row in soup.select("tr.visible-lg"):
        link = row.select_one('a[href^="/match/"]')
        if not link:
            continue
        key = link["href"].split("/")[-1]
        if not re.fullmatch(str(year) + r"[a-z0-9]+_(?:qm\d+|(?:ef|qf|sf|f)\d+m\d+)", key):
            continue
        event, suffix = key.split("_")
        parsed = re.fullmatch(r"(qm|ef|qf|sf|f)(\d+)(?:m(\d+))?", suffix)
        alliances = {}
        for color in ("red", "blue"):
            teams = [int(a.get_text(strip=True)) for a in row.select(f'td.{color} a[href^="/team/"]')]
            score = row.select_one(f"td.{color}Score")
            alliances[color] = {"teams": teams, "score": integer(score.get_text(strip=True)) if score else None}
        if not any(team in a["teams"] for a in alliances.values()):
            continue
        heading = row.find_parent("table").find_previous("h3")
        label = row.select_one(".match-name a")
        matches[key] = {"key": key, "year": year, "event_key": event, "event_name": heading.get_text(" ", strip=True) if heading else event,
            "event_start": "", "comp_level": parsed[1], "set_number": int(parsed[2]) if parsed[3] else 1,
            "match_number": int(parsed[3] or parsed[2]), "label": label.get_text(strip=True) if label else suffix,
            "alliances": alliances, "videos": [], "official": None, "source": "tba_public_page", "source_url": f"{BASE}/match/{key}", "fetched_at": now(), "focus_team": team}
    if not matches:
        raise ValueError(f"No match rows found for team {team} in {year}; TBA may have no data or its page layout changed.")
    return list(matches.values())


def parse_match_page(html, match):
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for frame in soup.select("iframe[src]"):
        m = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]{11})", frame["src"])
        if m and m[1] not in ids:
            ids.append(m[1])
    official = {"red": {}, "blue": {}}
    for row in soup.select("table.match-table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != 3:
            continue
        label = cells[1].get_text(" ", strip=True)
        for color, cell in (("red", cells[0]), ("blue", cells[2])):
            if label in PAGE_FIELDS:
                value = integer(cell.get_text(" ", strip=True))
                if value is not None:
                    official[color][PAGE_FIELDS[label]] = value
            endgame = re.fullmatch(r"Robot ([123]) Endgame", label)
            if endgame:
                official[color]["tower_robot" + endgame[1]] = cell.get_text(" ", strip=True)
    # HTML calls these values Fuel, but does not expose separate API count/point pairs.
    # Keep the source semantic explicit rather than inventing exact count fields.
    match.update(videos=[{"type": "youtube", "key": i, "url": f"https://www.youtube.com/watch?v={i}"} for i in ids],
                 official=official if any(official.values()) else None, official_unit="displayed_fuel", fetched_at=now())
    return match


def normalize_api(match, team, event):
    out = {"key": match["key"], "year": int(match["key"][:4]), "focus_team": team, "event_key": match["event_key"],
           "event_name": event.get("name", match["event_key"]), "event_start": event.get("start_date", ""),
           "comp_level": match["comp_level"], "set_number": match["set_number"], "match_number": match["match_number"],
           "label": f"Quals {match['match_number']}" if match["comp_level"] == "qm" else f"{match['comp_level'].upper()} {match['set_number']} · {match['match_number']}",
           "alliances": {c: {"teams": [int(t[3:]) for t in match["alliances"][c]["team_keys"]], "score": match["alliances"][c]["score"]} for c in ("red", "blue")},
           "videos": [{**v, "url": "https://www.youtube.com/watch?v=" + v["key"]} for v in match["videos"] if v["type"] == "youtube"],
           "official": None, "official_unit": "count", "raw_score_breakdown": match.get("score_breakdown"),
           "source": "tba_api_v3", "source_url": f"{BASE}/api/v3/match/{match['key']}", "fetched_at": now()}
    if out["year"] == 2026 and match.get("score_breakdown"):
        out["official"] = {}
        for color in ("red", "blue"):
            b = match["score_breakdown"][color]
            hub = b.get("hubScore", {})
            out["official"][color] = {p: hub.get(p + "Count") for p in ("auto", "transition", "shift1", "shift2", "shift3", "shift4", "endgame")}
            out["official"][color].update(fuel_count=hub.get("totalCount"), fuel_points=hub.get("totalPoints"), total_points=b.get("totalPoints"),
                foul_points=b.get("foulPoints"), adjust_points=b.get("adjustPoints"), tower_points=b.get("totalTowerPoints"))
            for n in (1, 2, 3):
                out["official"][color][f"tower_robot{n}"] = b.get(f"endGameTowerRobot{n}")
    return out


def sync(store, team=8324, year=2026, progress=lambda *_: None):
    key = os.environ.get("TBA_AUTH_KEY") or os.environ.get("TBA_API_KEY")
    headers = {"User-Agent": "AutoScout/0.1 (local FRC scouting; cached reads)"}
    if key:
        headers["X-TBA-Auth-Key"] = key
    warnings = []
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        if key:
            r = client.get(f"{BASE}/api/v3/team/frc{team}/matches/{year}"); r.raise_for_status()
            matches = r.json()
            (store.root / "sources" / f"frc{team}-{year}-api.json").write_text(json.dumps(matches, indent=2))
            events = {}
            for i, m in enumerate(matches):
                if m["event_key"] not in events:
                    e = client.get(f"{BASE}/api/v3/event/{m['event_key']}"); e.raise_for_status(); events[m["event_key"]] = e.json()
                store.put_match(normalize_api(m, team, events[m["event_key"]])); progress((i + 1) / max(1, len(matches)), m["key"])
        else:
            r = client.get(f"{BASE}/team/{team}/{year}"); r.raise_for_status()
            (store.root / "sources" / f"frc{team}-{year}.html").write_text(r.text)
            matches = parse_team_page(r.text, team, year)
            for i, m in enumerate(matches):
                cache = store.root / "sources" / (m["key"] + ".html")
                try:
                    if cache.exists() and time.time() - cache.stat().st_mtime < 3600:
                        html = cache.read_text()
                    else:
                        r = client.get(m["source_url"]); r.raise_for_status(); html = r.text; cache.write_text(html); time.sleep(0.15)
                    m = parse_match_page(html, m)
                except (httpx.HTTPError, ValueError) as exc:
                    warnings.append(f"{m['key']}: {exc}")
                    previous = store.match(m["key"])
                    if previous:
                        m = previous
                    else:
                        m["sync_error"] = str(exc)
                store.put_match(m); progress((i + 1) / len(matches), m["key"])
    return {"matches": len(matches), "source": "tba_api_v3" if key else "tba_public_page", "warnings": warnings}
