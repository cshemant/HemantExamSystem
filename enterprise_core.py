"""Enterprise-grade exam scoring and answer normalization helpers.

This module is deliberately framework-independent so correctness can be tested
without starting Flask or touching the database.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

QUESTION_TYPE_LABELS = {
    "single_choice": "Single Choice (MCQ)",
    "multiple_select": "Multiple Select",
    "true_false": "True / False",
    "numerical": "Numerical Answer",
    "short_text": "Short Text",
    "essay": "Descriptive / Essay",
}

QUESTION_TYPE_ALIASES = {
    "mcq": "single_choice",
    "single": "single_choice",
    "single_choice": "single_choice",
    "single choice": "single_choice",
    "single-choice": "single_choice",
    "msq": "multiple_select",
    "multi": "multiple_select",
    "multiple": "multiple_select",
    "multiple_select": "multiple_select",
    "multiple select": "multiple_select",
    "multiple-select": "multiple_select",
    "tf": "true_false",
    "t/f": "true_false",
    "true_false": "true_false",
    "true false": "true_false",
    "true/false": "true_false",
    "numeric": "numerical",
    "number": "numerical",
    "numerical": "numerical",
    "short": "short_text",
    "text": "short_text",
    "short_text": "short_text",
    "short text": "short_text",
    "essay": "essay",
    "descriptive": "essay",
    "long_text": "essay",
    "long text": "essay",
}


def canonical_question_type(value: Any) -> str:
    raw = str(value or "single_choice").strip().lower().replace("-", "_")
    return QUESTION_TYPE_ALIASES.get(raw, QUESTION_TYPE_ALIASES.get(raw.replace("_", " "), "single_choice"))


def _canonical_option_set(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        parts = [str(x) for x in value]
    else:
        raw = str(value or "").upper().strip()
        parts = re.split(r"[,;|\s]+", raw) if any(ch in raw for ch in ",;| ") else list(raw)
    options = sorted({p.strip().upper() for p in parts if p.strip().upper() in {"A", "B", "C", "D"}})
    return ",".join(options)


def _canonical_bool(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"true", "t", "1", "yes", "y", "a"}:
        return "true"
    if raw in {"false", "f", "0", "no", "n", "b"}:
        return "false"
    return ""


def _canonical_decimal(value: Any) -> str:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return ""
    if not number.is_finite():
        return ""
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _canonical_text(value: Any, case_sensitive: bool = False) -> str:
    raw = " ".join(str(value or "").strip().split())
    return raw if case_sensitive else raw.casefold()


def question_answer_key(question: Any) -> str:
    key = str(getattr(question, "answer_key", "") or "").strip()
    if key:
        return key
    return str(getattr(question, "correct_answer", "") or "").strip()


def normalize_answer(question: Any, value: Any) -> str:
    qtype = canonical_question_type(getattr(question, "question_type", "single_choice"))
    if qtype == "single_choice":
        raw = str(value or "").strip().upper()
        return raw if raw in {"A", "B", "C", "D"} else ""
    if qtype == "multiple_select":
        return _canonical_option_set(value)
    if qtype == "true_false":
        return _canonical_bool(value)
    if qtype == "numerical":
        return _canonical_decimal(value)
    if qtype == "short_text":
        return _canonical_text(value, bool(getattr(question, "answer_case_sensitive", False)))
    if qtype == "essay":
        # Essay answers are preserved for manual grading; whitespace is normalized
        # only at the edges so paragraphs/newlines remain available to the grader.
        return str(value or "").strip()
    return ""


def normalized_key(question: Any) -> str:
    qtype = canonical_question_type(getattr(question, "question_type", "single_choice"))
    key = question_answer_key(question)
    if qtype == "short_text":
        # Multiple accepted short answers may be separated with |.
        return "|".join(_canonical_text(x, bool(getattr(question, "answer_case_sensitive", False))) for x in key.split("|") if x.strip())
    return normalize_answer(question, key)


def is_answer_correct(question: Any, answer: Any) -> bool:
    qtype = canonical_question_type(getattr(question, "question_type", "single_choice"))
    student = normalize_answer(question, answer)
    if not student:
        return False
    if qtype == "short_text":
        accepted = [x for x in normalized_key(question).split("|") if x]
        return student in accepted
    if qtype == "essay":
        # Essay correctness is determined by the manual grading workflow.
        return False
    if qtype == "numerical":
        key = normalized_key(question)
        if not key:
            return False
        try:
            tolerance = Decimal(str(getattr(question, "answer_tolerance", "") or "0").strip() or "0")
            if tolerance < 0:
                tolerance = -tolerance
            return abs(Decimal(student) - Decimal(key)) <= tolerance
        except (InvalidOperation, ValueError):
            return False
    return student == normalized_key(question)


def validate_question_definition(
    question_type: Any,
    question_text: str,
    options: dict[str, str],
    answer_key: Any,
    answer_tolerance: Any = "",
) -> str | None:
    """Return a user-facing validation error or None."""
    qtype = canonical_question_type(question_type)
    if not str(question_text or "").strip():
        return "Question text is required."
    if qtype in {"single_choice", "multiple_select"}:
        if any(not str(options.get(k, "") or "").strip() for k in "ABCD"):
            return "Options A, B, C and D are required for choice questions."
        if qtype == "single_choice":
            key = str(answer_key or "").strip().upper()
            if key not in {"A", "B", "C", "D"}:
                return "Choose one correct answer (A, B, C or D)."
        elif not _canonical_option_set(answer_key):
            return "Choose at least one correct option for a multiple-select question."
    elif qtype == "true_false":
        if not _canonical_bool(answer_key):
            return "Choose True or False as the correct answer."
    elif qtype == "numerical":
        if not _canonical_decimal(answer_key):
            return "Enter a valid numerical correct answer."
        if str(answer_tolerance or "").strip():
            try:
                tolerance = Decimal(str(answer_tolerance).strip())
                if tolerance < 0:
                    return "Numerical tolerance cannot be negative."
            except InvalidOperation:
                return "Numerical tolerance must be a valid number."
    elif qtype == "short_text":
        if not str(answer_key or "").strip():
            return "Enter at least one accepted short-text answer."
    elif qtype == "essay":
        # No answer key is required; faculty assign marks after submission.
        pass
    return None
