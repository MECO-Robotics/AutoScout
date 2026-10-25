import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("AUTOSCOUT_DATA_DIR", "data")).resolve()
        for folder in ("videos", "evidence", "sources", "exports"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS matches (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS configs (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
              id INTEGER PRIMARY KEY, match_key TEXT NOT NULL, timestamp REAL NOT NULL,
              team INTEGER, alliance TEXT NOT NULL, kind TEXT NOT NULL, count INTEGER NOT NULL,
              status TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT, notes TEXT NOT NULL,
              run_id TEXT, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS obs_match ON observations(match_key, timestamp);
            CREATE TABLE IF NOT EXISTS robot_tags (id INTEGER PRIMARY KEY, match_key TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS priors (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, action TEXT, payload TEXT, created_at TEXT);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "autoscout.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def put_match(self, match):
        previous = self.match(match["key"])
        if previous:
            for key in ("local_video", "download_error", "video_metadata", "ml_result", "ml_summary", "automatic"):
                if key not in match and key in previous:
                    match[key] = previous[key]
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO matches VALUES (?, ?)", (match["key"], json.dumps(match)))
            if previous and previous.get("official") != match.get("official"):
                db.execute("INSERT INTO audit(action,payload,created_at) VALUES(?,?,?)", ("official_revision", json.dumps(previous), now()))

    def match(self, key):
        with self.db() as db:
            row = db.execute("SELECT payload FROM matches WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def matches(self):
        with self.db() as db:
            rows = db.execute("SELECT payload FROM matches").fetchall()
        return sorted((json.loads(r[0]) for r in rows), key=lambda m: (m.get("event_start", ""), m["event_key"], m["comp_level"] != "qm", m["set_number"] if m["comp_level"] != "qm" else 0, m["match_number"]))

    def config(self, key):
        with self.db() as db:
            row = db.execute("SELECT payload FROM configs WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_config(self, key, payload):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO configs VALUES(?,?)", (key, json.dumps(payload)))

    def observations(self, key):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM observations WHERE match_key=? ORDER BY timestamp,id", (key,))]

    def add_observation(self, key, payload):
        values = {"team": None, "count": 1, "status": "pending", "source": "manual", "evidence": None, "notes": "", "run_id": None, **payload, "match_key": key, "created_at": now()}
        cols = "match_key,timestamp,team,alliance,kind,count,status,source,evidence,notes,run_id,created_at"
        with self.db() as db:
            cursor = db.execute(f"INSERT INTO observations({cols}) VALUES({','.join('?' for _ in cols.split(','))})", [values[c] for c in cols.split(',')])
            return cursor.lastrowid

    def update_observation(self, oid, patch):
        with self.db() as db:
            row = db.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone()
            if not row:
                return None
            allowed = {k: v for k, v in patch.items() if k in ("status", "team", "count", "notes", "kind")}
            if allowed:
                db.execute("INSERT INTO audit(action,payload,created_at) VALUES(?,?,?)", ("observation_review", json.dumps(dict(row)), now()))
                db.execute(f"UPDATE observations SET {','.join(k+'=?' for k in allowed)} WHERE id=?", [*allowed.values(), oid])
            return dict(db.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone())

    def job(self, jid):
        with self.db() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (jid,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_job(self, payload):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?)", (payload["id"], json.dumps(payload)))

    def video_path(self, match):
        name = match.get("local_video")
        if not name:
            return None
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root / "videos") or not path.is_file():
            return None
        return path

    def tags(self, key):
        with self.db() as db:
            return [dict(json.loads(r['payload']), id=r['id']) for r in db.execute('SELECT * FROM robot_tags WHERE match_key=? ORDER BY id', (key,))]

    def save_tag(self, key, payload, tag_id=None):
        with self.db() as db:
            if tag_id is not None:
                row = db.execute('SELECT payload FROM robot_tags WHERE match_key=? AND id=?', (key, tag_id)).fetchone()
                if not row:
                    return None
                db.execute('INSERT INTO audit(action,payload,created_at) VALUES(?,?,?)', ('robot_tag_change', json.dumps({'id': tag_id, 'match_key': key, 'before': json.loads(row[0]), 'after': payload}), now()))
                db.execute('UPDATE robot_tags SET payload=? WHERE id=?', (json.dumps(payload), tag_id))
            else:
                tag_id = db.execute('INSERT INTO robot_tags(match_key,payload) VALUES(?,?)', (key, json.dumps(payload))).lastrowid
                db.execute('INSERT INTO audit(action,payload,created_at) VALUES(?,?,?)', ('robot_tag_create', json.dumps({'id': tag_id, 'match_key': key, 'after': payload}), now()))
        return {**payload, 'id': tag_id}
