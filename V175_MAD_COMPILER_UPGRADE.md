# V175 — MAD Lab compiler resource upgrade

## Scope
This update builds on V174 (bulk experiment save) and V173 (scoring). It does not change exam grading routes, reference comparisons, QR jobs, or the practical register schema.

## Changed files to deploy
- `app.py` — passes Android `resources` from student projects and raises Android project payload limit to 1.6 MB (configurable).
- `static/android_lab.js` — creates drawable/mipmap/raw/xml/anim/animator/menu/font XML files and uploads PNG/JPEG/WebP images; preserves existing Java, layout and Manifest editor.
- `templates/android_lab.html` — resource actions and launcher icon instructions.
- `android_build_worker.py` — validates/writes resource XML and images into `app/src/main/res/*`; bundles extra predetermined AndroidX and Google Play Services Maps/Location dependencies.
- `oracle_android_builder/warmup/app/build.gradle` — warms new dependencies inside the controlled compiler image for offline `gradle --offline` builds.

## Deployment order
1. Back up your staging app, database, worker, and Docker image/tag. **Do not push to `main` for this test.**
2. Push `app.py`, `templates/android_lab.html`, `static/android_lab.js` to staging and manually deploy Render.
3. Deploy `android_build_worker.py` to the actual **Android compiler worker host** (not only Render's web app). Update `android_build_worker.py` alongside its runner if copied by `install_oracle_fallback_compiler.sh`.
4. Rebuild the Android compiler Docker image from `oracle_android_builder/Dockerfile`, including the modified `oracle_android_builder/warmup/app/build.gradle`; point `ANDROID_DOCKER_IMAGE` at the rebuilt image. Verify warmup resolves AndroidX, Maps and Location. Restart worker service.
5. Test a custom drawable XML, an uploaded icon (under `res/mipmap/ic_launcher.png` with `android:icon="@mipmap/ic_launcher"`), and one original experiment. Check logs and QR/marks afterwards.
6. For a local non-Docker builder, install/cache the new Gradle dependencies while online, then test `gradle --offline`.

## Syllabus audit (MAD-Lab PDF, 2 pages)
| Experiments | Builder dependencies | On-device/external requirements |
| --- | --- | --- |
| 1 installation | Web editor replaces some IDE tasks, not full Android Studio | Native IDE installation not possible from webpage |
| 2A–2C layouts, 3A–3B views | Android SDK, AndroidX + XML layouts | APK installation |
| 4A–4E buttons/controls, 5 list/grid/image/scroll | Android SDK + image resources | APK installation |
| 6A custom toast, 6B date/time pickers | drawable XML + Android SDK | APK installation |
| 7A–7B activities/intents | Java activities + Manifest | External intent handler for some actions |
| 8A–8D content provider, service, receiver, sensors | Android SDK and custom Java components; Manifest editable | Actual sensors, components and runtime permissions; receiver behavior varies by OS version |
| 9A camera | Android SDK and resources | Camera hardware, runtime permissions; camera handling per Android version |
| 9B Bluetooth | Android SDK and resources | Bluetooth hardware; Android 12+ permissions, user confirmation |
| 10 animation | res/anim XML + Android SDK | Device/emulator rendering |
| 11A Async/SQLite, 11B–11C login | Built-in Android SQLite and Java threading/UI | Device testing; AsyncTask itself is deprecated |
| 12A SMS | Android SDK | SMS hardware/service and runtime/default-app restrictions; not guaranteed by arbitrary third-party APK |
| 12B email | Android Intent APIs | External installed mail app or configured email provider |
| 12C Maps | Google Play Services Maps + Location dependencies | Real API key, enabled Maps SDK, Google Play services, internet, possible billing; not supplied by this update |

## Limits and safeguards
- Compiler continues to use **fixed** managed Gradle dependencies: students cannot install arbitrary libraries from a web editor. This prevents remote dependency injection into a shared build worker.
- Added up to 30 files per resource folder, 350 KB per resource file, 1.2 MB decoded resources overall, 1.6 MB project JSON by default. Large photos need compression and might require further limits/config changes.
- Uploaded files are restricted to known resource folders and image signatures. Do not upload credentials or personal files.
- APK generation validates build success, **not runtime behavior**; students need physical devices/emulators to test cameras, Bluetooth, SMS, sensors and maps.
- This environment ran automated code/simulated builds; a real Android SDK and Docker rebuild is still required to verify full APK builds end-to-end.
