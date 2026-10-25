import argparse
import json
import os
from pathlib import Path

from .store import Store


def load_env():
    path = Path(".env")
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env()
    parser = argparse.ArgumentParser(description="FRC AutoScout local video review")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve"); serve.add_argument("--port", type=int, default=8324); serve.add_argument("--host", action="append", help="Bind address; repeat for multiple interfaces (default: 127.0.0.1)")
    sync = commands.add_parser("sync"); sync.add_argument("--team", type=int, default=8324); sync.add_argument("--year", type=int, default=2026)
    download = commands.add_parser("download"); download.add_argument("match", nargs="?"); download.add_argument("--all", action="store_true")
    gpu = commands.add_parser("detect"); gpu.add_argument("match"); gpu.add_argument("--start", type=float, default=0); gpu.add_argument("--end", type=float); gpu.add_argument("--fps", type=float, default=2); gpu.add_argument("--confidence", type=float, default=.25)
    commands.add_parser("export")
    args = parser.parse_args()
    store = Store()
    if args.command == "serve":
        import uvicorn
        from .app import create_app
        import socket
        sockets = []
        try:
            for host in args.host or ["127.0.0.1"]:
                listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sockets.append(listener)
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind((host, args.port))
                listener.listen(128)
                listener.setblocking(False)
            server = uvicorn.Server(uvicorn.Config(create_app(store), port=args.port))
            server.run(sockets=sockets)
        finally:
            for listener in sockets:
                listener.close()
    elif args.command == "sync":
        from .tba import sync
        print(json.dumps(sync(store, args.team, args.year, lambda p, text: print(f"{p:.0%} {text}", flush=True)), indent=2))
    elif args.command == "download":
        from .media import download
        keys = [m["key"] for m in store.matches()] if args.all else [args.match]
        if not all(keys):
            parser.error("Pass a match key or --all")
        failed = []
        for key in keys:
            try:
                print(json.dumps(download(store, key)), flush=True)
            except Exception as exc:
                failed.append(key); print(json.dumps({"match": key, "error": str(exc)}), flush=True)
        if failed:
            raise SystemExit(1)
    elif args.command == "detect":
        from .ml import run
        print(json.dumps(run(store, args.match, start=args.start, end=args.end, sample_fps=args.fps, confidence=args.confidence, progress=lambda p,t: print(f"{p:.0%} {t}", flush=True)), indent=2))
    else:
        from .metrics import summarize
        path = store.root / "exports" / "team-8324-2026.json"
        records = [{**m, "config": store.config(m["key"]), "observations": store.observations(m["key"]), "summary": summarize(m, store.observations(m["key"]), store.config(m["key"]))} for m in store.matches()]
        path.write_text(json.dumps(records, indent=2))
        print(path)


if __name__ == "__main__":
    main()
