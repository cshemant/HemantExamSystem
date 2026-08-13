# Staff Password Reset Workflow

## Permissions

- **Super Admin** can reset the password of any database-backed staff account: Faculty, HOD, or Exam Controller (including a legacy `admin` account after it has been migrated to a staff role).
- **HOD** can reset the password of **Faculty accounts only**.
- Faculty and Exam Controller users cannot access staff password management.
- The configured **Super Admin's own password** remains controlled by `SUPER_ADMIN_PASSWORD` / `ADMIN_PASSWORD` in the deployment environment; it is not exposed in the Staff Users page.

## User interface

A **Staff** link is visible in desktop and mobile navigation for Super Admin and HOD users.

- Super Admin sees staff creation, role/department update, enable/disable, and **Reset Password**.
- HOD sees only Faculty accounts and the **Reset Password** action.

## Password reset

1. Open **Staff**.
2. Select **Reset Password** for the target account.
3. Enter and confirm a new password (minimum 10 characters).
4. Select **Save New Password**.

The password is stored only as a Werkzeug password hash. The plaintext password is never written to the audit trail. The audit trail records who performed the reset and which account/role was targeted.
