from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')
EXAM=(ROOT/'templates/exam.html').read_text(encoding='utf-8')
BUILDER=(ROOT/'templates/exam_builder.html').read_text(encoding='utf-8')

def _route_block(name, next_name=None):
    start=APP.index(f'def {name}')
    if next_name:
        end=APP.index(f'def {next_name}', start)
    else:
        end=APP.find('\n@app.route', start+5)
    return APP[start:end]

def test_next_question_allows_unanswered_skip():
    block=_route_block('next_exam_question','save_answer')
    assert "Answer this question before continuing." not in block
    assert "answered=_answer_is_present" in block
    assert "previous_elapsed={elapsed}s; answered={1 if answered else 0}" in block

def test_manual_final_submit_does_not_require_answer():
    block=_route_block('submit_exam')
    assert "not _answer_is_present" not in block
    assert "Use Next until you reach the final question before submitting." in block

def test_timeout_bypasses_sequential_final_question_validation():
    block=_route_block('submit_exam')
    timeout_pos=block.index("if client_reason=='TIME_EXPIRED':")
    seq_pos=block.index("if cfg and cfg.secure_sequential:", timeout_pos)
    assert timeout_pos < seq_pos
    assert "finalize_attempt(s,attempt,'TIME_EXPIRED')" in block

def test_secure_timeout_submits_by_ajax_and_not_form_navigation():
    timer=JS[JS.index('function startTimer'):JS.index('async function logIntegrity')]
    assert "submitExamToServer(form,examId,'TIME_EXPIRED')" in timer
    assert "form.submit()" not in timer

def test_ui_says_answer_optional():
    assert 'Answer optional' in EXAM
    assert 'Answer required' not in EXAM
    assert 'require an answer' not in BUILDER
