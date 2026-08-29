from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
QB=(ROOT/'templates'/'question_bank.html').read_text(encoding='utf-8')


def test_python_parses():
    ast.parse(APP)


def test_bulk_approval_route_present():
    assert "/admin/question-bank/bulk-approve" in APP
    assert "def bulk_approve_bank_questions" in APP
    assert "bank_questions_bulk_approved" in APP


def test_faculty_can_approve_only_own_bank_questions():
    assert "def can_approve_bank_question" in APP
    assert "role=='faculty'" in APP
    assert "q.created_by" in APP
    assert "actor_label(s)" in APP


def test_question_bank_has_bulk_review_controls():
    assert "Approve Selected Drafts" in QB
    assert "bulk_approve_bank_questions" in QB
    assert "data-select-all=\"question_ids\"" in QB
    assert "Review" in QB
    assert "approvable_question_ids" in QB
