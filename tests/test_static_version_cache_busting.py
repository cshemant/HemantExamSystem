from pathlib import Path
BASE=(Path(__file__).resolve().parents[1]/'templates/base.html').read_text(encoding='utf-8')
def test_exam_js_and_css_are_versioned():
    assert "app.js') }}?v={{ app_version }}" in BASE
    assert "style.css') }}?v={{ app_version }}" in BASE
