# Security & Privacy Overview

## Implemented application controls
- Passwords stored using Werkzeug password hashing.
- CSRF protection on state-changing requests.
- Role-based staff access: Super Admin, Exam Controller, HOD and Faculty.
- 45-minute default inactivity timeout (configurable with `SESSION_TIMEOUT_MINUTES`).
- Exam approval before activation for Faculty-created workflows.
- Question pool locked after attempts begin.
- Question revision history and staff audit trail.
- Browser-level tab/fullscreen activity signals shown in detail only to staff.
- Encrypted offline backup format (`.lwhbackup`) using password-derived encryption.
- Secure cookie flags for online deployment and standard security headers.

## Deployment responsibilities
- Use HTTPS for online deployments.
- Keep PostgreSQL credentials and `SECRET_KEY` in hosting secrets, not source control.
- Use a trusted Windows code-signing certificate for distributed executables/installers.
- Define institutional retention rules for student data and exam results.
- Keep offline server laptops physically controlled during examinations.
- Review browser integrity events as signals, not automatic proof of malpractice.
