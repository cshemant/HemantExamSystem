# Windows Release Signing

The GitHub Actions workflow now supports optional Authenticode signing for both the compiled executable and the installer.

Configure repository secrets:
- `WINDOWS_CERT_BASE64` — Base64-encoded `.pfx` code-signing certificate.
- `WINDOWS_CERT_PASSWORD` — Password for the `.pfx` certificate.

If these secrets are present, the workflow signs the executable and installer with SHA-256 and a timestamp before publishing release assets. If they are absent, the build still succeeds but remains unsigned.

A signed release improves publisher identity and reputation, but it does not guarantee that SmartScreen or antivirus products will never show a warning. Never ask institutional users to disable antivirus or bypass security protections.
