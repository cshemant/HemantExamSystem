#!/usr/bin/env python3
"""Apply a guarded fix to the existing staging app.py (no database/config changes)."""
from pathlib import Path
import ast, datetime, sys, shutil
p=Path(__file__).resolve().parent/'app.py'
if len(sys.argv)>1: p=Path(sys.argv[1]).resolve()
if not p.is_file(): raise SystemExit('Not found: '+str(p))
s=p.read_text(encoding='utf-8')
route="@app.route('/student/exam/<int:exam_id>/camera-preflight', methods=['GET', 'POST'])"
if route in s or "@app.route('/student/exam/<int:exam_id>/camera-preflight',methods=['GET','POST'])" in s:
 print('Route already registered; no changes made.'); raise SystemExit(0)
anchor='\n\ndef v188_webcam_preflight(exam_id):\n'
if s.count(anchor)!=1:
 raise SystemExit('Source mismatch. No changes made. Please compare your app.py with the included corrected version.')
s2=s.replace(anchor,'\n\n'+route+'\n@student_required\ndef v188_webcam_preflight(exam_id):\n',1)
try: tree=ast.parse(s2)
except SyntaxError as ex: raise SystemExit('Python syntax check failed: '+str(ex))
fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='v188_webcam_preflight'),None)
if not fn or len(fn.decorator_list)!=2: raise SystemExit('Route/auth check failed. File unchanged.')
backup=p.with_name(p.name+'.bak-v190-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(p,backup)
p.write_text(s2,encoding='utf-8',newline='\n')
print('Camera preflight route fixed. Backup:',backup)
