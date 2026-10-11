import base64, json
from pathlib import Path
import pytest
import android_build_worker as worker

PNG=(b'\x89PNG\r\n\x1a\n'+b'data')

def project():
    package='com.example.student'
    return {'activities':{'MainActivity.java':f'package {package}; public class MainActivity {{}}'},'receivers':{},'services':{},'java_classes':{},'layouts':{'activity_main.xml':'<LinearLayout />'},'values':{'strings.xml':'<resources><string name="app_name">App</string></resources>'},'manifest':f'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:icon="@mipmap/ic_launcher"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>'}

def test_resource_validation():
    p=project();p['resources']={'drawable':{'shape.xml':'<shape xmlns:android="http://schemas.android.com/apk/res/android"/>'},'mipmap':{'ic_launcher.png':base64.b64encode(PNG).decode()}}
    assert worker._project_resources(p)['mipmap']['ic_launcher.png']==PNG
    worker._project(json.dumps(p))

def test_reject_traversal_and_fake_images():
    p=project();p['resources']={'drawable':{'../evil.xml':'<shape/>'}}
    with pytest.raises(RuntimeError,match='Invalid resource file'):worker._project(json.dumps(p))
    p['resources']={'drawable':{'picture.png':base64.b64encode(b'not really image').decode()}}
    with pytest.raises(RuntimeError,match='not a valid image'):worker._project_resources(p)

def test_build_writes_xml_and_icon(monkeypatch,tmp_path):
    p=project();p['resources']={'drawable':{'custom_toast.xml':'<shape/>'},'mipmap':{'ic_launcher.png':base64.b64encode(PNG).decode()}}
    sdk=tmp_path/'sdk';sdk.mkdir();key=tmp_path/'debug.keystore';key.write_bytes(b'dummy')
    monkeypatch.setenv('ANDROID_SDK_ROOT',str(sdk));monkeypatch.setenv('ANDROID_DEBUG_KEYSTORE',str(key))
    monkeypatch.setattr(worker,'_gradle_executable',lambda:'gradle')
    def pretend(args,cwd,timeout=240,env=None):
        base=Path(cwd)/'app/src/main/res'
        assert (base/'drawable/custom_toast.xml').read_text()=='<shape/>'
        assert (base/'mipmap/ic_launcher.png').read_bytes()==PNG
        gradle=(Path(cwd)/'app/build.gradle').read_text()
        assert 'play-services-maps' in gradle
        apk=Path(cwd)/'app/build/outputs/apk/debug/app-debug.apk';apk.parent.mkdir(parents=True);apk.write_bytes(b'apk')
        return 'ok'
    monkeypatch.setattr(worker,'_run',pretend)
    assert worker.build_android_apk(json.dumps(p))['success']
