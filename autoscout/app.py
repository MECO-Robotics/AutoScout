import csv
import io
import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import cv2
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import media, tba, ml
from .metrics import summarize
from .store import Store, now


Kind = Literal["fuel_made", "fuel_missed", "intake", "ferry", "climb_attempt", "climb_complete", "inactive", "note"]


class Observation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    timestamp: float = Field(ge=0, le=86400)
    team: int | None = Field(default=None, ge=1, le=99999)
    alliance: Literal["red", "blue"]
    kind: Kind
    count: int = Field(default=1, ge=1, le=999)
    notes: str = Field(default="", max_length=2000)


class Review(BaseModel):
    status: Literal["pending", "accepted", "rejected"]
    team: int | None = Field(default=None, ge=1, le=99999)
    count: int = Field(default=1, ge=1, le=999)
    kind: Kind
    notes: str = Field(default="", max_length=2000)


class SyncRequest(BaseModel):
    team: int = Field(default=8324, ge=1, le=99999)
    year: int = Field(default=2026, ge=2026, le=2026)


class MLRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    start: float = Field(default=0, ge=0, le=86400)
    end: float | None = Field(default=None, gt=0, le=86400)
    sample_fps: float = Field(default=30, ge=.5, le=240)
    confidence: float = Field(default=.25, ge=.01, le=.99)


