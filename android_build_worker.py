"""Minimal, isolated Java Android APK builder used by the queue worker."""
import base64, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

PACKAGE='com.learnwithhemant.studentapp'

def _tool(name):
    sdk=Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or '')
    if not sdk.is_dir():raise RuntimeError('Android SDK is not configured. Run INSTALL_CODE_RUNNER.bat again.')
    suffix='.bat' if os.name=='nt' and name in {'d8','apksigner'} else ('.exe' if os.name=='nt' else '')
    candidates=list((sdk/'build-tools').glob(f'*/{name}{suffix}'))
    if not candidates:raise RuntimeError(f'Android build tool is missing: {name}. Run INSTALL_CODE_RUNNER.bat again.')
    return str(sorted(candidates,key=lambda p:tuple(int(x) if x.isdigit() else 0 for x in re.split(r'[.-]',p.parent.name)))[-1])

def _run(args,cwd,timeout=90):
    done=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=timeout,creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
    log=(done.stdout or '')+(done.stderr or '')
    if done.returncode:raise RuntimeError(log.strip() or f'Build command failed ({done.returncode}).')
    return log

def build_android_apk(source):
    try:project=json.loads(source)
    except Exception as exc:raise RuntimeError('The Android project data is invalid.') from exc
    activity=str(project.get('activity') or '');layout=str(project.get('layout') or '');manifest=str(project.get('manifest') or '')
    if len(activity)>80000 or len(layout)>40000 or len(manifest)>20000:raise RuntimeError('Android project exceeds the safe build limit.')
    # Keep the first release deterministic and safe: Java/XML only, no arbitrary
    # Gradle scripts, shell hooks, native libraries or downloaded dependencies.
    if not all(x.strip() for x in (activity,layout,manifest)):raise RuntimeError('Activity, layout and manifest are required.')
    sdk=Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or '')
    platforms=sorted((sdk/'platforms').glob('android-*')) if sdk.is_dir() else []
    if not platforms:raise RuntimeError('Android platform is missing. Run INSTALL_CODE_RUNNER.bat again.')
    android_jar=platforms[-1]/'android.jar';logs=[]
    with tempfile.TemporaryDirectory(prefix='lwh-android-') as td:
        root=Path(td);src=root/'src/com/learnwithhemant/studentapp';res=root/'res/layout';gen=root/'gen';classes=root/'classes';dex=root/'dex';compiled=root/'compiled'
        for folder in (src,res,gen,classes,dex,compiled):folder.mkdir(parents=True,exist_ok=True)
        (src/'MainActivity.java').write_text(activity,encoding='utf-8')
        (res/'activity_main.xml').write_text(layout,encoding='utf-8')
        (root/'AndroidManifest.xml').write_text(manifest,encoding='utf-8')
        aapt2=_tool('aapt2');d8=_tool('d8');zipalign=_tool('zipalign');apksigner=_tool('apksigner')
        logs.append(_run([aapt2,'compile','--dir',str(root/'res'),'-o',str(compiled)],root))
        flats=[str(p) for p in compiled.glob('*.flat')]
        unsigned=root/'unsigned.apk'
        logs.append(_run([aapt2,'link','-o',str(unsigned),'-I',str(android_jar),'--manifest',str(root/'AndroidManifest.xml'),'--rename-manifest-package',PACKAGE,'--java',str(gen)]+flats,root))
        java_files=[str(p) for p in (root/'src').rglob('*.java')]+[str(p) for p in gen.rglob('*.java')]
        logs.append(_run(['javac','-encoding','UTF-8','-source','8','-target','8','-classpath',str(android_jar),'-d',str(classes)]+java_files,root))
        class_files=[str(p) for p in classes.rglob('*.class')]
        logs.append(_run([d8,'--lib',str(android_jar),'--output',str(dex)]+class_files,root))
        logs.append(_run(['jar','uf',str(unsigned),'-C',str(dex),'classes.dex'],root))
        aligned=root/'aligned.apk';signed=root/'StudentApp-debug.apk'
        logs.append(_run([zipalign,'-f','4',str(unsigned),str(aligned)],root))
        keystore=Path(os.environ.get('ANDROID_DEBUG_KEYSTORE') or (Path.home()/'.android/debug.keystore'))
        if not keystore.is_file():raise RuntimeError('Android debug signing key is missing. Run INSTALL_CODE_RUNNER.bat again.')
        logs.append(_run([apksigner,'sign','--ks',str(keystore),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(signed),str(aligned)],root))
        logs.append(_run([apksigner,'verify','--verbose',str(signed)],root))
        apk=signed.read_bytes()
        if len(apk)>7*1024*1024:raise RuntimeError('Generated APK is larger than 7 MB.')
        return {'output':'Android APK built and signed successfully.\n'+''.join(logs)[-12000:], 'exit_code':0,'success':True,'apk_base64':base64.b64encode(apk).decode('ascii')}
