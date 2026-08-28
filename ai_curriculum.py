"""Provider-neutral curriculum parsing and AI question generation helpers.

The Flask app owns persistence/permissions. This module only handles:
- extracting text from supported syllabus uploads,
- deterministic unit/topic parsing as a no-AI fallback,
- OpenAI/Gemini structured-output calls,
- validation/normalization of generated question payloads.
"""
from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None


class AIProviderError(RuntimeError):
    pass


@dataclass
class AIConfig:
    provider: str
    model: str
    api_key: str


def get_ai_config() -> AIConfig:
    provider = (os.getenv("AI_PROVIDER") or "none").strip().lower()
    if provider == "openai":
        return AIConfig(provider, (os.getenv("OPENAI_MODEL") or "gpt-5-mini").strip(), (os.getenv("OPENAI_API_KEY") or "").strip())
    if provider == "gemini":
        return AIConfig(provider, (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip(), (os.getenv("GEMINI_API_KEY") or "").strip())
    return AIConfig("none", "", "")


def ai_status() -> dict[str, Any]:
    cfg = get_ai_config()
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "configured": cfg.provider in {"openai", "gemini"} and bool(cfg.api_key),
    }


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 90) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:12000]
        # Provider error bodies can be very large. Surface the actionable message
        # instead of flashing the entire JSON response into the admin UI.
        message = detail
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                error = parsed.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message = error["message"]
                elif isinstance(error, str):
                    message = error
        except Exception:
            pass
        message = re.sub(r"\s+", " ", str(message)).strip()[:1200]
        raise AIProviderError(f"AI API HTTP {exc.code}: {message}") from exc
    except Exception as exc:
        raise AIProviderError(f"AI API request failed: {exc}") from exc
    try:
        return json.loads(body)
    except Exception as exc:
        raise AIProviderError("AI API returned a non-JSON response.") from exc


def _openai_output_text(data: dict[str, Any]) -> str:
    # The REST Responses API returns output items; SDKs also expose output_text.
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    texts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                value = content.get("text")
                if isinstance(value, str):
                    texts.append(value)
    return "\n".join(texts).strip()


def _call_openai(prompt: str, schema_name: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None) -> dict[str, Any]:
    cfg = get_ai_config()
    if not cfg.api_key:
        raise AIProviderError("OPENAI_API_KEY is not configured.")
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    if image:
        raw, mime = image
        content.append({"type": "input_image", "image_url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"})
    payload = {
        "model": cfg.model,
        "store": False,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    data = _http_json("https://api.openai.com/v1/responses", payload, {"Authorization": f"Bearer {cfg.api_key}"})
    text = _openai_output_text(data)
    if not text:
        err = data.get("error") or data.get("incomplete_details") or "No structured text returned."
        raise AIProviderError(f"OpenAI returned no usable output: {err}")
    try:
        return json.loads(text)
    except Exception as exc:
        raise AIProviderError("OpenAI structured output could not be parsed as JSON.") from exc


def _gemini_generate_content_output_text(data: dict[str, Any]) -> str:
    """Extract text from the legacy GenerateContent response."""
    texts: list[str] = []
    for candidate in data.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        for part in (content or {}).get("parts") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "\n".join(texts).strip()


def _gemini_interaction_output_text(data: dict[str, Any]) -> str:
    """Extract the last model text from a raw Gemini Interactions response.

    The SDK exposes ``interaction.output_text`` as a convenience property, but the
    REST response contains ``steps[].content[].text``.  Keeping this extractor in
    our provider adapter avoids an SDK dependency and works with Render's current
    lightweight requirements.
    """
    texts: list[str] = []
    for step in data.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for content in step.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "text" and isinstance(content.get("text"), str):
                texts.append(content["text"])
    return "\n".join(texts).strip()


def _call_gemini_interactions(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Use Gemini's current Interactions structured-output API for 3.x models."""
    cfg = get_ai_config()
    payload = {
        "model": cfg.model,
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
        # Question generation is stateless; do not retain interactions server-side.
        "store": False,
    }
    data = _http_json(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        payload,
        {"x-goog-api-key": cfg.api_key},
        timeout=120,
    )
    status = str(data.get("status") or "").lower()
    if status and status not in {"completed", "incomplete"}:
        errors = data.get("errors") or []
        raise AIProviderError(f"Gemini interaction did not complete ({status}): {str(errors)[:800]}")
    text = _gemini_interaction_output_text(data)
    if not text:
        errors = data.get("errors") or "No structured text returned."
        raise AIProviderError(f"Gemini returned no usable structured output: {str(errors)[:800]}")
    try:
        return json.loads(text)
    except Exception as exc:
        raise AIProviderError("Gemini structured output could not be parsed as JSON.") from exc


def _call_gemini_generate_content(prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None) -> dict[str, Any]:
    """Legacy GenerateContent path retained for Gemini 2.x and image parsing."""
    cfg = get_ai_config()
    parts: list[dict[str, Any]] = [{"text": prompt}]
    if image:
        raw, mime = image
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode("ascii")}})
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.model}:generateContent"
    data = _http_json(url, payload, {"x-goog-api-key": cfg.api_key}, timeout=120)
    text = _gemini_generate_content_output_text(data)
    if not text:
        reason = data.get("promptFeedback") or "No structured text returned."
        raise AIProviderError(f"Gemini returned no usable output: {reason}")
    try:
        return json.loads(text)
    except Exception as exc:
        raise AIProviderError("Gemini structured output could not be parsed as JSON.") from exc


