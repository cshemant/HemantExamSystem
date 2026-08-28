from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BUILDER=(ROOT/'templates/exam_builder.html').read_text(encoding='utf-8')
EXAM=(ROOT/'templates/exam.html').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')

def test_config_and_migration():
    assert 'secure_sequential:Mapped[bool]' in APP
    assert "('exam_configs','secure_sequential'" in APP
    assert "('exam_configs','sequential_min_seconds'" in APP

def test_builder_controls():
    assert 'name="secure_sequential"' in BUILDER
    assert 'name="sequential_min_seconds"' in BUILDER

def test_server_side_next_enforcement():
    assert '/next-question' in APP
    assert 'Please spend at least' in APP
    assert 'Only the current question can be answered in Secure Sequential mode.' in APP
    assert 'Answer this question before continuing.' not in APP
    assert 'answered=_answer_is_present' in APP

def test_only_current_question_rendered():
    assert 'aq_rows=[row for row in aq_rows if row.position==current_position]' in APP
    assert 'Question {{ current_position }} of {{ total_questions }}' in EXAM
    assert 'Next Question' in EXAM

def test_next_timer_js():
    assert 'function startSequentialNextCountdown()' in JS
    assert 'Next available in' in JS
