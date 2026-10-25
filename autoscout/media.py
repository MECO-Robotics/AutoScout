import hashlib
import json
import re
import shutil
from pathlib import Path

import cv2
import imageio_ffmpeg
import yt_dlp

from .store import now


def metadata(path):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("Video cannot be decoded. Use an MP4 with H.264 video.")
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return {"fps": fps, "frames": frames, "duration": frames / fps if fps else 0,
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), "bytes": Path(path).stat().st_size}
    finally:
        cap.release()


def frame_at(path, seconds):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        if not ok:
            raise ValueError("No frame at this time. Choose a time inside the video.")
        return frame
    finally:
        cap.release()


def download(store, key, progress=lambda *_: None):
    match = store.match(key)
    if not match:
        raise ValueError("Unknown match; sync matches first.")
    if store.video_path(match):
        return {"match": key, "path": match["local_video"], "cached": True}
    # Resume a file downloaded before metadata was stored.
    existing = store.root / "videos" / (key + ".mp4")
    if not existing.exists():
        videos = [v for v in match.get("videos", []) if v["type"] == "youtube" and re.fullmatch(r"[\w-]{11}", v["key"])]
        if not videos:
            raise ValueError("No YouTube video attached to this match. Attach a local recording instead.")
        if shutil.disk_usage(store.root).free < 700 * 1024**2:
            raise ValueError("Less than 700 MB free. Free disk space before downloading footage.")

        def hook(d):
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if d.get("status") == "downloading" and total:
                progress(min(.95, d.get("downloaded_bytes", 0) / total * .95), "Downloading footage")

        options = {"format": "bestvideo[height<=1080][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo[height<=1080][ext=mp4]",
                   "merge_output_format": "mp4", "outtmpl": str(store.root / "videos" / (key + ".%(ext)s")),
                   "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(), "noplaylist": True, "quiet": True, "noprogress": True,
                   "socket_timeout": 20, "retries": 2, "fragment_retries": 2, "max_filesize": 300 * 1024**2,
                   "js_runtimes": {"node": {}}, "remote_components": ["ejs:github"], "progress_hooks": [hook]}
        errors = []
        for video in videos:
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info("https://www.youtube.com/watch?v=" + video["key"], download=True)
                match["download_source"] = {"video_id": video["key"], "title": info.get("title"), "downloaded_at": now()}
                break
            except yt_dlp.utils.DownloadError as exc:
                errors.append(str(exc))
        if not existing.exists():
            match["download_error"] = "\n".join(errors) or "Video download did not produce an MP4."
            store.put_match(match)
            raise ValueError(match["download_error"])
    details = metadata(existing)
    if details["duration"] <= 0:
        raise ValueError("Downloaded video has no decodable frames.")
    with existing.open("rb") as source:
        details["sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
    match.update(local_video=str(existing.relative_to(store.root)), video_metadata=details)
    match.pop("download_error", None)
    store.put_match(match)
    progress(1, "Footage ready")
    return {"match": key, "path": match["local_video"], "metadata": details}
