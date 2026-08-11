# Institution Deployment Guide

## Offline / LAN
1. Install `LearnWithHemantExamSetup_V2.02.exe` or run the approved one-click executable.
2. Complete Institution Setup and create the Super Admin.
3. Open **Batches & Sections** and create academic groups.
4. Import students using CSV/Excel.
5. Prepare Question Bank and exams.
6. Assign exam sessions to the required batch/section.
7. Open **Exam Centre** and test the displayed LAN URL/QR code from one student device.
8. Ensure Windows Firewall permits the application on the Private network profile.
9. Take an encrypted backup before the examination.
10. Keep the server window open until all students submit.

## Online
- Use PostgreSQL and HTTPS.
- Configure `APP_MODE=online`, `DATABASE_URL`, strong `SECRET_KEY`, `ADMIN_PASSWORD`, and secure cookies.
- Use the same Institution Profile and role workflow.

## White-label reuse
No source-code changes are required for another college. Update **System → Institution Profile** with the institution name, short name, logo, department, academic year and examination contact.
