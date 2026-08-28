from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')
RESULTS=(ROOT/'templates/results.html').read_text(encoding='utf-8')
AUDIT=(ROOT/'templates/attempt_audit.html').read_text(encoding='utf-8')
def test_diagnostic_models_and_route():
    assert "class AttemptDiagnostic(Base)" in APP
    assert "class AttemptDiagnosticEvent(Base)" in APP
    assert "/admin/attempt/<int:attempt_id>/audit" in APP
def test_submission_reasons():
    for reason in ("MANUAL","TIME_EXPIRED","INTEGRITY_LIMIT"):
        assert reason in APP
def test_page_load_and_heartbeat_history():
    assert "/student/exam-page-loaded" in APP
    assert "_diagnostic_event(s,attempt,'heartbeat'" in APP
    assert "/student/exam-page-loaded" in JS
def test_results_has_audit_link():
    assert "View Audit" in RESULTS
    assert "Submission reason" in AUDIT
    assert "Client IP" in AUDIT
