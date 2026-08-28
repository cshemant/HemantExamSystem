from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
MARK=(ROOT/'templates'/'practical_mark_entry.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')


def test_receipt_auto_awards_configured_record_marks():
    assert 'record_marks_auto' in APP
    assert '_award_record_marks_for_receipt' in APP
    assert "float(practical_marks_maxima(register)['record'])" in APP
    assert "('practical_marks','record_marks_auto','BOOLEAN NOT NULL DEFAULT FALSE')" in APP


def test_existing_v82_receipts_are_backfilled_on_mark_entry():
    assert 'Backfill V82 receipts' in APP
    assert 'record_receipt_by_student' in APP
    assert '_,changed=_award_record_marks_for_receipt' in APP


def test_mark_entry_displays_auto_awarded_record_marks():
    assert '✓ Record received' in MARK
    assert 'data-record-auto=' in MARK
    assert 'm.record_marks' in MARK
    assert 'data-record-auto' in MARK
    assert 'practical-auto-record-mark' in MARK


def test_auto_record_mark_does_not_imply_attendance():
    assert "input.getAttribute('data-record-auto')!=='1'" in JS


def test_removing_receipt_removes_only_auto_awarded_record_mark():
    assert '_remove_auto_record_marks_for_receipt' in APP
    assert 'not bool(row.record_marks_auto)' in APP
