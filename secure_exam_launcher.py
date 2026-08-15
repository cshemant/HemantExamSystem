"""Windows kiosk launcher for institutional exam devices.

This is a hardened browser-session foundation, not a claim of OS-level lockdown.
It launches Microsoft Edge in kiosk/full-screen mode and uses a dedicated local
profile so normal browsing state, saved passwords and extensions are not reused.
For high-stakes certification exams, pair this with institution-managed Windows
kiosk/AppLocker/MDM policies or a certified secure-browser product.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse


def find_edge() -> str | None:
    candidates = [
        shutil.which("msedge"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def validate_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError("Use a valid http:// or https:// exam URL.")
    return value.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch an exam in a restricted Microsoft Edge kiosk session.")
    parser.add_argument("url", type=validate_url, help="Exam server URL, e.g. http://192.168.1.10:8080")
    parser.add_argument("--keep-profile", action="store_true", help="Keep the temporary kiosk browser profile for diagnostics.")
    args = parser.parse_args()

    if os.name != "nt":
        print("This kiosk launcher is intended for Windows exam devices.", file=sys.stderr)
        return 2
    edge = find_edge()
    if not edge:
        print("Microsoft Edge was not found on this device.", file=sys.stderr)
        return 3

    profile = Path(tempfile.mkdtemp(prefix="LWHExamKiosk_"))
    command = [
        edge,
        "--kiosk", args.url,
        "--edge-kiosk-type=fullscreen",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-translate",
        "--disable-print-preview",
        "--disable-features=PasswordManagerOnboarding,AutofillServerCommunication,MediaRouter",
        f"--user-data-dir={profile}",
    ]
    try:
        return subprocess.call(command)
    finally:
        if not args.keep_profile:
            shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