def _call_gemini(prompt: str, schema_name: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None) -> dict[str, Any]:
    del schema_name  # Gemini does not require a schema name.
    cfg = get_ai_config()
    if not cfg.api_key:
        raise AIProviderError("GEMINI_API_KEY is not configured.")

    # Gemini 3.x structured output is documented on the Interactions API.  V110
    # still sent 3.6 Flash through legacy GenerateContent; that could surface as
    # a provider/server failure after the confirmation click.  Text generation
    # now uses Interactions for all Gemini 3.x models.  Image syllabus parsing
    # keeps the legacy multimodal route until that path is migrated separately.
    if cfg.model.startswith("gemini-3") and image is None:
        return _call_gemini_interactions(prompt, schema)
    return _call_gemini_generate_content(prompt, schema, image=image)


def structured_generate(prompt: str, schema_name: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None) -> dict[str, Any]:
    cfg = get_ai_config()
    if cfg.provider == "openai":
        return _call_openai(prompt, schema_name, schema, image=image)
    if cfg.provider == "gemini":
        return _call_gemini(prompt, schema_name, schema, image=image)
    raise AIProviderError("No AI provider is configured. Set AI_PROVIDER to openai or gemini and add its API key.")


def extract_upload_text(filename: str, content_type: str, raw: bytes) -> tuple[str, str]:
    """Return (text, source_type). Images intentionally return blank text for AI vision parsing."""
    name = (filename or "").lower()
    mime = (content_type or mimetypes.guess_type(filename or "")[0] or "application/octet-stream").lower()
    if mime.startswith("text/") or name.endswith((".txt", ".md", ".csv")):
        return raw.decode("utf-8", errors="replace"), "text"
    if name.endswith(".pdf") or mime == "application/pdf":
        if PdfReader is None:
            raise ValueError("PDF parsing requires the pypdf package.")
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text, "pdf"
    if name.endswith(".docx") or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if Document is None:
            raise ValueError("DOCX parsing requires the python-docx package.")
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text, "docx"
    if mime.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "", "image"
    raise ValueError("Supported syllabus formats are PDF, DOCX, TXT/MD/CSV, PNG, JPG/JPEG and WEBP.")


UNIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_no": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "raw_text": {"type": "string"},
                    "topics": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["unit_no", "title", "summary", "raw_text", "topics"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "units"],
    "additionalProperties": False,
}


