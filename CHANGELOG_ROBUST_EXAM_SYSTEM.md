## V21.1 – Dedicated Super Admin username

- Added `SUPER_ADMIN_USERNAME` with backwards compatibility for `ADMIN_USERNAME`.
- Added optional `SUPER_ADMIN_PASSWORD`, falling back to the existing `ADMIN_PASSWORD`.
- When `SUPER_ADMIN_USERNAME` differs from legacy `admin`, the old `admin` account is automatically migrated to an active Faculty account while preserving its password hash.
- The legacy Admin row is removed after migration so `admin` no longer retains Super Admin authority.
- Reserved the configured Super Admin username so it cannot also be created as a normal staff account.

## V14.2 – Custom Subject Catalog

- Added persistent custom subject creation with faculty-assigned categories.
- Added categorized subject selectors to Question Bank create/edit screens.
- Added Category + Subject filtering and category labels in the Question Bank table.
- Added default Course/Semester auto-fill when a catalog subject is selected.
- Added category-aware CSV/Excel Question Bank import templates.
- Existing and preloaded subjects are registered automatically without deleting prior data.


## V8 - Preloaded engineering question banks
- Added **44** ready-made engineering subject banks.
- Added **745** MCQs organized into **5 units per subject**.
- Every prepared item includes the correct answer, difficulty, Bloom level and CO mapping.
- Added one-click **Activate Bank** and category activation.
- Added **Create Ready Exam**: a 15-question pool is created and each student receives 10 randomized questions.
- Added master CSV/Excel export for the prepared library.
- Added starter-bank coverage across Common Engineering, CSE/IT, ECE/EE, Mechanical and Civil subjects.
- Built-in content is explicitly marked as a general starter bank that should be reviewed against the institution's exact syllabus before high-stakes use.

# Robust Examination System Upgrade

Implemented on top of the supplied V5 project without removing the existing online/offline, login, student import, exam, autosave, resume, timer, scoring or result functionality.

## Added
- Reusable Question Bank
- Question Bank CSV/XLSX templates and bulk import
- Subject, Semester, Unit, Topic, Difficulty, Bloom Level, CO mapping and Tags
- Draft/Approved question workflow
- Question revision/version history
- Add selected approved bank questions to an exam
- Exam blueprint generator
- Unit-wise weightage
- Easy/Medium/Hard weightage
- Question pool size vs questions-per-student
- Random per-student question subset
- Stable option shuffling per attempt
- Browser-level tab/full-screen integrity event logging
- Result CSV and Excel export
- Question item analysis: usage, correct rate, observed difficulty and discrimination indicator
- Faculty user accounts with role separation
- Administrator audit trail
- Offline database backup and restore
- HOD presentation guide
- Sample Question Bank CSV/XLSX

## Important integrity behavior
Once an exam has attempts, blueprint regeneration is blocked so the question pool cannot silently change underneath recorded attempts/results.

## Secure-browser scope
The integrity monitoring added here is browser-level. It records tab/full-screen exits when enabled. It does not claim to be an operating-system lockdown browser.

## V79.1 - Practical Exam Attendance Visibility
- Practical Exam attendance is now auto-awarded only for a clean, on-time submitted attempt with zero integrity violations.
- Existing faculty Absent decisions are preserved.
- Student Practical Marks now shows `Present · marks` / `Absent · 0` instead of a bare number/dash.
- Opening Practical Marks repairs eligible older submitted practical attempts so attendance becomes visible without manual re-entry.

## V2.35.0 / V109.1
- Voice requests with explicit question counts now auto-fill the exam rather than creating an empty manual draft.
- Reuses approved bank questions first and AI-generates the shortage.
- Supports up to 100 requested questions with <=20-question provider batches and duplicate avoidance.
- Confirmed syllabus is preferred; legacy subjects can fall back to approved Question Bank context without university-specific code.
- Curriculum requests may target All Units.
