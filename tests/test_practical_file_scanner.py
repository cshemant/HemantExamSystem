from pathlib import Path
from types import SimpleNamespace

from practical_core import extract_practical_scan_fields, practical_scan_auto_match

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
TEMPLATE=(ROOT/'templates'/'practical_register_detail.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'practical_file_scanner.js').read_text(encoding='utf-8')


def test_scan_field_extraction():
    fields=extract_practical_scan_fields('Name: Rahul Sharma\nRoll No: 2024/17008\nB.Tech CSE')
    assert fields['roll_no']=='2024/17008'
    assert fields['name']=='Rahul Sharma'


def test_exact_roll_match_is_automatic():
    students=[SimpleNamespace(id=1,roll_no='2024/17008',name='Rahul Sharma'),SimpleNamespace(id=2,roll_no='2024/17009',name='Rohit Sharma')]
    result=practical_scan_auto_match('Student Name: Rahul Sharma\nRegistration No: 2024/17008',students)
    assert result['match'] is not None
    assert result['match']['student_id']==1
    assert result['match']['roll_strength']>=.9


def test_name_only_does_not_auto_save():
    students=[SimpleNamespace(id=1,roll_no='17008',name='Rahul Sharma')]
    result=practical_scan_auto_match('Name: Rahul Sharma\nDepartment: CSE',students)
    assert result['match'] is None


def test_scanner_schema_routes_and_ui_exist():
    assert 'class PracticalFileSubmission(Base):' in APP
    assert "/file-submissions/scan" in APP
    assert "/file-submissions/<int:submission_id>/delete" in APP
    assert 'data-practical-file-scanner' in TEMPLATE
    assert 'Scan Record' in TEMPLATE
    assert 'tesseract.min.js' in TEMPLATE
    assert 'pdf.min.js' not in TEMPLATE
    assert 'application/pdf' not in TEMPLATE
    assert 'window.Tesseract.createWorker' in JS
    assert 'practical_student_id' in JS


def test_image_is_not_posted_to_server():
    # The browser sends OCR text only for transient matching; scanned image bytes stay client-side.
    assert "ocr_text:current.ocrText" in JS
    assert 'FormData' not in JS
    assert "request.get_json" in APP


def test_scanner_does_not_persist_ocr_or_filename():
    assert "row.ocr_text=''" in APP
    assert "row.source_filename=''" in APP
    assert "ocr_text='',source_filename=''" in APP


def test_scanner_has_timeout_retry_and_handwriting_second_pass():
    assert 'promiseTimeout' in JS
    assert '30000' in JS
    assert 'https://unpkg.com/tesseract.js-core@5.1.1' in JS
    assert 'SPARSE_TEXT' in JS
    assert 'handwritingCanvas' in JS
    assert 'Trying handwriting enhancement' in JS
    assert 'tessdata.projectnaptha.com' not in JS
