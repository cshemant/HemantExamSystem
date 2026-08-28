from pathlib import Path
APP=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')

def test_exam_delete_removes_diagnostic_children_before_attempt():
    route=APP[APP.index("def delete_exam(exam_id):"):APP.index("@app.route('/admin/exam/<int:exam_id>/toggle'", APP.index("def delete_exam(exam_id):"))]
    event_pos=route.index("delete(AttemptDiagnosticEvent)")
    diag_pos=route.index("delete(AttemptDiagnostic)")
    attempt_pos=route.index("delete(Attempt).where")
    assert event_pos < attempt_pos
    assert diag_pos < attempt_pos
