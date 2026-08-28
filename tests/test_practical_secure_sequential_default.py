from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BUILDER=(ROOT/'templates/exam_builder.html').read_text(encoding='utf-8')

def test_practical_defaults_enable_secure_sequential():
    start=APP.index('def apply_practical_exam_security_defaults')
    end=APP.index('def candidate_is_checked_in', start)
    block=APP[start:end]
    assert 'cfg.secure_sequential=True' in block
    assert 'cfg.sequential_min_seconds=max(1,int(cfg.sequential_min_seconds or 10))' in block

def test_blueprint_explains_practical_sequential_default():
    assert 'Secure Sequential (one question at a time)' in BUILDER
