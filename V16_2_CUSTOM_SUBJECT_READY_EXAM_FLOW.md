# V16.2 — Custom Subject Ready Exam Flow

- Renamed the custom-subject action from **Create Draft Exam** to **Create Ready Exam** for consistency with preloaded subjects.
- Creating a ready exam still creates a safe **Draft / Inactive** exam; it does not bypass approval.
- After creation, the system now opens **Blueprint & Sessions** directly.
- Super Admin / HOD / Exam Controller can approve from that page.
- Once approved, **Activate for Students** is available on the same page.
- The page clearly shows whether the exam is **Active · Visible** or **Inactive · Hidden**.
- Student visibility rules remain unchanged: with no session, all registered students can see an active exam; with sessions, only assigned batch/section students can see it within the configured window.
