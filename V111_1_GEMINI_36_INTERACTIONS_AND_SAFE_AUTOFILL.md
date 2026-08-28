# V111.1 — Gemini 3.6 Interactions API + Safe AI Autofill

## Fixes
- Gemini 3.x text structured-output requests now use the current `/v1beta/interactions` API with `response_format` JSON Schema.
- Gemini 2.x and multimodal image syllabus parsing retain the legacy GenerateContent adapter.
- Raw Interactions REST output is parsed from `steps[].content[].text`.
- AI exam autofill now runs inside a database savepoint and catches unexpected provider/database exceptions so a provider failure does not turn the whole request into a bare HTTP 500 page.
- App version bumped to 2.35.1.

## Render staging
Recommended variables:
- `AI_PROVIDER=gemini`
- `GEMINI_MODEL=gemini-3.6-flash`
- `GEMINI_API_KEY=<secret>`

## Files changed
- `ai_curriculum.py`
- `app.py`
- `tests/test_v111_gemini_interactions.py`
