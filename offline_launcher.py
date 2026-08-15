"""One-click Windows launcher for Learn with Hemant Offline Exam V2.10.

This file is compiled into a single executable for distribution. The executable
stores mutable data outside the application bundle so upgrades do not overwrite
students, exams, attempts, or the administrator account.
"""
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_VERSION = "2.10"
DEFAULT_PORT = 8080


def user_data_dir() -> Path:
    if os.name == "nt":
        root = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "LearnWithHemantExam"
    return Path.home() / ".learnwithhemant-exam"


def persistent_secret(data_dir: Path) -> str:
    secret_file = data_dir / "server.secret"
    if secret_file.exists():
        value = secret_file.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    value = secrets.token_urlsafe(48)
    secret_file.write_text(value, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return value


def app_health(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.6) as r:
            payload = json.loads(r.read().decode("utf-8"))
            return payload.get("status") == "ok" and payload.get("mode") == "offline"
    except Exception:
        return False


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def choose_port() -> tuple[int, bool]:
    if app_health(DEFAULT_PORT):
        return DEFAULT_PORT, True
    if port_is_free(DEFAULT_PORT):
        return DEFAULT_PORT, False
    for port in range(DEFAULT_PORT + 1, DEFAULT_PORT + 20):
        if app_health(port):
            return port, True
        if port_is_free(port):
            return port, False
    raise RuntimeError("No free local port was found between 8080 and 8099.")


def lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "SERVER-IP"


def open_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if app_health(port):
            webbrowser.open(url, new=2)
            return
        time.sleep(0.15)
    webbrowser.open(url, new=2)


def configure_environment(data_dir: Path) -> None:
    os.environ["APP_MODE"] = "offline"
    os.environ["OFFLINE_REQUIRE_SETUP"] = "1"
    os.environ["EXAM_DATA_DIR"] = str(data_dir)
    os.environ["SECRET_KEY"] = persistent_secret(data_dir)
    os.environ["COOKIE_SECURE"] = "0"
    # Never allow a machine-level cloud database variable to redirect the
    # downloadable offline build away from its local SQLite database.
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("ADMIN_PASSWORD", None)


def main() -> int:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    configure_environment(data_dir)

    port, already_running = choose_port()
    if already_running:
        webbrowser.open(f"http://127.0.0.1:{port}", new=2)
        return 0

    os.environ["PORT"] = str(port)

    # Import only after offline-specific environment variables are locked in.
    from app import app
    from waitress import serve

    ip = lan_ip()
    info = (
        f"Learn with Hemant Offline Exam V{APP_VERSION}\n"
        f"Faculty login: http://127.0.0.1:{port}\n"
        f"Student LAN URL: http://{ip}:{port}\n"
        f"Data folder: {data_dir}\n"
    )
    try:
        (data_dir / "LAN_ACCESS.txt").write_text(info, encoding="utf-8")
    except OSError:
        pass

    print("=" * 68)
    print(f"LEARN WITH HEMANT — OFFLINE EXAM V{APP_VERSION}")
    print(f"Faculty login:  http://127.0.0.1:{port}")
    print(f"Student LAN URL: http://{ip}:{port}")
    print(f"Data folder:     {data_dir}")
    print("Keep this window open while the examination is running.")
    print("Close this window after all students have submitted their exams.")
    print("=" * 68)

    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    serve(app, host="0.0.0.0", port=port, threads=12, clear_untrusted_proxy_headers=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except Exception as exc:
        print(f"\nUnable to start the offline exam system: {exc}\n")
        input("Press Enter to close...")
        raise
