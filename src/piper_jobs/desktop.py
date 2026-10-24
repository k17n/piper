"""`piper ui`: start the API on a free localhost port, the scheduler, and a window."""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .api import STATIC_DIR, create_app
from .config import Settings
from .scheduler import start_scheduler

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_static() -> None:
    if (STATIC_DIR / "index.html").is_file():
        return
    npm = shutil.which("npm")
    if npm and (WEB_DIR / "node_modules").is_dir():
        print("Building the UI (npm run build)...")
        subprocess.run([npm, "run", "build"], cwd=WEB_DIR, check=False)
    if not (STATIC_DIR / "index.html").is_file():
        print("UI is not built yet: run `cd web && npm install && npm run build`. Serving the API only.")


def run_ui(settings: Settings, *, browser: bool = False, port: int | None = None) -> None:
    ensure_static()
    app = create_app(settings)
    port = port or free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started and thread.is_alive():
        time.sleep(0.05)
    if not thread.is_alive():
        raise SystemExit("The API server failed to start.")

    scheduler = start_scheduler(app.state.runner, settings)
    url = f"http://127.0.0.1:{port}/"
    print(f"Piper running at {url}")
    try:
        if not browser:
            try:
                import webview

                webview.create_window("Piper", url, width=1440, height=920, min_size=(900, 600))
                webview.start()
                return
            except Exception as exc:  # no GUI backend available → fall back to the browser
                print(f"Native window unavailable ({exc}); opening your browser instead.")
        webbrowser.open(url)
        print("Press Ctrl+C to quit.")
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        server.should_exit = True
