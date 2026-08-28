from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')
PIN=(ROOT/'templates/exam_pin_verify.html').read_text(encoding='utf-8')

def test_secure_iframe_does_not_log_visibility_during_internal_navigation():
    assert "insideSecureShell" in JS
    assert "if(!insideSecureShell)" in JS
    assert "The outer secure shell monitors top-level visibility instead." in JS

def test_outer_shell_logs_real_tab_visibility():
    assert "document.addEventListener('visibilitychange'" in PIN
    assert "'tab_hidden','Secure exam tab/window became hidden'" in PIN

def test_parent_visibility_guard_ignores_submission_transition():
    assert "if(examFinished || !shellActive || submissionInProgress)return;" in PIN
