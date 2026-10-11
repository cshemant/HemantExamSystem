#!/usr/bin/env python3
"""Apply V181 queue-clear control to an existing exam project without replacing app.py."""
from pathlib import Path
import argparse, datetime, shutil, ast

ROUTE = '''

@app.post('/admin/compiler-queue/clear')
@admin_required
def admin_compiler_queue_clear():
    """Invalidate all outstanding compiler jobs without removing any history."""
    s=DB()
    try:
        # One database transaction; active worker completion then fails its lease check.
        count=s.scalar(select(func.count()).select_from(CodeRunJob).where(
            CodeRunJob.status.in_(['queued','running']))) or 0
        s.execute(update(CodeRunJob).where(
            CodeRunJob.status.in_(['queued','running'])
        ).values(
            status='failed', success=False, error='Compilation queue cleared by super administrator',
            runner_claim_token='', completed_at=now_iso(), source_code='', stdin_text=''
        ))
        audit_event(s,'compiler_queue_cleared','code_run_jobs','',f'cancelled={count}')
        s.commit()
        flash(f'Compilation queue cleared: {count} pending/running job(s) cancelled.')
    except Exception:
        s.rollback()
        app.logger.exception('Super admin compilation queue clear failed')
        flash('Unable to clear the compilation queue. Check server logs.','error')
    finally:
        s.close()
    return redirect(url_for('admin_dashboard'))
'''

PANEL = '''
{% if staff_role == 'super_admin' %}
<section class="card" style="margin-top:20px;padding:20px">
  <h2>Compilation Queue</h2>
  <p>Clear all pending and running Code Editor and Android APK jobs. Completed jobs, examination records and practical marks are retained.</p>
  <form method="post" action="{{ url_for('admin_compiler_queue_clear') }}"
        onsubmit="return confirm('Cancel ALL queued and running compilation jobs for ALL students? This cannot be undone.');">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <button type="submit" class="btn btn-danger" style="background:#b42318;color:#fff;border:0;padding:12px 18px;border-radius:8px;cursor:pointer">
      Clear Compilation Queue
    </button>
  </form>
</section>
{% endif %}
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    args=parser.parse_args()
    root=args.root.resolve()
    app=root/'app.py'; page=root/'templates'/'admin_dashboard.html'
    if not app.is_file() or not page.is_file():
        parser.error('Project must contain app.py and templates/admin_dashboard.html')
    orig=app.read_text(encoding='utf-8'); html=page.read_text(encoding='utf-8')
    if 'def admin_compiler_queue_clear()' in orig or "url_for('admin_compiler_queue_clear')" in html:
        parser.error('V181 already appears applied; no changes made')
    anchor="@app.route('/admin')\n@staff_required\ndef admin_dashboard():"
    if orig.count(anchor)!=1:parser.error('Admin dashboard route anchor not found exactly once; refusing patch')
    if html.count('{% endblock %}')!=1:parser.error('Template endblock anchor not found exactly once; refusing patch')
    if 'class CodeRunJob(' not in orig or 'def audit_event(' not in orig:
        parser.error('Missing expected CodeRunJob/audit_event; refusing patch')
    new_app=orig.replace(anchor, ROUTE+'\n'+anchor,1)
    new_html=html.replace('{% endblock %}',PANEL+'\n{% endblock %}',1)
    ast.parse(new_app)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for path in (app,page):shutil.copy2(path,path.with_name(path.name+'.before_v181_'+stamp))
    try:
        app.write_text(new_app,encoding='utf-8')
        page.write_text(new_html,encoding='utf-8')
    except Exception:
        print('ERROR writing files; restore from .before_v181 backups.')
        raise
    print('V181 installed. Backups:',stamp)
    print('Modified:',app,page,sep='\n- ')
    print('Restart web application and verify as super admin. No DB migration.')

if __name__=='__main__':main()
