from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_mock_drive_server_enforcement_is_present():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    assert "class MockDriveProgress" in app
    assert "question.mock_section!=progress.active_section" in app
    assert "Complete and lock every Mock Drive section" in app
    assert "Every question must be assigned" in app

def test_mock_drive_ui_and_embedded_editor_are_present():
    exam=(ROOT/'templates'/'exam.html').read_text(encoding='utf-8')
    picker=(ROOT/'templates'/'mock_drive_sections.html').read_text(encoding='utf-8')
    editor=(ROOT/'templates'/'_embedded_code_editor.html').read_text(encoding='utf-8')
    assert 'Complete &amp; Lock Section' in exam
    assert "mock_active_section=='technical'" in exam
    assert 'Choose your next section' in picker
    assert 'student-code-editor' in editor
    assert 'mock-section-lock-note' not in exam
    assert 'mock-technical-nav' in exam

def test_result_release_date_and_secure_submission_escape_are_present():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    builder=(ROOT/'templates'/'exam_builder.html').read_text(encoding='utf-8')
    submitted=(ROOT/'templates'/'submitted.html').read_text(encoding='utf-8')
    shell=(ROOT/'templates'/'exam_pin_verify.html').read_text(encoding='utf-8')
    assert 'result_release_at' in app
    assert 'name="result_release_at"' in builder
    assert "type:'secure-exam-submitted'" in submitted
    assert "parsed.pathname+parsed.search+parsed.hash" in shell

def test_general_grouping_strip_is_hidden_and_submission_escapes_iframe():
    student=(ROOT/'templates'/'student_dashboard.html').read_text(encoding='utf-8')
    exams=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
    submitted=(ROOT/'templates'/'submitted.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    assert "unit_group.label|lower != 'general'" in student
    assert '{% if not mock_drive_page %}<h3>{{ group.subject }}</h3>{% endif %}' in exams
    assert '<div {% if mock_drive_page %}hidden{% endif %}>' in exams
    assert 'window.top.location.replace(resultPath)' in submitted
    assert 'window.top.location.replace(destination.pathname+destination.search+destination.hash)' in js

def test_mock_clock_is_authoritative_and_pin_polling_stops_during_exam():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    pin=(ROOT/'templates'/'exam_pin_verify.html').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    assert "source='mock_drive_window'" in app
    assert "return datetime.fromisoformat(mock_end)" in app
    assert "if(shellActive||examFinished)return" in pin
    assert 'height:clamp(340px,50vh,480px)' in css

def test_mock_drive_csv_uses_visible_selected_section():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    questions=(ROOT/'templates'/'questions.html').read_text(encoding='utf-8')
    assert "mock_section=selected_section if cfg and cfg.exam_type=='mock_drive'" in app
    assert 'data-mock-section-target' in questions
    assert "labels[section.value]+' MCQ CSV Import'" in questions
    assert 'Unassigned — choose section…' in questions
    assert 'mock-entry-or' in questions

def test_mock_drive_timing_and_one_question_flow_are_configurable():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    builder=(ROOT/'templates'/'exam_builder.html').read_text(encoding='utf-8')
    exam=(ROOT/'templates'/'exam.html').read_text(encoding='utf-8')
    picker=(ROOT/'templates'/'mock_drive_sections.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    for field in ('mock_drive_start_at','mock_drive_end_at','mock_section_minutes','current_question_position','section_end_at'):
        assert field in app
    for field in ('mock_drive_start_at','mock_drive_end_at','mock_{{ key }}_minutes'):
        assert field in builder
    assert 'Question {{ current_position }} of {{ total_questions }}' in exam
    assert 'previous_mock_drive_question' in exam
    assert 'startSectionTimer' in exam and 'startSectionTimer' in js
    assert 'section.minutes' in picker and 'mock_durations' in picker

def test_all_four_standard_sections_are_configured():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    for key in ('verbal','reasoning','quantitative','technical'):
        assert f"'{key}':" in app

def test_mock_test_drive_has_separate_placement_admin_page():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
    exams=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
    assert "@app.route('/admin/mock-test-drive',methods=['GET','POST'])" in app
    assert "rows=build_admin_exam_rows(s,False)" in app
    assert "rows=build_admin_exam_rows(s,True)" in app
    assert "if is_mock!=bool(mock_drive_only):continue" in app
    assert "if is_mock:subject,unit_label='General','Mock Test Drive'" in app
    assert "url_for('mock_test_drive_exams')" in base
    assert '>Placement <' in base
    assert 'Mock Test Drive</a>' in base
    assert "'Mock Test Drive' if mock_drive_page else 'Exams'" in exams
    assert '<h2>Create Exam</h2>' in exams
    assert '<div class="card"><h2>Exam List</h2>' in exams
