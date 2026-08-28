from pathlib import Path
APP=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
TPL=(Path(__file__).resolve().parents[1]/'templates/practical_code.html').read_text(encoding='utf-8')

def test_practical_code_uses_assignment_aware_resolution():
    start=APP.index('def resolve_practical_target_for_student')
    end=APP.index('def _strip_code_comments',start)
    block=APP[start:end]
    assert 'group_section' in block
    assert 'group_year' in block
    assert 'register_candidates' in block
    assert "match_basis':'assignment-auto-sync'" in block

def test_student_practical_code_enables_safe_auto_sync():
    start=APP.index('def practical_code_exam_rows_for_student')
    end=APP.index('def student_practical_code_available',start)
    block=APP[start:end]
    assert 'auto_sync=True' in block
    assert "target.get('auto_synced')" in block

def test_code_editor_still_renders_for_valid_target():
    assert '{% if target.ok %}' in TPL
    assert 'data-practical-code-editor' in TPL
    assert 'Type your practical code here...' in TPL
