from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
AI=(ROOT/'ai_curriculum.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
VOICE=(ROOT/'static'/'voice_assistant.js').read_text(encoding='utf-8')
DASH=(ROOT/'templates'/'placement_dashboard.html').read_text(encoding='utf-8')
PASS=(ROOT/'templates'/'skill_passport.html').read_text(encoding='utf-8')


def test_python_parses():
    ast.parse(APP);ast.parse(AI)


def test_models_present():
    for name in ['PlacementSkill','PlacementExternalEvidence','PlacementRemedialPlan','PlacementExamMap']:
        assert f'class {name}(Base):' in APP


def test_routes_present():
    for route in ['/admin/placements','/admin/placements/mock','/admin/placements/evidence/import','/admin/placements/assign-remedial','/student/skill-passport']:
        assert route in APP


def test_ai_generator_present():
    assert 'def generate_placement_questions' in AI
    assert 'not an official employer paper' in AI


def test_navigation_present():
    assert 'Placement Readiness' in BASE
    assert 'Skill Passport' in BASE
    assert 'function placementMockCommand' in VOICE


def test_dashboard_features_present():
    for text in ['Company Drive Simulator','Curriculum ↔ Placement Gap','Import External Skill Evidence','Assign Improvement Plans']:
        assert text in DASH
    assert 'Verified Skill Evidence' in PASS
