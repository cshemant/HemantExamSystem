
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
EXAMS=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
CODE=(ROOT/'templates'/'practical_code.html').read_text(encoding='utf-8')

def test_exam_config_has_practical_code_window_columns():
    assert "practical_code_start_at:Mapped[str]" in APP
    assert "practical_code_end_at:Mapped[str]" in APP
    assert "('exam_configs','practical_code_start_at'" in APP
    assert "('exam_configs','practical_code_end_at'" in APP

def test_admin_edit_modal_exposes_start_and_end_times_only_for_practical_mapping():
    assert 'name="practical_code_start_at" type="datetime-local"' in EXAMS
    assert 'name="practical_code_end_at" type="datetime-local"' in EXAMS
    assert 'data-practical-code-start-at=' in EXAMS
    assert 'data-practical-code-end-at=' in EXAMS
    assert "practicalWrap.style.display=active?'grid':'none'" in EXAMS

def test_backend_validates_window_and_end_after_start():
    assert "Set both Practical Code start and end time, or leave both blank." in APP
    assert "Practical Code end time must be after the start time." in APP
    assert "cfg.practical_code_start_at=practical_code_start_at" in APP
    assert "cfg.practical_code_end_at=practical_code_end_at" in APP

def test_student_editing_is_server_authoritative():
    assert "def practical_code_window_state" in APP
    assert "can_submit=bool(exam.is_active and window.get('can_edit'))" in APP
    assert "if not selected.get('can_submit')" in APP

def test_closed_practical_code_is_view_only_but_visible():
    assert "window.get('status')=='closed'" in APP
    assert 'readonly aria-readonly="true"' in CODE
    assert "Your code and marks are view-only." in APP
