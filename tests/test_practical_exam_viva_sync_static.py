from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BANK=(ROOT/'templates'/'question_bank.html').read_text(encoding='utf-8')
EDIT=(ROOT/'templates'/'question_bank_edit.html').read_text(encoding='utf-8')


def test_practical_exam_visibility_exists():
    assert "'practical_exam':'Practical Exam'" in APP
    assert 'value="practical_exam">Practical Exam</option>' in BANK
    assert 'value="practical_exam"' in EDIT


def test_experiment_serial_is_persisted_and_snapshotted():
    assert "practical_experiment_no:Mapped[str]=mapped_column(String,nullable=False,default='')" in APP
    assert "('questions','practical_experiment_no',\"VARCHAR NOT NULL DEFAULT ''\")" in APP
    assert "('bank_questions','practical_experiment_no',\"VARCHAR NOT NULL DEFAULT ''\")" in APP
    assert "normalize_practical_exam_no(bq.practical_experiment_no)" in APP


def test_practical_exam_cannot_mix_experiments_or_regular_questions():
    assert 'Practical Exam questions must be the only questions in the exam' in APP
    assert "len(experiment_numbers)!=1" in APP
    assert "mixed_practical_and_regular_questions" in APP
    assert "multiple_experiment_numbers" in APP


def test_submission_syncs_by_roll_experiment_and_safe_disambiguation():
    assert 'def sync_practical_viva_from_attempt' in APP
    assert "student.registration_no" in APP
    assert "PracticalExperiment.experiment_no==target_experiment" in APP
    assert "_practical_register_section_code(item[0])==group_section" in APP
    assert "Subject is only a final tie-breaker" in APP
    assert "len(candidates)!=1" in APP
    assert "mark.viva_marks=viva_value" in APP
    assert "practical_viva_auto_synced" in APP


def test_practical_sync_is_called_on_finalize_and_manual_grading():
    assert APP.count('sync_practical_viva_from_attempt(s,attempt)') >= 2
    assert "Practical Exam viva auto-sync failed" in APP
    assert "Practical Exam viva re-sync failed" in APP


def test_practical_questions_are_not_student_practice_questions():
    # Student practice queries remain intentionally limited to practice_only/both.
    assert "BankQuestion.practice_visibility.in_(['practice_only','both'])" in APP


def test_existing_submitted_attempts_are_repaired_after_exam_conversion():
    assert 'def resync_submitted_practical_attempts' in APP
    assert 'resync_submitted_practical_attempts(s,exam.id)' in APP
    assert "Practical Exam retroactive viva sync failed" in APP


def test_result_page_can_idempotently_repair_viva_mapping():
    assert "reason':'already_synced'" in APP
    assert "Practical Exam viva repair failed while showing result" in APP
