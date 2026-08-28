# V109.1 — Voice AI Question Auto-fill Fix

## Problem fixed

V108 only used the syllabus-driven AI path when the spoken subject matched a confirmed Curriculum Subject. A legacy/preloaded Subject Catalog item such as Cyber Security therefore fell back to the old manual exam route even when the voice request explicitly asked for a question count. The resulting exam was empty and the Question Bank page only showed the questions that already existed.

## New behavior

A natural-language request such as:

`Create an exam for Cyber Security with 60 questions for 60 minutes`

now preserves both `60 questions` and `60 minutes` and enables AI auto-fill automatically.

1. Approved Question Bank items are copied first.
2. If the requested count is larger than the approved pool, the shortage is generated with the configured AI provider.
3. If the active institution has a confirmed syllabus for the subject, that syllabus is the authoritative generation context.
4. Otherwise, existing approved Question Bank units/topics/questions are used as a provider-neutral fallback context. This avoids hard-coded university logic.
5. New AI questions are stored as Draft / review-pending and are also copied into the draft exam immediately.
6. The exam cannot be activated until those AI questions are reviewed/approved.

Example: if Cyber Security has 15 approved questions and 60 are requested, the system reuses the 15 and asks the AI provider for the remaining 45. The exam draft contains up to 60 questions after generation.

## Large requests

Question-count requests now support up to 100 questions. AI generation is performed in batches of at most 20 questions with duplicate-avoidance context, rather than asking a provider for 60–100 questions in one response.

## All Units

A curriculum-backed voice request no longer requires the professor to state a unit. Omitting the unit means `All Units`, and the missing AI questions are distributed across the confirmed syllabus units.

## Manual UI

The existing-subject exam form now includes an optional `Auto-fill` checkbox, question count, difficulty and question type. This makes the same behavior testable without voice commands.

## Safety

AI-generated questions remain review-pending Draft items. Subject-context generation (used when no confirmed syllabus exists) is clearly tagged separately from syllabus-grounded generation.
