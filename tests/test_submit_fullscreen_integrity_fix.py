from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')
EXAM=(ROOT/'templates/exam.html').read_text(encoding='utf-8')
PIN=(ROOT/'templates/exam_pin_verify.html').read_text(encoding='utf-8')

def test_native_confirm_removed():
    assert "confirm('Submit exam now?')" not in EXAM
    assert 'exam-submit-confirm' in EXAM
    assert 'Confirm & Submit' in EXAM

def test_submission_guard_in_exam_frame():
    assert 'examSubmissionInProgress' in JS
    assert "secure-exam-submitting" in JS
    assert "if(examSubmissionInProgress)return;" in JS

def test_secure_shell_ignores_submit_navigation_fullscreen_exit():
    assert 'let submissionInProgress=false;' in PIN
    assert "data.type==='secure-exam-submitting'" in PIN
    assert 'if(examFinished || !shellActive || submissionInProgress)return;' in PIN
