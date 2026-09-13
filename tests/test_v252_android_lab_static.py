from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_android_lab_routes_and_private_download_exist():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    assert "@app.route('/student/android-lab')" in app
    assert "@app.post('/student/android-lab/build')" in app
    assert "@app.get('/student/android-lab/apk/<job_token>')" in app
    assert "CodeRunJob.student_id==student_id" in app
    assert "base64.b64decode(encoded,validate=True)" in app
    assert "apk_bytes[:2]!=b'PK'" in app

def test_android_worker_is_template_limited_and_signed():
    worker=(ROOT/'android_build_worker.py').read_text(encoding='utf-8')
    queue=(ROOT/'code_runner_worker.py').read_text(encoding='utf-8')
    assert "if language=='android':return build_android_apk(source)" in queue
    for tool in ('aapt2','d8','zipalign','apksigner'):
        assert tool in worker
    assert '--rename-manifest-package' in worker
    assert 'ANDROID_DEBUG_KEYSTORE' in worker
    assert 'apksigner' in worker and 'verify' in worker

def test_android_installer_and_ui_are_one_click():
    setup=(ROOT/'setup_code_runner_windows.ps1').read_text(encoding='utf-8')
    start=(ROOT/'start_code_runner_windows.ps1').read_text(encoding='utf-8')
    template=(ROOT/'templates/android_lab.html').read_text(encoding='utf-8')
    script=(ROOT/'static/android_lab.js').read_text(encoding='utf-8')
    assert 'Install-AndroidBuildTools' in setup
    assert 'Existing Android command-line SDK detected; keeping it.' in setup
    assert 'Existing Android debug signing key detected; keeping it.' in setup
    assert 'Installing it automatically' in start
    assert 'MainActivity.java' in template and 'AndroidManifest.xml' in template
    assert 'download_url' in script and 'Build APK' in template
