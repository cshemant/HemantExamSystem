from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
MARKS=(ROOT/'templates'/'practical_code.html').read_text(encoding='utf-8')


def test_clean_on_time_practical_attendance_sync_exists():
    assert 'def sync_practical_attendance_from_attempt' in APP
    assert "if not meta.get('is_practical')" in APP
    assert "attempt.status!='submitted'" in APP
    assert "submitted_at>deadline" in APP
    assert "IntegrityEvent.attempt_id==attempt.id" in APP
    assert "reason':'integrity_violation'" in APP
    assert "mark.attendance='P'" in APP
    assert "attendance_marks=attendance_max" in APP
    assert 'practical_attendance_auto_synced' in APP


def test_auto_attendance_does_not_override_faculty_absent():
    assert "(mark.attendance or '').upper()=='A'" in APP
    assert "reason':'faculty_marked_absent'" in APP


def test_attendance_sync_runs_on_submit_and_legacy_student_marks_view():
    assert APP.count('sync_practical_attendance_from_attempt(s,attempt)') >= 2
    assert 'Practical Exam attendance auto-sync failed' in APP
    assert 'Repair legacy/submitted Practical Exam attendance before rendering marks.' in APP
    assert 'Practical Exam attendance repair failed while showing result' in APP


def test_student_practical_marks_show_attendance_status_and_marks():
    assert "mark.attendance=='P'" in MARKS
    assert 'Present ·' in MARKS
    assert "mark.attendance=='A'" in MARKS
    assert 'Absent · 0' in MARKS
