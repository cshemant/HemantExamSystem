from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
TPL=(ROOT/'templates/attempt_audit.html').read_text(encoding='utf-8')
def test_clean_client_fields():
    assert 'def parse_client_user_agent' in APP
    assert '<span>Browser</span>' in TPL
    assert '<span>Operating System</span>' in TPL
    assert '<span>Device Type</span>' in TPL
    assert 'diag.user_agent' not in TPL
