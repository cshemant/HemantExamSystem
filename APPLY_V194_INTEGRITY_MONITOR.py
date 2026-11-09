#!/usr/bin/env python3
"""Guarded, repeatable staging patch for the V194 exam integrity monitor."""
from pathlib import Path
import ast
import re
import shutil
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
PAYLOAD=ROOT/'V194_UPDATE'
MARKER='# V194: Centralized, read-only integrity monitoring.'


def change_pattern(data, pattern, replacement, filename):
    changed, n=re.subn(pattern, replacement, data, count=1, flags=re.S)
    if n==1:return changed
    if replacement.strip() in data:return data
    raise RuntimeError(f'Expected source pattern not found in {filename}; no files have been changed.')


def modify(base):
    changes={}
    base_path=base/'templates/base.html'
    s=base_path.read_text(encoding='utf-8')
    old='''<a href="{{ url_for('analytics') }}">Analytics</a>'''
    new='''<a href="{{ url_for('analytics') }}">Analytics</a><a href="{{ url_for('integrity_monitor_v194') }}">Integrity Monitor</a>'''
    if new not in s:
        if s.count(old)!=4:
            raise RuntimeError('Expected four desktop/mobile analytics links in base.html.')
        s=s.replace(old,new)
    changes[base_path]=s

    app_path=base/'app.py'
    app=app_path.read_text(encoding='utf-8')
    route_text=(PAYLOAD/'v194_route.txt').read_text(encoding='utf-8')
    anchor="@app.route('/admin/exam/<int:exam_id>/integrity-dashboard')"
    if MARKER not in app:
        if app.count(anchor)!=1:raise RuntimeError('Could not identify integrity-dashboard anchor in app.py.')
        app=app.replace(anchor,route_text+anchor)
    ast.parse(app)
    changes[app_path]=app

    dash=base/'templates/exam_integrity_dashboard.html'
    s=dash.read_text(encoding='utf-8')
    s=change_pattern(s,r'<div class="card soft"><p><strong>Review signals, not proof of cheating\..*?(?=<div class="card"><h2>Student Attempts</h2>)',
       '''<p class="mini-meta">ML: {{ 'On' if ml_enabled else 'Off' }} · Webcam: {{ 'On' if webcam_enabled else 'Off' }}{% if ml_enabled %} · ML baseline: {{ ml_baseline_count }}/25{% endif %} · Signals are for faculty review.</p>\n''',dash)
    changes[dash]=s

    security=base/'templates/exam_security_profile.html'
    s=security.read_text(encoding='utf-8')
    s=change_pattern(s,r'<div class="card soft"><p><strong>Safeguards:.*?(?=<div class="card">\s*<h2>Staging Security Mode</h2>)',
       '<p class="mini-meta">For high-stakes exams, use supervised, phone-restricted rooms.</p>\n',security)
    s=s.replace('<h2>Staging Security Mode</h2>','<h2>Security Mode</h2>')
    s=s.replace(' — Existing browser workflows, question shuffling and audit logging. No SEB requirement.',' — Browser-based exam')
    s=s.replace(' — Requires validated SEB Config Key and managed lab supervision.',' — Verified SEB + supervision')
    s=s.replace(' — Same verified-browser enforcement, plus strict institution operating procedures. Enable optional monitoring separately below.',' — Verified SEB + institutional controls')
    s=change_pattern(s,r'  <p>Set <code>EXAM_SEB_EXTERNAL_ORIGIN</code>.*?(?=  <label for="seb-key">)',
       '''  <p class="mini-meta">SEB origin: {{ seb_origin or 'Not configured' }} · Save your .seb configuration before copying its Config Key.</p>\n''',security)
    s=change_pattern(s,r'  <p class="mini-meta">Model availability on server:.*?</p>',
       '''  <p class="mini-meta">ML: {{ 'Ready' if dependencies.ml else 'Unavailable' }} · Computer Vision: {{ 'Ready' if dependencies.cv else 'Unavailable' }} · Settings lock after the first attempt.</p>''',security)
    s=change_pattern(s,r'  <p class="mini-meta"><strong>Privacy and fairness:</strong>.*?</p>',
       '''  <p class="mini-meta">Monitoring alerts require human review. Provide camera-access alternatives through the invigilator.</p>''',security)
    s=change_pattern(s,r'  <label class="checkline"><input type="checkbox" name="enable_ml".*?</label>',
       '''  <label class="checkline"><input type="checkbox" name="enable_ml" {% if profile.ml_enabled %}checked{% endif %}> <strong>ML anomaly review</strong> (25 completed attempts required)</label>''',security)
    s=change_pattern(s,r'  <label class="checkline"><input type="checkbox" name="enable_webcam".*?</label>',
       '''  <label class="checkline"><input type="checkbox" name="enable_webcam" {% if profile.webcam_enabled %}checked{% endif %}> <strong>Webcam proctoring</strong> (camera verification required)</label>''',security)
    s=change_pattern(s,r'{% if pool_count <= .*?{% endif %}\s*<p class="mini-meta">Modern macOS/iOS.*?</p>',
       '''<p class="mini-meta">More bank questions than assigned questions allow different paper variants. SEB requires compatible clients.</p>''',security)
    changes[security]=s

    exam=base/'templates/exam.html'
    s=exam.read_text(encoding='utf-8')
    s=change_pattern(s,r'<p class="mini-meta">Webcam permission and a test frame are required before starting or resuming\..*?</p>',
       '''<p class="mini-meta">Camera required · Face-count checks · No video stored</p>''',exam)
    s=change_pattern(s,r'<p class="mini-meta">Question content stays unavailable until the webcam is working\..*?</p>',
       '''<p class="mini-meta">Questions remain locked until verification succeeds.</p>''',exam)
    changes[exam]=s

    preflight=base/'templates/exam_webcam_preflight_v188.html'
    s=preflight.read_text(encoding='utf-8')
    s=change_pattern(s,r'<p class="mini-meta">Camera frames are processed for approximate face detection;.*?</p>',
       '''<p class="mini-meta">Frames are checked, not stored. Detection may be imperfect; contact the invigilator if camera access is unavailable.</p>''',preflight)
    changes[preflight]=s

    for filename in ('templates/integrity_monitor_v194.html',
                     'templates/_integrity_monitor_live_v194.html',
                     'static/integrity_monitor_v194.css',
                     'static/integrity_monitor_v194.js'):
        target=base/filename
        payload=PAYLOAD/filename
        changes[target]=payload.read_text(encoding='utf-8')
    return changes


def main():
    base=ROOT
    changes=modify(base)  # Validate every target before writing anything.
    actually_changed={path:content for path,content in changes.items()
                      if not path.exists() or path.read_text(encoding='utf-8')!=content}
    if not actually_changed:
        print('V194 already installed. No changes needed.')
        return
    backup=base/('V194_backup_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
    saved=[]
    created=[]
    try:
        for path in actually_changed:
            if path.exists():
                backup_path=backup/path.relative_to(base)
                backup_path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,backup_path)
                saved.append((path,backup_path))
            else:created.append(path)
        for path,data in actually_changed.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data,encoding='utf-8',newline='\n')
    except Exception:
        for target,backup_path in saved:shutil.copy2(backup_path,target)
        for target in created:
            if target.exists():target.unlink()
        raise
    print('V194 installed. Backup:',backup)
    for path in actually_changed:print('  ',path.relative_to(base))
    print('Use git diff, then stage only the runtime files listed in README_V194.md.')


if __name__=='__main__':main()
