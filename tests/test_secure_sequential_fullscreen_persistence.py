from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXAM=(ROOT/'templates/exam.html').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')
PIN=(ROOT/'templates/exam_pin_verify.html').read_text(encoding='utf-8')

def test_secure_exam_form_does_not_escape_iframe_on_next():
    assert 'target="_top"' not in EXAM
    assert 'formaction="{{ url_for(\'next_exam_question\',exam_id=exam.id) }}"' in EXAM

def test_final_submission_still_notifies_secure_parent():
    assert "secure-exam-submitting" in JS
    assert "secure-exam-submitted" in JS
    assert "window.parent.postMessage" in JS

def test_parent_shell_owns_fullscreen_until_finish():
    assert "document.addEventListener('fullscreenchange'" in PIN
    assert "finishShell" in PIN
    assert "shell.replaceChildren(frame)" in PIN
