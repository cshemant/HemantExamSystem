# Learn with Hemant — Exam System V2.02

One codebase supports:

- **Online mode:** Flask + PostgreSQL (for `exam.learnwithhemant.com`).
- **Offline/LAN source mode:** Flask + SQLite.
- **Offline V2.02 Windows distribution:** a compiled one-click executable built automatically by GitHub Actions.

The exam workflow includes student/admin login, bulk student import from CSV/XLSX, exams, question import, randomized question order, server timer, autosave, resume, automatic submission/scoring, and results.

## Online deployment

Set environment variables on the hosting platform:

```text
APP_MODE=online
SECRET_KEY=<long-random-secret>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
DATABASE_URL=<PostgreSQL URL>
COOKIE_SECURE=1
```

Install:

```bash
pip install -r requirements-online.txt
```

Start:

```bash
gunicorn wsgi:app
```

### Permanent offline download route

The login page links to:

```text
https://exam.learnwithhemant.com/download/offline
```

That URL is intentionally owned by the application and remains stable. It redirects to `OFFLINE_DOWNLOAD_URL`, so the binary can later move from GitHub Releases to Cloudflare R2 or another storage provider without changing the login-page HTML.

Default V2.02 target:

```text
https://github.com/cshemant/HemantExamSystem/releases/download/v2.02/LearnWithHemant_Offline_Exam_V2.02_Windows.zip
```

Override it in Render/hosting environment variables when needed:

```text
OFFLINE_DOWNLOAD_URL=https://your-public-storage.example/offline-v2.02.zip
```

## Offline V2.02 — end-user experience

The release package contains a compiled Windows executable:

```text
LearnWithHemantOfflineExam.exe
```

Faculty workflow:

1. Download and extract the ZIP.
2. Double-click `LearnWithHemantOfflineExam.exe`.
3. The local server starts and the browser opens automatically.
4. On first launch, faculty creates an administrator username/password.
5. Students on the same LAN/Wi-Fi open the LAN URL shown in the launcher window.
6. Internet is not required while the exam is running.

Offline data persists in:

```text
%LOCALAPPDATA%\LearnWithHemantExam\
```

This keeps the SQLite database separate from the executable, so replacing the executable with a later version does not overwrite exam data.

## Building and publishing Offline V2.02

The repository includes:

```text
.github/workflows/build-offline-v202.yml
```

The workflow uses a Windows GitHub runner and Nuitka to compile the application. Raw `.py`, template and CSS project files are not included as editable files in the end-user ZIP.

After committing V2.02, create and push the release tag:

```bash
git add .
git commit -m "Add Offline Exam V2.02 distribution"
git push
git tag v2.02
git push origin v2.02
```

GitHub Actions then creates the permanent Release assets:

```text
LearnWithHemant_Offline_Exam_V2.02_Windows.zip
LearnWithHemant_Offline_Exam_V2.02_Windows.zip.sha256
```

The fixed download URL becomes valid after that release workflow completes.

## Security design

- No default administrator password in the compiled offline distribution.
- First-run administrator setup.
- Administrator/student passwords are stored as hashes.
- CSRF protection on state-changing requests.
- HttpOnly/SameSite cookies; Secure cookies online.
- Additional browser security headers.
- Mutable local database is stored outside the executable under the current Windows user's LocalAppData.
- End-user package contains a compiled executable instead of editable project source/templates.
- SHA-256 checksum is published with the release.

A distributed desktop/server executable cannot be made impossible to reverse-engineer by a machine administrator. For high-stakes exams, use controlled lab PCs, OS account restrictions, backups, and code-sign the Windows executable. Also note that if the GitHub **source repository itself is public**, the source remains publicly readable regardless of binary packaging. To hide source code, keep the source repository private and host only the compiled ZIP on a separate public binary/storage endpoint, then set `OFFLINE_DOWNLOAD_URL` to that endpoint.

## Source-based offline/LAN mode

For development/testing only:

```bash
python -m pip install -r requirements.txt
python app.py
```

Faculty PC:

```text
http://127.0.0.1:8080
```

Student LAN access:

```text
http://SERVER-IP:8080
```

The compiled V2.02 distribution is preferred for colleges/faculty because it avoids requiring Python installation and does not expose the editable project files in the download package.
