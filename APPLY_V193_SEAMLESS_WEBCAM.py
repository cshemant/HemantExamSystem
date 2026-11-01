#!/usr/bin/env python3
"""Guarded staging-only V193 installer: camera stays alive during Next/Previous.

Usage: python APPLY_V193_SEAMLESS_WEBCAM.py
Run from the Git checkout's application root, next to app.py.
"""
from pathlib import Path
from datetime import datetime, timezone
import shutil, sys, os

ROOT = Path.cwd()
TEMPLATE = ROOT/'templates/exam.html'
SOURCE = Path(__file__).resolve().parent/'payload/static/exam_webcam_seamless_v193.js'
TARGET = ROOT/'static/exam_webcam_seamless_v193.js'
MARKER = "<script defer src=\"{{ url_for('static',filename='exam_proctor_v189.js') }}?v=189\"></script>"
INSERT = "<script defer src=\"{{ url_for('static',filename='exam_webcam_seamless_v193.js') }}?v=193\"></script>"

def main():
    if not (ROOT/'app.py').is_file() or not TEMPLATE.is_file():
        sys.exit('STOP: Run this in the staging root containing app.py and templates/exam.html.')
    if not SOURCE.is_file() or not TARGET.parent.is_dir():
        sys.exit('STOP: V193 payload file is missing. Extract the complete ZIP.')
    original=TEMPLATE.read_bytes()
    if INSERT.encode() in original and TARGET.is_file():
        print('V193 is already installed; no change.');return
    if original.count(MARKER.encode())!=1 or INSERT.encode() in original:
        sys.exit('STOP: Installed exam template is incompatible or already partly modified; nothing changed.')
    if TARGET.exists():
        sys.exit('STOP: A V193 JavaScript file already exists but the template is not updated. Review manually.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup=TEMPLATE.with_name(f'exam.html.before_v193_{stamp}.bak')
    backup.write_bytes(original)
    new=original.replace(MARKER.encode(), (MARKER+'\n'+INSERT).encode(),1)
    try:
        TEMPLATE.write_bytes(new)
        shutil.copy2(SOURCE,TARGET)
    except Exception:
        TEMPLATE.write_bytes(original)
        if TARGET.exists():TARGET.unlink()
        raise
    print('Applied V193 seamless question navigation. Webcam JavaScript and server rules are unchanged.')
    print('Backup:', backup.name)
    print('Git commit ONLY: templates/exam.html static/exam_webcam_seamless_v193.js')

if __name__=='__main__': main()
