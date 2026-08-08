# Security and Distribution Notes — Offline V2.02

## What is protected

The public offline package is designed to be harder to casually modify than a source ZIP:

- GitHub Actions compiles `offline_launcher.py` and imported application modules with Nuitka on Windows.
- Templates/static assets are bundled into the executable rather than shipped as ordinary editable files.
- No `.env`, SQLite database, source ZIP, or default administrator password is included in the end-user package.
- The first launch requires faculty to create the administrator credential.
- Runtime data is stored under `%LOCALAPPDATA%\\LearnWithHemantExam`.
- Passwords remain hashed in the database.
- A SHA-256 checksum is published with the release ZIP.

## What cannot be guaranteed

No client-side/offline application can be made completely tamper-proof if a person has administrator access to the machine. A determined reverse engineer can inspect binaries and a local machine administrator can copy or alter local data.

For formal examinations, combine the application with:

- controlled college/lab computers;
- restricted Windows accounts;
- physical/network supervision;
- regular database backups;
- a code-signing certificate for the Windows executable;
- a private source repository.

## Important repository note

If `HemantExamSystem` remains a public GitHub repository, users can read/clone the original source even though the downloadable offline build is compiled. For stronger source protection, make the source repository private and publish the compiled ZIP to a separate public release repository, Cloudflare R2, or another public object store. The website does not need code changes for that move: update only the `OFFLINE_DOWNLOAD_URL` environment variable.
