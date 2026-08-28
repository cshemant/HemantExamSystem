from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')

def test_next_rejections_preserve_secure_shell():
    block=APP[APP.index("def next_exam_question(exam_id):"):APP.index("@app.route('/student/save-answer'",APP.index("def next_exam_question(exam_id):"))]
    assert 'def resume_current_question()' in block
    assert "secure_shell=1" in block
    assert "return resume_current_question()" in block

def test_ajax_submit_returns_json():
    block=APP[APP.index('def submit_exam(exam_id):'):APP.index("@app.route('/student/submitted/",APP.index('def submit_exam(exam_id):'))]
    assert "ajax=request.headers.get('X-Requested-With')=='XMLHttpRequest'" in block
    assert 'jsonify(ok=True,submitted=True,submitted_url=result_url)' in block
    assert 'jsonify(ok=False,submitted=False,exam_url=url' in block

def test_submitted_page_has_sameorigin_fallback():
    assert "or request.endpoint=='submitted'" in APP

def test_js_consumes_json_without_redirect_chain():
    assert "'Accept':'application/json'" in JS
    assert 'payload.submitted_url' in JS
    assert 'payload.exam_url' in JS
