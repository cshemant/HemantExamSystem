
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
