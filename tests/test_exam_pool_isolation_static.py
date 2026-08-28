from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
EXAMS=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
QB=(ROOT/'templates'/'question_bank.html').read_text(encoding='utf-8')


def test_new_existing_subject_exam_starts_empty():
    route=APP.split("def create_exam_for_existing_subject():",1)[1].split("@app.route('/admin/exams'",1)[0]
    assert 'cfg.question_count=0' in route
    assert 'cfg.pool_size=0' in route
    assert 'copy_bank_question_to_exam' not in route


def test_manual_add_syncs_pool_and_per_student():
    route=APP.split('def bank_add_to_exam():',1)[1].split("@app.route('/admin/question-bank/practice-visibility'",1)[0]
    assert 'sync_manual_exam_question_count(s,exam_id)' in route
    assert 'BankQuestion.subject==cfg.subject.strip()' in route


def test_new_exam_form_does_not_autoselect_question_count():
    assert 'Questions per Student' not in EXAMS.split('<h2>Create Exam for Existing Subject</h2>',1)[1].split('</div>\n<script>',1)[0]


def test_created_exam_is_preselected_in_question_bank():
    assert 'target_exam_id==e.id' in QB
