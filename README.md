# Learn with Hemant — Exam System V2 (Dual Mode)

One Flask codebase, two deployment modes:

- **Offline / LAN:** SQLite (`exam.db`) on the faculty/server computer.
- **Online:** PostgreSQL on a hosted server/VPS/container platform.

The exam workflow remains intentionally simple: students, exams, MCQs, CSV import, activation, randomized question order, server-controlled timer, autosave, resume, automatic submission, automatic scoring, and results.

## 1) Offline / LAN mode

Run `setup_once.bat` once while Internet is available to install Python dependencies. Then run `run_server.bat`.

Default offline admin (from `.env.example`):

```text
Username: admin
Password: Admin@123
```

Faculty PC:

```text
http://127.0.0.1:8080
```

Students on the same LAN/Wi-Fi:

```text
http://SERVER-IP:8080
```

The server prints the likely LAN URL when it starts.

### Upgrading from V1 without losing your existing offline data

If your V1 folder already contains `exam.db`, copy that exact file into the V2 project folder before starting V2. The V2 SQLAlchemy models intentionally keep the V1 table/column structure compatible, so the same SQLite database can be read directly.

Back up `exam.db` before upgrading.

## 2) Online / PostgreSQL mode

Install online dependencies:

```bash
python -m pip install -r requirements-online.txt
```

Copy `.env.online.example` to `.env` and set:

```text
APP_MODE=online
SECRET_KEY=<long-random-value>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
PORT=8080
COOKIE_SECURE=1
WEB_CONCURRENCY=3
```

Run behind a production WSGI server:

```bash
gunicorn --workers 3 --threads 4 --bind 0.0.0.0:8080 wsgi:app
```

Use HTTPS and a domain/reverse proxy in production.

## 3) Docker online test

The included `docker-compose.online.yml` starts PostgreSQL + the web app. Change all example passwords/secrets before exposing it publicly.

```bash
docker compose -f docker-compose.online.yml up --build
```

The local Docker Compose file sets `COOKIE_SECURE=0` so HTTP localhost testing works. In production behind HTTPS, set `COOKIE_SECURE=1`.

Then open:

```text
http://localhost:8080
```

## 4) How dual mode works

The application reads environment variables at startup:

```text
APP_MODE=offline
DATABASE_URL omitted
        ↓
SQLite: <project>/exam.db
```

or

```text
APP_MODE=online
DATABASE_URL=postgresql+psycopg://...
        ↓
PostgreSQL
```

The routes, templates, login, timer, scoring and exam logic are the same in both modes.

## 5) Online safeguards added in V2

- Database abstraction through SQLAlchemy
- PostgreSQL support
- CSRF checks for forms and autosave requests
- Secure/HttpOnly session cookies in production online mode
- Reverse-proxy support
- Environment-based secrets
- Database connection pre-ping
- `/health` endpoint for hosting health checks
- POST-only exam submission

## Important

V2 is dual-deploy, not yet a seamless offline-to-cloud synchronization engine. If Internet disappears during an online exam, the online server becomes unreachable unless the college switches students to a separately running LAN server. Automatic merging/synchronization between offline SQLite and online PostgreSQL should be implemented as a later version because it requires conflict-resolution and exam-integrity rules.
