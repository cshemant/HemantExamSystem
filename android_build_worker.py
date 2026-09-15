"""Controlled Java/XML AndroidX APK builder executed by the local worker."""
import base64,json,os,re,subprocess,tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE='com.learnwithhemant.studentapp'  # Default for newly created projects only.
ANDROID_NAME='{http://schemas.android.com/apk/res/android}name'
JAVA_RE=re.compile(r'^[A-Z][A-Za-z0-9_]{0,49}\.java$');XML_RE=re.compile(r'^[a-z][a-z0-9_]{0,49}\.xml$')
GROUP_LIMITS={'activities':10,'receivers':10,'services':10,'java_classes':20}
ANDROIDX_DEPENDENCIES=('androidx.appcompat:appcompat:1.7.0','androidx.activity:activity:1.9.3','androidx.constraintlayout:constraintlayout:2.2.0','com.google.android.material:material:1.12.0')

def _run(args,cwd,timeout=240,env=None):
    done=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=timeout,env=env,creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
    log=(done.stdout or '')+(done.stderr or '')
    if done.returncode:raise RuntimeError(log.strip()[-12000:] or f'Build command failed ({done.returncode}).')
    return log

def _xml(name,body):
    try:return ET.fromstring(body)
    except ET.ParseError as exc:raise RuntimeError(f'{name} contains invalid XML: {exc}.') from exc

def _java_group(project,key):
    value=project.get(key,{})
    if not isinstance(value,dict):raise RuntimeError(f'Invalid {key.replace("_"," ")} collection.')
    minimum=1 if key=='activities' else 0;limit=GROUP_LIMITS[key]
    if not minimum<=len(value)<=limit:raise RuntimeError(f'Use {minimum} to {limit} {key.replace("_"," ")} files.')
    clean={}
    for raw,body in value.items():
        name=str(raw);body=str(body or '');class_name=name[:-5]
        if not JAVA_RE.fullmatch(name):raise RuntimeError(f'Invalid Java filename: {name}.')
        found=re.search(r'\bpublic\s+(?:final\s+|abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b',body)
        if not found or found.group(1)!=class_name:raise RuntimeError(f'{name} must declare public class {class_name}.')
        package=re.search(r'^\s*package\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*;',body,re.MULTILINE)
        if not package:raise RuntimeError(f'{name} must declare a valid Java package.')
        clean[name]=body
    return clean

def _package_of(body):
    return re.search(r'^\s*package\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*;',body,re.MULTILINE).group(1)

def _declared(app,tag,namespace):
    found=set()
    for node in app.findall(tag):
        raw=(node.get(ANDROID_NAME) or '').strip();resolved=namespace+raw if raw.startswith('.') else (namespace+'.'+raw if '.' not in raw else raw)
        if resolved:found.add(resolved)
    return found

def _project(source):
    try:p=json.loads(source)
    except Exception as exc:raise RuntimeError('Invalid Android project data.') from exc
    if not isinstance(p,dict):raise RuntimeError('Invalid Android project data.')
    if 'activities' not in p:p['activities']={'MainActivity.java':str(p.get('activity') or '')}
    groups={key:_java_group(p,key) for key in GROUP_LIMITS}
    names=[name for files in groups.values() for name in files]
    duplicate=next((name for name in names if names.count(name)>1),None)
    if duplicate:raise RuntimeError(f'{duplicate} exists in more than one Java category.')
    main_body=groups['activities'].get('MainActivity.java') or next(iter(groups['activities'].values()))
    namespace=_package_of(main_body)
    layouts=p.get('layouts',{})
    if not isinstance(layouts,dict) or not 1<=len(layouts)<=15:raise RuntimeError('Use 1 to 15 layout files.')
    clean_layouts={}
    for raw,body in layouts.items():
        name=str(raw);body=str(body or '')
        if not XML_RE.fullmatch(name):raise RuntimeError(f'Invalid layout filename: {name}.')
        _xml(name,body);clean_layouts[name]=body
    values=p.get('values',{})
    if not isinstance(values,dict) or not 1<=len(values)<=10:raise RuntimeError('Use 1 to 10 values XML files.')
    clean_values={}
    for raw,body in values.items():
        name=str(raw);body=str(body or '')
        if not XML_RE.fullmatch(name):raise RuntimeError(f'Invalid values filename: {name}.')
        if _xml(name,body).tag!='resources':raise RuntimeError(f'{name} must have a <resources> root.')
        clean_values[name]=body
    manifest=str(p.get('manifest') or '');opening=re.search(r'<manifest\b[^>]*>',manifest,re.I)
    if not opening:raise RuntimeError('Manifest requires a <manifest> root.')
    # AGP 8 uses the generated Gradle namespace. Remove a legacy manifest
    # package attribute instead of forcing a portal-specific package.
    fixed=re.sub(r'\s+package\s*=\s*(["\']).*?\1','',opening.group(),count=1,flags=re.I)
    manifest=manifest[:opening.start()]+fixed+manifest[opening.end():];root=_xml('AndroidManifest.xml',manifest);app=root.find('application')
    if app is None:raise RuntimeError('Manifest requires one <application>.')
    for key,tag in {'activities':'activity','receivers':'receiver','services':'service'}.items():
        expected={_package_of(body)+'.'+name[:-5] for name,body in groups[key].items()}
        missing=sorted(expected-_declared(app,tag,namespace))
        if missing:raise RuntimeError(f'Manifest missing {tag} declaration(s): '+', '.join(missing)+'.')
    launcher=False
    for node in app.findall('activity'):
        for intent in node.findall('intent-filter'):
            actions={x.get(ANDROID_NAME) for x in intent.findall('action')};categories={x.get(ANDROID_NAME) for x in intent.findall('category')}
            launcher=launcher or ('android.intent.action.MAIN' in actions and 'android.intent.category.LAUNCHER' in categories)
    if not launcher:raise RuntimeError('Manifest requires one MAIN/LAUNCHER activity.')
    total=sum(len(body) for files in groups.values() for body in files.values())+sum(map(len,clean_layouts.values()))+sum(map(len,clean_values.values()))+len(manifest)
    if total>260000:raise RuntimeError('Android project exceeds the 260 KB source limit.')
    return groups,clean_layouts,clean_values,manifest,namespace

