from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_voice_assistant_assets_are_staff_only_in_base_template():
    base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
    assert "voice_assistant.css" in base
    assert "voice_assistant.js" in base
    assert "web_session.get('role') in ['admin','faculty']" in base
    assert 'window.EXAM_VOICE_CONFIG' in base


def test_voice_assistant_reuses_existing_forms_and_confirmation():
    js = (ROOT / 'static' / 'voice_assistant.js').read_text(encoding='utf-8')
    assert 'form.requestSubmit' in js
    assert 'Confirm & Create' in js
    assert 'Confirm & Save' in js
    assert 'Confirm Session' in js
    assert "'/admin" not in js  # routes come from Flask/Jinja rather than hard-coded deployment paths


def test_voice_assistant_blocks_high_risk_voice_actions():
    js = (ROOT / 'static' / 'voice_assistant.js').read_text(encoding='utf-8')
    for marker in ('delete', 'password', 'change role', 'restore', 'backup', 'reset'):
        assert marker in js
    assert 'For safety, voice cannot execute deletion' in js


def test_voice_assistant_supports_browser_fallback():
    js = (ROOT / 'static' / 'voice_assistant.js').read_text(encoding='utf-8')
    assert 'window.SpeechRecognition||window.webkitSpeechRecognition' in js
    assert 'Or type a command' in js
    assert "option value=\"en-IN\"" in js
    assert "option value=\"hi-IN\"" in js
