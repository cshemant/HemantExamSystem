# Public Guide & Update Workflow

The public guide system is designed so normal feature development does **not** require hand-editing the public update page or the live sitemap.

## When a release should be visible publicly

Add this safe metadata block near the top of the release note:

```html
<!-- PUBLIC_UPDATE
title: Short user-facing title
audience: Faculty, Admin, Student
guide: question-bank
date: 2026-08-30
summary: One short sentence explaining what changed for the user.
highlights: First benefit | Second benefit | Third benefit
-->
```

The `guide:` value is optional. Supported guide slugs are:

- `admin-assistant`
- `question-bank`
- `exam-delivery`
- `attendance`
- `practical-assessment`
- `placement-readiness`
- `student-practice`
- `offline-exams`

## What updates automatically after deployment

When a marked release note is deployed:

1. `/updates` adds the release to the public change feed.
2. `/updates/<release>` gets a public summary page.
3. The matching `/guides/<tool>` page shows it in the change history.
4. The matching guide visual shows the newest release as its **Latest improvement**.
5. The production `/sitemap.xml` automatically includes the new public update URL.

No database migration or CMS is required.

## Safety rule

Only text inside the `PUBLIC_UPDATE` metadata block is published. The rest of the Markdown release note is never rendered on the public website. This prevents source-code paths, internal diagnostics, implementation details and security notes from being exposed accidentally.

Do not put passwords, API keys, private URLs, student data or internal security details in a `PUBLIC_UPDATE` block.
