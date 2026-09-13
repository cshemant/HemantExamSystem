# Android App Lab (V2.52)

Students can edit `MainActivity.java`, `activity_main.xml`, and `AndroidManifest.xml`, select **Build APK**, download the signed debug APK, and install it on an Android phone.

## Automatic worker setup

Use the same `START_PRODUCTION_COMPILER.bat`, `START_STAGING_COMPILER.bat`, or `START_PRELIVE_COMPILER.bat` launcher. On its first run after this update, it detects a missing Android toolchain and automatically runs the existing installer. The installer:

- keeps existing Docker, Piston, language runtimes, profiles, SDK files, and signing key;
- installs Java 17 only when `javac` is unavailable;
- downloads Android command-line tools only when absent;
- installs Android platform/build tools and accepts their licences;
- creates one persistent debug signing key only when absent.

Later launches reuse everything. All APKs use the same package ID and signing key, so a newly downloaded build updates the student's previously installed Student App instead of creating duplicate applications.

## Safety and retention

The worker accepts only the three controlled Java/XML files. It does not accept Gradle scripts, arbitrary dependencies, native code, or build hooks. APK downloads are student-bound and expire after six hours by default.
