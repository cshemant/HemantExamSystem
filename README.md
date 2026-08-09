# Learn with Hemant — Examination System V2.02+

A dual-mode examination platform for colleges and faculty. The same application supports online delivery and offline/LAN examinations, with a reusable academic Question Bank and controlled examination workflow.

## Core examination workflow
- Student and Faculty/Admin login
- Bulk student import from CSV/XLSX
- Reusable Question Bank
- Subject, Semester, Unit, Topic, Difficulty, Bloom Level, CO mapping and Tags
- Draft/Approved question workflow
- Question version history
- CSV/XLSX Question Bank import and templates
- Add selected approved questions to an exam
- Exam blueprint generation using Unit and Difficulty weightage
- Larger question pool + randomized per-student subset
- Option shuffling with stable answer mapping
- Autosave, Resume, Server Timer and automatic submission/scoring
- Browser-level integrity event logging (tab/full-screen exits)
- Results filtering and CSV/XLSX export
- Question/item analytics
- Role-based faculty accounts
- Administrator audit trail
- Offline database backup/restore

## Online deployment
Set:

```text
APP_MODE=online
SECRET_KEY=<long-random-secret>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
DATABASE_URL=<PostgreSQL URL>
COOKIE_SECURE=1
```

Install and start:

```bash
pip install -r requirements-online.txt
gunicorn wsgi:app
```

## Offline / LAN mode
For source testing:

```bash
python -m pip install -r requirements.txt
python app.py
```

Faculty PC:

```text
http://127.0.0.1:8080
```

Students on the same LAN/Wi-Fi:

```text
http://SERVER-IP:8080
```

The Wi-Fi/LAN does not need Internet access.

## Question Bank import format
Use the in-app CSV/XLSX template. Main columns:

```text
subject,course_semester,unit,topic,question,option_a,option_b,option_c,option_d,correct_answer,marks,difficulty,bloom_level,co_mapping,tags,status
```

## Exam Blueprint
A faculty member can define:
- Questions per student
- Question pool size
- Easy / Medium / Hard percentages
- Unit distribution such as `1:20, 2:30, 3:30, 4:20`
- Randomized question selection/order
- Option shuffling
- Browser integrity monitoring threshold

The generator uses only **approved** Question Bank items. Once attempts begin, the generated question pool is locked from regeneration to protect result integrity.

## Governance
- Faculty accounts avoid sharing the administrator password.
- Faculty can manage students, Question Bank, exams, results and analytics.
- Administrator-only controls include faculty account management, audit logs and recovery tools.
- Editing a Question Bank item preserves a revision record; faculty edits return the item to Draft until approved again.

## Offline recovery
In offline mode, **System → Download Backup** creates a consistent `.db` snapshot. The same page can restore a valid backup. Back up before important examinations.

## Security notes
- Passwords are stored as hashes.
- CSRF protection is enforced on state-changing requests.
- Session cookies are HttpOnly/SameSite and Secure in online mode.
- Browser security headers are enabled.
- Browser integrity monitoring is **not** an OS-level lockdown browser. For high-stakes exams, use controlled lab PCs and a dedicated secure-browser/kiosk layer.
- The downloadable Windows binary should be code-signed and security-validated before institutional distribution.

## Presentation
See `HOD_PRESENTATION_GUIDE.md` for the recommended live demonstration and likely HOD questions.
