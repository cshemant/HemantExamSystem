# Learn with Hemant — Examination System V2.10 Enterprise


## V2.20 / V78.1 — Practical Exam anti-cheating enforcement

Practical Exams now receive a one-time secure default profile: randomized questions/options, full-screen monitoring, rotating PIN + single-device lock, a strict common start with 5-minute grace, warning/final-warning/auto-submit at 3 integrity violations, delayed results/answer review until the common end, and an optional per-session IP/roll-number lock. See `V78_1_PRACTICAL_ANTI_CHEATING.md`.

## V28 Student Practice & Learning Centre

V28 adds a protected student practice layer: published question pools, unit/difficulty practice, timed mocks, wrong-answer retry, bookmarks, explanations, weak-area analytics and faculty-controlled previous-paper release. Existing Question Bank items remain confidential (`Official Exam Only`) until staff explicitly publish them. See `V28_STUDENT_PRACTICE_CENTRE.md`.

A dual-mode examination platform for colleges and faculty. The same application supports online delivery and offline/LAN examinations, with a reusable academic Question Bank and controlled examination workflow.

## Core examination workflow
- Student and Faculty/Admin login
- Bulk student import from CSV/XLSX
- Reusable Question Bank
- Multiple assessment types: single choice, multiple select, true/false, numerical tolerance, short text and descriptive/essay with manual grading
- Subject, Semester, Unit, Topic, Difficulty, Bloom Level, CO mapping and Tags
- Draft/Approved question workflow
- Question version history
- CSV/XLSX Question Bank import and templates
- Add selected approved questions to an exam
- Exam blueprint generation using Unit and Difficulty weightage
- Larger question pool + randomized per-student subset
- Option shuffling with stable answer mapping
- Autosave, Resume, Server Timer and automatic submission/scoring
- Browser-level integrity event logging (tab/full-screen/copy/paste/context-menu events)
- Optional invigilator identity check-in before a candidate can start
- Live Exam Controller Command Centre with candidate heartbeat/connection state
- Results filtering and CSV/XLSX export
- Question/item analytics
- Role-based faculty accounts
- Administrator audit trail
- Offline database backup/restore
- Optional staff TOTP MFA, login throttling, stronger security headers and SQLite WAL reliability
- CO/PO/PSO attainment analytics and manual grading workflow for descriptive answers
- Optional bearer-auth integration API for exam/result synchronization
- Encrypted, authenticated Edge Exam Packages for central-to-campus LAN handoff

## Online deployment
Set:

```text
APP_MODE=online
SECRET_KEY=<long-random-secret>
SUPER_ADMIN_USERNAME=superadmin
LEGACY_ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
DATABASE_URL=<PostgreSQL URL>
COOKIE_SECURE=1
```

### Super Admin username migration
For an existing deployment where `admin` is currently the Super Admin and you want to keep the same `admin` username/password as a normal Faculty account:

1. Add `SUPER_ADMIN_USERNAME=superadmin` in the hosting environment.
2. Keep the existing `ADMIN_PASSWORD` value unchanged (or optionally set `SUPER_ADMIN_PASSWORD`).
3. Keep `LEGACY_ADMIN_USERNAME=admin` (this is also the default).
4. Redeploy. On startup, the system creates/updates `superadmin` as Super Admin and converts the old `admin` account to an active Faculty account using the same password hash.

Do not remove the Super Admin environment variable after migration; it identifies the privileged account on future starts.

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
category,subject,course_semester,unit,topic,question_type,question,option_a,option_b,option_c,option_d,correct_answer,answer_key,answer_tolerance,answer_case_sensitive,marks,difficulty,bloom_level,co_mapping,po_mapping,pso_mapping,tags,status
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
- Optional candidate identity check-in and heartbeat policy

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

## Institution-ready deployment layer (V14 package)
This package adds configurable institution branding, staff roles, batch/section management, exam approval, scheduled batch assignments, LAN QR access, institutional analytics, encrypted backup/restore and an installer/signing-ready Windows release workflow. See `INSTITUTION_DEPLOYMENT_GUIDE.md`, `SECURITY_PRIVACY_OVERVIEW.md` and `PILOT_PROPOSAL.md`.


## V2.10 Enterprise upgrade
See `ENTERPRISE_V27_IMPLEMENTATION.md` for the implemented enterprise upgrade, validation results and explicit limitations. See `ENTERPRISE_RELEASE_CHECKLIST.md` before every institutional pilot and `INTEGRATION_API.md` for the optional integration endpoints.

Run the regression suite after installing the project dependencies:

```bash
python -m unittest discover -s tests -v
```

For Windows kiosk-mode exam launch, see `secure_exam_launcher.py` and `build_secure_exam_client.bat`. This is a kiosk foundation and must not be represented as a certified OS-level lockdown browser without additional security validation.


## Encrypted Campus Edge packages
Set the same high-entropy `EXAM_PACKAGE_SIGNING_KEY` (32+ characters) on the authorized central server and campus node. From an exam Blueprint page, export a `.lwhexam` package; at the campus node, import it from **Exam Centre**. The question/answer payload is encrypted and authenticated, and modified packages are rejected. The imported exam remains inactive until local batch/session assignment and approval are completed.

A signed/encrypted `.lwhresults` archive can also be exported after an exam for secure reconciliation/audit transfer. Automatic bidirectional cloud/LAN synchronization is not claimed in this release.

## V107 Classroom Attendance

V107 adds timed batch/section attendance sessions with classroom LAN or approved CIDR verification, QR access, student login, optional WebAuthn fingerprint/passkey verification, one registered attendance device per student/site, live faculty roster, manual audited correction, device reset and CSV export. Biometrics never reach the server. See `V107_1_CLASSROOM_ATTENDANCE_SYSTEM.md`.

## V108 Multi-Institution Curriculum + AI Exams
V108 adds institution/program/curriculum/subject syllabus management plus provider-neutral OpenAI/Gemini structured question generation. AI-created questions enter the existing Question Bank as review-pending drafts and syllabus-grounded exams cannot be activated until generated questions are reviewed. See `V108_1_MULTI_INSTITUTION_AI_CURRICULUM.md`.


## V109 Voice/API Question Auto-fill
V109 fixes voice-created exams that previously fell back to an empty manual draft. Requests containing a question count now reuse approved Question Bank items and automatically generate only the shortage with the configured AI provider. Up to 100 questions are supported through batched generation. Confirmed institution syllabus data is preferred; otherwise existing approved Question Bank context is used and newly generated questions remain review-pending drafts. See `V109_1_VOICE_AI_AUTOFILL_FIX.md`.
