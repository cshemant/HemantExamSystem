#!/usr/bin/env python3
"""V192 guarded fix: permit webcam preflight endpoint to request user camera access.

Run in the staging project root. Does not edit data, environment, other routes,
student settings, or policy values for other pages.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import os
import sys

SOURCE = Path('app.py')
OLD = "if endpoint in {'take_exam','verify_student_exam_pin'}:"
NEW = "if endpoint in {'take_exam','verify_student_exam_pin','v188_webcam_preflight'}:"


def main():
    if not SOURCE.is_file():
        sys.exit('ERROR: app.py not found. Run this from the staging application root.')
    original = SOURCE.read_bytes()
    # Preserve existing CRLF/LF format and do not rewrite unrelated code.
    raw_old = OLD.encode('ascii')
    raw_new = NEW.encode('ascii')
    if raw_new in original:
        print('Already fixed; no changes made.')
        return
    if original.count(raw_old) != 1:
        sys.exit('ERROR: Expected security header condition was not found exactly once. No files changed.')
    source_text = original.decode('utf-8-sig')
    before = source_text.index('def security_headers(response):')
    section = source_text[before:before+3600]
    if 'camera_policy=' not in section or OLD not in section or 'v188_webcam_preflight' not in source_text:
        sys.exit('ERROR: Source layout incompatible with this guarded patch. No files changed.')
    updated = original.replace(raw_old, raw_new, 1)
    try:
        ast.parse(updated.decode('utf-8-sig'), filename=str(SOURCE))
    except SyntaxError as err:
        sys.exit(f'ERROR: Syntax check failed ({err}). No files changed.')
    suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = SOURCE.with_name(f'app.py.before_v192_{suffix}.bak')
    if backup.exists():
        sys.exit('ERROR: Backup filename collision. No files changed.')
    backup.write_bytes(original)
    try:
        os.chmod(backup, SOURCE.stat().st_mode)
        SOURCE.write_bytes(updated)
    except Exception:
        SOURCE.write_bytes(original)
        raise
    print('SUCCESS: Enabled camera access only for v188_webcam_preflight response documents.')
    print(f'Backup: {backup.name}')
    print('Next: git diff -- app.py  |  git add app.py  |  commit and push staging')

if __name__ == '__main__':
    main()