class RobotTag(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    run_id: str = Field(min_length=1, max_length=100)
    track_id: int | None = Field(default=None, ge=0)
    camera_segment: int | None = Field(default=None, ge=0)
    start: float = Field(ge=0, le=86400)
    end: float = Field(ge=0, le=86400)
    team: int = Field(ge=1, le=99999)
    box: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid_tag(self):
        if self.end < self.start:
            raise ValueError("Tag end must follow its start.")
        if self.track_id is None:
            raise ValueError("Select an existing robot track; drawn-box reconstruction is not yet supported.")
        if self.box is not None:
            x1,y1,x2,y2 = self.box
            if not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1:
                raise ValueError("Invalid robot box.")
        return self


def create_app(store=None):
    store = store or Store()
    from contextlib import asynccontextmanager
    from .worker import Worker
    worker = Worker(store)
    @asynccontextmanager
    async def lifespan(app):
        worker.start()
        yield
        worker.close()
    app = FastAPI(title="FRC AutoScout", version="0.2.0", lifespan=lifespan)
    app.state.store = store
    pool = ThreadPoolExecutor(max_workers=2)
    active, lock = {}, threading.Lock()
    static = Path(__file__).parent / "static"

    @app.middleware("http")
    async def local_mutations(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            from urllib.parse import urlparse
            if urlparse(origin).netloc != request.headers.get("host"):
                return Response("Cross-origin changes are not allowed", status_code=403)
        return await call_next(request)

    def match_or_404(key):
        match = store.match(key)
        if not match:
            raise HTTPException(404, "Match not found. Sync team matches first.")
        return match

    def start_job(kind, key, fn):
        with lock:
            if key in active:
                return store.job(active[key])
            jid = uuid.uuid4().hex
            payload = {"id": jid, "kind": kind, "match_key": key, "status": "queued", "progress": 0, "message": "Queued", "created_at": now()}
            store.put_job(payload); active[key] = jid

        def run():
            last_write = 0

            def progress(p, text):
                nonlocal last_write
                payload.update(status="running", progress=round(p, 3), message=text)
                if time.monotonic() - last_write > .4 or p >= 1:
                    store.put_job(payload); last_write = time.monotonic()
            try:
                progress(0, "Starting")
                result = fn(progress)
                payload.update(status="complete", progress=1, message="Complete", result=result, finished_at=now())
            except Exception as exc:
                payload.update(status="failed", message=str(exc), finished_at=now())
            finally:
                store.put_job(payload)
                with lock:
                    active.pop(key, None)
        pool.submit(run)
        return payload.copy()

    @app.get("/api/status")
    def status():
        return {"team": 8324, "year": 2026, "tba_key_configured": bool(os.environ.get("TBA_AUTH_KEY") or os.environ.get("TBA_API_KEY")),
                "active_jobs": list(active.values())}

    @app.get("/api/matches/{key}/automatic")
    def automatic_result(key: str, overlay: bool = False):
        m=match_or_404(key);state=m.get("automatic",{})
        relative=state.get("report")
        if not relative:return {"state":state,"report":None,"queue":store.config("automatic_queue")}
        path=(store.root/relative).resolve()
        if not path.is_relative_to(store.root/"automatic") or not path.is_file():
            raise HTTPException(404,"Analysis evidence not found")
        if overlay:return json.loads(path.with_name("overlay.json").read_text())
        report=json.loads(path.read_text())
        from .tagging import apply_tags
        report=apply_tags(report, store.tags(key), m)
        return {"state":state,"report":report,"queue":store.config("automatic_queue")}

    @app.get("/api/matches/{key}/priors")
    def priors(key: str):
        from .priors import get_priors
        return get_priors(store, match_or_404(key))

    @app.get("/api/matches/{key}/tags")
    def tags(key: str):
        m = match_or_404(key)
        return {"tags": store.tags(key), "run_id": m.get("automatic", {}).get("run_id")}

    def write_tag(key, payload, tag_id=None):
        m = match_or_404(key)
        if tag_id is not None:
            existing = next((tag for tag in store.tags(key) if tag['id'] == tag_id), None)
            if existing is None:
                raise HTTPException(404, "Tag not found.")
            if existing['run_id'] != payload.run_id:
                raise HTTPException(409, "Tags cannot move between analysis runs. Select a robot in current playback to create a new tag.")
        if payload.team not in [t for a in m['alliances'].values() for t in a['teams']]:
            raise HTTPException(422, "Team must belong to this match.")
        report = automatic_result(key)['report']
        if not report or payload.run_id != report['run_id']:
            raise HTTPException(409, "This analysis run is no longer current; reload playback.")
        if payload.end > report.get('duration', 86400):
            raise HTTPException(422, "Tag extends beyond the analyzed clip.")
        samples = [(h['timestamp'], r) for h in report.get('robot_history', []) for r in h['robots'] if r['track_id'] == payload.track_id]
        if not samples or not any(payload.start <= timestamp <= payload.end for timestamp, r in samples):
            raise HTTPException(422, "No cached robot track in the selected interval.")
        if payload.camera_segment is not None and not any(r.get('camera_segment') == payload.camera_segment for _, r in samples):
            raise HTTPException(422, "Camera segment does not match the cached track.")
        result = store.save_tag(key, {**payload.model_dump(), 'source': 'manual', 'updated_at': now(), 'deleted': False}, tag_id)
        if result is None:
            raise HTTPException(404, "Tag not found.")
        return result

    @app.post("/api/matches/{key}/tags")
    def add_tag(key: str, payload: RobotTag):
        return write_tag(key, payload)

    @app.patch("/api/matches/{key}/tags/{tag_id}")
    def edit_tag(key: str, tag_id: int, payload: RobotTag):
        return write_tag(key, payload, tag_id)

    @app.delete("/api/matches/{key}/tags/{tag_id}")
    def delete_tag(key: str, tag_id: int):
        match_or_404(key)
        tag = next((t for t in store.tags(key) if t['id'] == tag_id), None)
        if tag is None:
            raise HTTPException(404, "Tag not found.")
        return store.save_tag(key, {**tag, 'deleted': True, 'updated_at': now()}, tag_id)

    @app.get("/api/ml/status")
    def ml_status():
        return ml.runtime_status(store)

    @app.get("/api/matches/{key}/ml")
    def ml_result(key: str):
        match_or_404(key)
        return ml.read_result(store, key)

    @app.post("/api/matches/{key}/ml")
    def ml_analyze(key: str, payload: MLRequest):
        m = match_or_404(key)
        if not store.video_path(m):
            raise HTTPException(409, "Download this recording first.")
        if payload.end is not None and payload.end <= payload.start:
            raise HTTPException(422, "End must be after start.")
        return start_job("ml", key, lambda progress: ml.run(store, key, **payload.model_dump(), progress=progress))

    @app.get("/api/matches")
    def matches():
        return [{**m, "has_video": bool(store.video_path(m)), "summary": summarize(m, store.observations(m["key"]), store.config(m["key"]))} for m in store.matches()]

    @app.get("/api/matches/{key}")
    def detail(key: str):
        m = match_or_404(key)
        observations = store.observations(key)
        config = store.config(key)
        return {**m, "has_video": bool(store.video_path(m)), "config": config, "observations": observations, "summary": summarize(m, observations, config)}

    @app.post("/api/sync")
    def sync(request: SyncRequest):
        return start_job("sync", "sync", lambda progress: tba.sync(store, request.team, request.year, progress))

    @app.post("/api/matches/{key}/download")
    def download(key: str):
        match_or_404(key)
        return start_job("download", key, lambda progress: media.download(store, key, progress))

    @app.get("/api/jobs/{jid}")
    def job(jid: str):
        result = store.job(jid)
        if not result:
            raise HTTPException(404, "Job not found")
        return result

    @app.post("/api/matches/{key}/observations")
    def add(key: str, payload: Observation):
        m = match_or_404(key)
        if payload.team is not None and payload.team not in m["alliances"][payload.alliance]["teams"]:
            raise HTTPException(422, "That team is not on the selected alliance.")
        duration = m.get("video_metadata", {}).get("duration")
        if duration and payload.timestamp > duration:
            raise HTTPException(422, "Observation time is beyond the video duration.")
        oid = store.add_observation(key, {**payload.model_dump(), "status": "accepted", "source": "manual"})
        return {"id": oid}

    @app.patch("/api/observations/{oid}")
    def review(oid: int, payload: Review):
        with store.db() as db:
            row = db.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone()
        if not row:
            raise HTTPException(404, "Observation not found")
        m = match_or_404(row["match_key"])
        if payload.team is not None and payload.team not in m["alliances"][row["alliance"]]["teams"]:
            raise HTTPException(422, "That team is not on this observation's alliance.")
        return store.update_observation(oid, payload.model_dump())

    @app.get("/api/matches/{key}/video")
    def video(key: str):
        path = store.video_path(match_or_404(key))
        if not path:
            raise HTTPException(404, "No local footage. Download or attach a recording.")
        return FileResponse(path, media_type="video/mp4")

    @app.get("/api/matches/{key}/frame")
    def frame(key: str, time: float = 0):
        if not 0 <= time <= 86400:
            raise HTTPException(422, "Choose a valid frame time.")
        path = store.video_path(match_or_404(key))
        if not path:
            raise HTTPException(404, "No local footage")
        try:
            _, encoded = cv2.imencode(".jpg", media.frame_at(path, time))
            return Response(encoded.tobytes(), media_type="image/jpeg")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.post("/api/matches/{key}/upload")
    async def upload(key: str, file: UploadFile = File(...)):
        match_or_404(key)
        if not file.filename or Path(file.filename).suffix.lower() not in (".mp4",):
            raise HTTPException(422, "Choose an MP4 recording.")
        path = store.root / "videos" / f"{key}-{uuid.uuid4().hex}.mp4"
        size = 0
        try:
            with path.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 300 * 1024**2:
                        raise HTTPException(413, "Recording exceeds the MVP's 300 MB upload limit.")
                    out.write(chunk)
            details = media.metadata(path)
            m = match_or_404(key)
            m.update(local_video=str(path.relative_to(store.root)), video_metadata=details)
            store.put_match(m)
        except ValueError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(exc))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return {"ready": True, "metadata": details}

    @app.get("/api/export")
    def export(format: Literal["json", "csv"] = "json"):
        if format == "json":
            records = [{**m, "config": store.config(m["key"]), "observations": store.observations(m["key"]), "summary": summarize(m, store.observations(m["key"]), store.config(m["key"]))} for m in store.matches()]
            return Response(json.dumps(records, indent=2), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="autoscout-matches.json"'})
        output = io.StringIO()
        fields = ["match_key", "timestamp", "team", "alliance", "kind", "count", "status", "source", "notes", "evidence"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore"); writer.writeheader()
        for m in store.matches():
            for row in store.observations(m["key"]):
                safe = {k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v) for k, v in row.items()}
                writer.writerow(safe)
        return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="autoscout-observations.csv"'})

    @app.get("/evidence/{path:path}")
    def evidence(path: str):
        target = (store.root / "evidence" / path).resolve()
        if not target.is_relative_to(store.root / "evidence") or target.suffix != ".jpg" or not target.is_file():
            raise HTTPException(404, "Evidence frame not found")
        return FileResponse(target, media_type="image/jpeg")

    if static.is_dir():
        app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    return app