def _roman_to_int(value: str) -> int | None:
    value = value.upper().strip()
    roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
    if value.isdigit():
        return int(value)
    return roman.get(value)


def deterministic_syllabus_parse(text: str) -> dict[str, Any]:
    clean = "\n".join(line.strip() for line in (text or "").replace("\r", "\n").split("\n") if line.strip())
    if not clean:
        return {"summary": "", "units": []}
    rx = re.compile(r"(?im)^\s*(?:unit|module)\s*[-:]?\s*([0-9]+|[ivx]+)\b\s*[-:–—]?\s*(.*)$")
    matches = list(rx.finditer(clean))
    units: list[dict[str, Any]] = []
    if matches:
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
            body = clean[start:end].strip(" \n:-–—")
            raw_no = match.group(1)
            no = _roman_to_int(raw_no)
            unit_no = str(no if no is not None else raw_no)
            title = (match.group(2) or "").strip(" :-–—") or f"Unit {unit_no}"
            topic_source = body or title
            topics = [p.strip(" .-•") for p in re.split(r"[;•\n]+", topic_source) if len(p.strip(" .-•")) >= 3]
            if len(topics) <= 1 and "," in topic_source:
                topics = [p.strip(" .-•") for p in topic_source.split(",") if len(p.strip(" .-•")) >= 3]
            units.append({"unit_no": unit_no, "title": title[:250], "summary": body[:800], "raw_text": body[:12000], "topics": topics[:80]})
    else:
        # Preserve unstructured uploads as one unit so a faculty member can edit it.
        topics = [p.strip(" .-•") for p in re.split(r"[;•\n]+", clean) if len(p.strip(" .-•")) >= 3]
        units.append({"unit_no": "1", "title": "Unit 1", "summary": clean[:800], "raw_text": clean[:12000], "topics": topics[:80]})
    return {"summary": clean[:1000], "units": units}


def analyze_syllabus(text: str, *, subject_name: str, image: tuple[bytes, str] | None = None) -> dict[str, Any]:
    status = ai_status()
    if status["configured"]:
        prompt = (
            "Extract the academic syllabus into JSON. Do not invent topics that are not present. "
            "Preserve the source's unit/module numbering. For each unit give a short title, short summary, "
            "the source text relevant to that unit, and a clean list of teachable topics. "
            f"Subject: {subject_name}.\n\nSYLLABUS TEXT:\n{text[:80000]}"
        )
        return structured_generate(prompt, "syllabus_structure", UNIT_SCHEMA, image=image)
    if image:
        raise AIProviderError("Image syllabus parsing needs an AI provider because server-side OCR is intentionally not used.")
    return deterministic_syllabus_parse(text)


QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_type": {"type": "string", "enum": ["single_choice", "multiple_select", "true_false", "numerical", "short_text", "essay"]},
                    "question": {"type": "string"},
                    "option_a": {"type": "string"},
                    "option_b": {"type": "string"},
                    "option_c": {"type": "string"},
                    "option_d": {"type": "string"},
                    "answer_key": {"type": "string"},
                    "answer_tolerance": {"type": "string"},
                    "answer_case_sensitive": {"type": "boolean"},
                    "marks": {"type": "integer", "minimum": 1, "maximum": 100},
                    "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
                    "bloom_level": {"type": "string", "enum": ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]},
                    "topic": {"type": "string"},
                    "co_mapping": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["question_type", "question", "option_a", "option_b", "option_c", "option_d", "answer_key", "answer_tolerance", "answer_case_sensitive", "marks", "difficulty", "bloom_level", "topic", "co_mapping", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def _question_rules() -> str:
    return """
Rules:
- Avoid duplicates and near-duplicates.
- For single_choice and multiple_select, provide four plausible options A-D.
- For single_choice, answer_key must be exactly A, B, C, or D.
- For multiple_select, answer_key must be comma-separated option letters such as A,C.
- For true_false, answer_key must be true or false; option fields may be blank.
- For numerical, answer_key must be a numeric value and answer_tolerance may be 0 or a positive number.
- For short_text, answer_key may contain alternatives separated by |.
- For essay, answer_key may be blank because it is manually graded.
- Use Bloom levels from Remember, Understand, Apply, Analyze, Evaluate, Create.
- Provide a concise explanation/solution for faculty review.
- CO mapping may be blank when the supplied context does not provide CO information.
""".strip()


def generate_questions(*, institution: str, program: str, subject: str, unit_no: str, unit_title: str, syllabus_text: str, topics: list[str], requested_topic: str, count: int, difficulty: str, question_types: list[str] | None = None, avoid_questions: list[str] | None = None) -> dict[str, Any]:
    # Keep individual provider calls reasonably small. The Flask layer batches
    # larger exam requests (for example 60 or 100 questions) across calls.
    count = max(1, min(25, int(count)))
    requested_types = question_types or ["single_choice"]
    avoid = "\n".join(f"- {q}" for q in (avoid_questions or [])[-80:])
    prompt = f"""
Generate exactly {count} assessment questions as JSON for the curriculum below.
Institution: {institution}
Program/Curriculum: {program}
Subject: {subject}
Unit: {unit_no} {unit_title}
Requested topic focus: {requested_topic or 'entire selected unit'}
Requested difficulty: {difficulty}
Allowed question types: {', '.join(requested_types)}

Authoritative syllabus context (do not go outside this context):
{syllabus_text[:60000]}

Known topics: {', '.join(topics[:100])}

Questions already available/generated and therefore forbidden as duplicates:
{avoid or '- none supplied'}

- Stay within the supplied syllabus; do not introduce unrelated topics.
{_question_rules()}
""".strip()
    result = structured_generate(prompt, "question_batch", QUESTION_SCHEMA)
    questions = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(questions, list):
        raise AIProviderError("AI response did not contain a question list.")
    result["questions"] = questions[:count]
    return result


def generate_subject_context_questions(*, institution: str, subject: str, course_semester: str, unit: str, context_text: str, known_topics: list[str], requested_topic: str, count: int, difficulty: str, question_types: list[str] | None = None, avoid_questions: list[str] | None = None) -> dict[str, Any]:
    """Generate questions when no confirmed syllabus has been uploaded yet.

    This is deliberately weaker than syllabus-grounded generation. The caller
    supplies existing Question Bank material as the allowed context so the model
    is not tied to any university-specific hard-coded syllabus. Generated rows
    remain review-pending drafts.
    """
    count = max(1, min(25, int(count)))
    requested_types = question_types or ["single_choice"]
    avoid = "\n".join(f"- {q}" for q in (avoid_questions or [])[-80:])
    prompt = f"""
Generate exactly {count} assessment questions as JSON using the subject context below.
Institution: {institution or 'Not specified'}
Subject: {subject}
Course/Semester: {course_semester or 'Not specified'}
Requested unit: {unit or 'All available units'}
Requested topic focus: {requested_topic or 'No additional topic restriction'}
Requested difficulty: {difficulty}
Allowed question types: {', '.join(requested_types)}

IMPORTANT: No confirmed syllabus is available for this request. Treat the supplied
Question Bank context as the boundary. Stay close to its units/topics/concepts and
do not invent institution-specific syllabus coverage that is not evidenced here.

Existing Question Bank context:
{context_text[:60000]}

Known topics: {', '.join(known_topics[:120])}

Questions already available/generated and therefore forbidden as duplicates:
{avoid or '- none supplied'}

{_question_rules()}
""".strip()
    result = structured_generate(prompt, "question_batch", QUESTION_SCHEMA)
    questions = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(questions, list):
        raise AIProviderError("AI response did not contain a question list.")
    result["questions"] = questions[:count]
    return result
