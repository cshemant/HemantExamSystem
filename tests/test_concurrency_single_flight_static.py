from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
JS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
EXAM=(ROOT/'templates'/'exam.html').read_text(encoding='utf-8')
PIN=(ROOT/'templates'/'exam_pin_verify.html').read_text(encoding='utf-8')

def test_navigation_is_single_flight_on_client_and_server():
    assert 'initSingleFlightExamNavigation' in JS
    assert 'expected_position' in EXAM
    assert '.with_for_update().execution_options(populate_existing=True)' in APP
    assert "return redirect(url_for('take_exam',exam_id=exam_id),code=303)" in APP

def test_submission_and_postgresql_connections_are_bounded():
    assert "select(Attempt).where(Attempt.id==attempt.id).with_for_update()" in APP
    for setting in ('DB_POOL_SIZE','DB_MAX_OVERFLOW','DB_POOL_TIMEOUT','DB_POOL_RECYCLE'):
        assert setting in APP

def test_background_traffic_is_reduced():
    assert 'function startExamHeartbeat(examId,seconds=25)' in JS
    assert "_diagnostic_event(s,attempt,'heartbeat'" not in APP
    assert 'const answerSaveStates=new Map()' in JS
    assert "current_student_exam_pin" not in EXAM
    assert 'current_student_exam_pin' in PIN
