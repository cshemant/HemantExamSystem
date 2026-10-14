#!/usr/bin/env python3
"""Safe, idempotent V182 CSV template HTTP 500 hotfix.

Changes only the Flask import statement, preserves existing application code,
compiles the updated Python module, and creates a dated backup. No database access.
"""
from datetime import datetime
from pathlib import Path
import os
import shutil
import sys
import tempfile

OLD = (b'from flask import Flask, render_template, request, redirect, url_for, '
       b'session as web_session, flash, jsonify, abort, send_file, after_this_request, send_from_directory')
NEW = OLD.replace(b'Flask, render_template', b'Flask, Response, render_template')


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'app.py').expanduser().resolve()
    if not target.is_file():
        raise SystemExit(f'Error: cannot find {target}. Specify the full path to the server app.py.')
    current = target.read_bytes()
    if current.count(NEW) == 1:
        print('Already patched. No changes made.')
        return
    if current.count(OLD) != 1:
        raise SystemExit('No changes made: Flask import does not match the V182 snapshot. Review app.py manually.')

    updated = current.replace(OLD, NEW, 1)
    compile(updated.decode('utf-8-sig'), str(target), 'exec')  # verify syntax before deployment
    backup = target.with_name(target.name + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    shutil.copy2(target, backup)
    stat = target.stat()

    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.hotfix_', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as tmp:
            tmp.write(updated)
            tmp.flush()
            os.fsync(tmp.fileno())
        shutil.copymode(target, tmp_name)
        try:
            os.chown(tmp_name, stat.st_uid, stat.st_gid)
        except PermissionError:
            pass
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    print(f'CSV template hotfix applied. Backup created: {backup}')
    print('No database, template HTML, import rules or other application code was changed.')


if __name__ == '__main__':
    main()
