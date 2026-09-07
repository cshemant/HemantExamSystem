from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
WORKER=(ROOT/'code_runner_worker.py').read_text(encoding='utf-8')
START=(ROOT/'start_code_runner_windows.ps1').read_text(encoding='utf-8')

def test_remote_runner_uses_https_api_not_database():
    assert "CODE_RUNNER_SERVER_URL" in WORKER
    assert "Authorization':'Bearer '" in WORKER
    assert 'from app import' not in WORKER
    assert 'sqlalchemy' not in WORKER.lower()
    assert 'DATABASE_URL' not in START
    assert 'gcloud' not in START.lower()

def test_server_claim_is_atomic_and_leased():
    assert "@app.post('/api/code-runner/claim')" in APP
    assert 'with_for_update(skip_locked=True)' in APP
    assert 'CODE_RUNNER_LEASE_SECONDS' in APP
    assert 'runner_claim_token' in APP
    assert 'secrets.compare_digest' in APP
