from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'practical_register_detail.html').read_text(encoding='utf-8')
MARK=(ROOT/'templates'/'practical_mark_entry.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'practical_file_scanner.js').read_text(encoding='utf-8')
CSS=(ROOT/'static'/'style.css').read_text(encoding='utf-8')


def test_receipts_are_experiment_specific_without_destructive_constraint_change():
    assert 'experiment_receipts_json' in APP
    assert "payload.get('experiment_id')" in APP
    assert "str(experiment.id)" in APP
    assert "practical_record_received" in APP
    assert "('practical_file_submissions','experiment_receipts_json'" in APP


def test_scanner_requires_experiment_and_tracks_selected_count():
    assert 'data-scan-experiment-select' in DETAIL
    assert 'Current Experiment' in DETAIL
    assert 'experiment_id:experiment.id' in JS
    assert 'Select experiment first' in JS


def test_tracker_matrix_and_per_experiment_delete_exist():
    assert 'Record Submission Tracker' in DETAIL
    assert 'data-record-cell' in DETAIL
    assert 'name="experiment_id"' in DETAIL
    assert 'Exp {{ e.experiment_no }}' in DETAIL
    assert 'practical-record-tracker' in CSS


def test_mark_entry_shows_current_experiment_record_status():
    assert 'record_receipt_by_student' in APP
    assert 'record_receipt_by_student.get(st.id)' in MARK
    assert 'Record received' in MARK
    assert 'Record not submitted' in MARK


def test_export_contains_experiment_record_columns():
    assert "record_headers=[f'Record {e.experiment_no}'" in APP
    assert "'Received' if str(e.id) in receipts else 'Missing'" in APP
