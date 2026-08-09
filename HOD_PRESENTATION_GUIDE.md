# HOD Presentation Guide — Learn with Hemant Exam System

## One-line positioning
A dual-mode examination platform that can conduct exams entirely on a college LAN without Internet, or online for remote access, while keeping the same faculty and student workflow.

## Recommended 7-minute live demo
1. **Admin dashboard** — show student, question-bank, exam and attempt counts.
2. **Students** — show bulk CSV/XLSX login import.
3. **Question Bank** — show Unit, Topic, Difficulty, Bloom Level, CO mapping, tags, approval and version history.
4. **Exam Blueprint** — set questions per student, larger pool size, unit weightage and Easy/Medium/Hard percentages; generate the pool automatically.
5. **Offline LAN proof** — disconnect Internet, keep laptop and phone on the same Wi-Fi/LAN, open the laptop LAN URL on the phone and start the student exam.
6. **Integrity + delivery** — show autosave, resume, server timer, randomized paper and option shuffling. If enabled, browser tab/full-screen exits are logged for faculty review.
7. **Results & Analytics** — submit on phone; refresh faculty results; export Excel; open Question Analytics.

## Strong answers to likely questions
- **Why not Google Forms?** This system can continue on a local LAN with no Internet and keeps the examination workflow under institutional control.
- **How do we create hundreds of logins?** CSV/XLSX bulk import.
- **Do faculty recreate questions every time?** No. Approved questions remain in a reusable Question Bank.
- **Can papers follow syllabus weightage?** Yes. Blueprint generation supports unit and difficulty distribution.
- **Do all students receive the same paper?** Not necessarily. A larger pool can generate a different randomized subset and option order for each student.
- **What happens if a laptop fails?** Offline mode includes database backup and restore.
- **Can multiple faculty members work without sharing the admin password?** Yes. Role-based faculty accounts are supported; system recovery and user administration remain administrator-only.
- **How do we review question quality?** Item analysis shows usage, response correctness, observed difficulty and a discrimination indicator when enough responses exist.
- **Is this a full lockdown browser?** No. The current version provides browser-level integrity monitoring. OS-level lockdown/SEB-style control is a separate security layer and should not be overclaimed.

## Architecture to explain
Online mode: Browser → hosted application → managed server database.

Offline mode: Faculty laptop → local exam server → local database → students over the same LAN/Wi-Fi. Internet is not required during the exam.


## New: Ready-made unit-wise engineering question banks

The Question Bank now includes a built-in starter library covering **44 major/common engineering subjects** with **660 prepared MCQs**.

Each subject pack contains:
- 5 unit-wise sections
- 15 questions (3 per unit)
- Correct answers
- Easy / Medium / Hard classification
- Bloom level
- CO mapping
- Approved status after activation

Presentation shortcut:
1. Open **Question Bank**.
2. Show **Preloaded Unit-wise Subject Banks**.
3. Activate **CSE / IT Core** or a single subject.
4. Click **Create Ready Exam** for a subject.
5. The system creates a draft exam with a 15-question pool; each student receives 10 randomized questions.
6. Review the exam and click **Activate**.

Important positioning: the built-in content is a general starter bank and should be reviewed against the university's exact syllabus before high-stakes use.
