from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
ENTRY=(ROOT/'templates'/'theory_live_entry.html').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'theory_class_detail.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'theory_class.js').read_text(encoding='utf-8')


def test_theory_models_and_routes_exist():
    for token in ('class TheoryRegister','class TheoryStudent','class TheoryExperiment','class TheoryPerformance','def theory_classes','def theory_class_detail','def theory_live_entry','def theory_performed_save'):
        assert token in APP


def test_theory_link_added_to_staff_navigation():
    assert "url_for('theory_classes')" in BASE
    assert 'Theory Class' in BASE


def test_live_entry_is_date_only_not_practical_marks():
    assert 'Performed Date' in ENTRY
    assert 'Set All Today' in ENTRY
    for unwanted in ('Attendance /','Record /','Performance /','Viva /','Total /'):
        assert unwanted not in ENTRY


def test_theory_entry_autosaves_dates():
    assert 'data-theory-entry' in ENTRY
    assert 'data-theory-date' in ENTRY
    assert 'performed_date' in JS
    assert "method:'POST'" in JS


def test_detail_has_import_and_export_workflow():
    assert 'Upload Students' in DETAIL
    assert 'Update Experiments' in DETAIL
    assert "theory_export" in DETAIL


def test_theory_experiment_import_uses_required_fallback_argument():
    assert "normalize_experiment_code(x.experiment_no, x.sort_order or x.id or 1)" in APP
    assert "normalize_experiment_code(code, order)" in APP
    assert "normalize_experiment_code(x.experiment_no):x" not in APP
    assert "key=normalize_experiment_code(code);" not in APP