def _gradle_executable():
    configured=os.environ.get('LWH_ANDROID_GRADLE','').strip();candidates=[configured]
    if os.name=='nt':candidates += [str(p) for p in Path(__file__).resolve().parent.glob('.gradle-dist/gradle-*/bin/gradle.bat')]
    else:candidates+=['gradle']
    for value in candidates:
        if value and (value=='gradle' or Path(value).is_file()):return value
    raise RuntimeError('Controlled Android Gradle builder is missing. Run INSTALL_CODE_RUNNER.bat once.')

def _build_gradle(namespace):
    deps='\n'.join(f"    implementation '{item}'" for item in ANDROIDX_DEPENDENCIES)
    return f"""plugins {{ id 'com.android.application' version '8.7.3' }}
android {{
    namespace '{namespace}'
    compileSdk 35
    defaultConfig {{ applicationId '{namespace}'; minSdk 23; targetSdk 35; versionCode 1; versionName '1.0' }}
    signingConfigs {{ debug {{ storeFile file(System.getenv('ANDROID_DEBUG_KEYSTORE')); storePassword 'android'; keyAlias 'androiddebugkey'; keyPassword 'android' }} }}
    buildTypes {{ debug {{ signingConfig signingConfigs.debug }} }}
}}
dependencies {{
{deps}
}}
"""

def build_android_apk(source):
    groups,layouts,values,manifest,namespace=_project(source);sdk=os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME');key=os.environ.get('ANDROID_DEBUG_KEYSTORE')
    if not sdk or not Path(sdk).is_dir():raise RuntimeError('Android SDK is missing. Run INSTALL_CODE_RUNNER.bat once.')
    if not key or not Path(key).is_file():raise RuntimeError('Android debug signing key is missing.')
    with tempfile.TemporaryDirectory(prefix='lwh-androidx-') as td:
        root=Path(td);app=root/'app';java_root=app/'src/main/java';layout=app/'src/main/res/layout';value_dir=app/'src/main/res/values'
        for folder in (java_root,layout,value_dir):folder.mkdir(parents=True,exist_ok=True)
        for files in groups.values():
            for name,body in files.items():
                java=java_root/Path(_package_of(body).replace('.','/'));java.mkdir(parents=True,exist_ok=True);(java/name).write_text(body,encoding='utf-8')
        for name,body in layouts.items():(layout/name).write_text(body,encoding='utf-8')
        for name,body in values.items():(value_dir/name).write_text(body,encoding='utf-8')
        (app/'src/main/AndroidManifest.xml').write_text(manifest,encoding='utf-8')
        (root/'settings.gradle').write_text("pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\ndependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\nrootProject.name='StudentApp'\ninclude ':app'\n",encoding='utf-8')
        (root/'build.gradle').write_text('// System managed. Students cannot modify this file.\n',encoding='utf-8')
        (app/'build.gradle').write_text(_build_gradle(namespace),encoding='utf-8')
        (root/'gradle.properties').write_text('org.gradle.daemon=false\norg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\n',encoding='utf-8')
        env=os.environ.copy();env.update({'ANDROID_HOME':sdk,'ANDROID_SDK_ROOT':sdk,'ANDROID_DEBUG_KEYSTORE':key})
        log=_run([_gradle_executable(),'--offline','--no-daemon','--console=plain',':app:assembleDebug'],root,300,env)
        apk=app/'build/outputs/apk/debug/app-debug.apk'
        if not apk.is_file():raise RuntimeError('Gradle completed without producing the debug APK.')
        data=apk.read_bytes()
        if len(data)>12*1024*1024:raise RuntimeError('Generated APK is larger than 12 MB.')
        components=sum(len(groups[k]) for k in ('activities','receivers','services'))
        return {'output':f'AndroidX APK built successfully with {components} components, {len(groups["java_classes"])} helper classes and {len(layouts)} layouts.\n'+log[-10000:],'exit_code':0,'success':True,'apk_base64':base64.b64encode(data).decode('ascii')}
