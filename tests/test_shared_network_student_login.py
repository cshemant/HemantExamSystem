from pathlib import Path
APP=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')

def test_login_never_claims_or_blocks_by_ip():
    start=APP.index('def current_practical_exam_ip_locks_for_login')
    end=APP.index('def clear_student_session_for_ip_conflict',start)
    block=APP[start:end]
    assert 'return True,None,None' in block
    assert 'ensure_exam_ip_session_lock' not in block

def test_shared_ip_is_allowed_during_exam():
    start=APP.index('def ensure_exam_ip_session_lock')
    end=APP.index('def current_practical_exam_ip_locks_for_login',start)
    block=APP[start:end]
    assert 'if row.student_id!=student.id:' in block
    assert 'return True,row' in block
    assert "exam_ip_roll_switch_blocked" not in block

def test_new_practical_defaults_do_not_enable_ip_roll_block():
    assert 'security.block_ip_roll_switch=False' in APP
