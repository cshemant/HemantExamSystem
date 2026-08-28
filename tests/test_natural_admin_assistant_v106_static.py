from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_natural_language_assistant_has_fuzzy_context_engine():
    js = (ROOT / 'static' / 'voice_assistant.js').read_text(encoding='utf-8')
    for marker in (
        'levenshtein', 'candidateScore', 'SUBJECT_ALIASES', 'exam_voice_context_v2',
        'minor spelling mistakes', 'Speak naturally', 'half\\s+(?:an\\s+)?hour',
        'Cloud Computing ka Unit 2 exam bana do 30 minute ka',
    ):
        assert marker in js


def test_natural_language_assistant_keeps_confirmation_and_safety():
    js = (ROOT / 'static' / 'voice_assistant.js').read_text(encoding='utf-8')
    assert 'Confirm & Create' in js
    assert 'Confirm & Save' in js
    assert 'Confirm Session' in js
    assert 'For safety, voice cannot execute deletion' in js
    assert 'form.requestSubmit' in js


def test_subject_catalog_context_is_exposed_only_as_data():
    exams = (ROOT / 'templates' / 'exams.html').read_text(encoding='utf-8')
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'EXAM_VOICE_SUBJECT_CATALOG' in exams
    assert 'voice_subject_catalog' in app
    assert "'approved_count':approved_count" in app


def test_blueprint_page_exposes_recent_exam_context():
    builder = (ROOT / 'templates' / 'exam_builder.html').read_text(encoding='utf-8')
    assert 'data-voice-exam-context' in builder
    assert 'data-voice-exam-id' in builder
    assert 'data-voice-subject' in builder


def test_microphone_policy_is_staff_scoped():
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert "voice_staff_page=web_session.get('role') in {'admin','faculty'}" in app
    assert "microphone_policy='microphone=(self)' if voice_staff_page else 'microphone=()'" in app
