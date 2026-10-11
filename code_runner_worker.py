"""Token-authenticated remote compiler worker; never connects to the database."""
import json, os, platform, signal, subprocess, tempfile, threading, time, traceback
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from android_build_worker import build_android_apk

SERVER_URL=os.getenv('CODE_RUNNER_SERVER_URL','').strip().rstrip('/')
RUNNER_TOKEN=os.getenv('CODE_RUNNER_TOKEN','').strip()
PISTON_URL=os.getenv('CODE_RUNNER_API_URL','http://127.0.0.1:2000/api/v2/execute').strip()
BACKEND=os.getenv('CODE_RUNNER_BACKEND','piston').strip().lower()
WORK_ROOT=os.getenv('CODE_RUNNER_WORK_ROOT','').strip()
WORKERS=max(1,min(4,int(os.getenv('CODE_RUNNER_WORKERS','1'))))
POLL_SECONDS=max(.3,min(5,float(os.getenv('CODE_RUNNER_QUEUE_POLL_SECONDS','.7'))))
RUNNER_NAME=os.getenv('CODE_RUNNER_NAME',platform.node() or 'windows-runner')[:80]
ALL_CAPABILITIES=('c','c++','java','python','php','android')
CAPABILITIES=tuple(dict.fromkeys(
    item.strip().lower() for item in os.getenv('CODE_RUNNER_CAPABILITIES',','.join(ALL_CAPABILITIES)).split(',')
    if item.strip().lower() in ALL_CAPABILITIES
))
stop_event=threading.Event()
# Android project resources are base64 encoded in the claim JSON.
# Reading only 250 KB truncates that JSON and raises JSONDecodeError.
MAX_API_RESPONSE_BYTES=16*1024*1024


def api(path,payload=None,allow_empty=False):
    data=None if payload is None else json.dumps(payload).encode()
    req=Request(SERVER_URL+path,data=data,headers={
        'Authorization':'Bearer '+RUNNER_TOKEN,'Content-Type':'application/json',
        'Accept':'application/json','X-Runner-Name':RUNNER_NAME,
        'X-Runner-Capabilities':','.join(CAPABILITIES),
    },method='GET' if payload is None else 'POST')
    try:
        with urlopen(req,timeout=25) as response:
            # Read the complete response (up to a safe limit), not just 250 KB.
            # A large image or audio resource can make the JSON claim much larger.
            raw=response.read(MAX_API_RESPONSE_BYTES + 1)
            if len(raw)>MAX_API_RESPONSE_BYTES:
                raise RuntimeError('Worker API response exceeds 16 MiB; check project limits.')
            if allow_empty and not raw:return None
            if not raw:raise RuntimeError('Worker API returned an empty JSON response.')
            try:
                return json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeError) as exc:
                raise RuntimeError(
                    f'Invalid JSON response from {path}: {len(raw)} bytes, '
                    f'HTTP {response.status}; {exc}'
                ) from exc
    except HTTPError as exc:
        if allow_empty and exc.code==204:return None
        detail=exc.read(500).decode('utf-8','replace')
        raise RuntimeError(f'Server API {exc.code}: {detail}') from exc
    except (URLError,TimeoutError) as exc:raise RuntimeError(f'Server connection failed: {exc}') from exc

def execute_with_docker(language,source,stdin_text):
    """Execute generic code in a short-lived, networkless multi-architecture container."""
    specs={
        'c':('gcc:14','main.c','gcc /workspace/main.c -O0 -o /tmp/program && /tmp/program'),
        'c++':('gcc:14','main.cpp','g++ /workspace/main.cpp -O0 -o /tmp/program && /tmp/program'),
        'java':('eclipse-temurin:17-jdk','Main.java','javac -d /tmp /workspace/Main.java && java -cp /tmp Main'),
        'python':('python:3.13-slim','main.py','python /workspace/main.py'),
        'php':('php:8.4-cli','main.php','php /workspace/main.php'),
    }
    if language not in specs:raise RuntimeError(f'{language} is not supported by this cloud worker.')
    image,filename,command=specs[language]
    with tempfile.TemporaryDirectory(prefix='lwh-code-',dir=WORK_ROOT or None) as folder:
        Path(folder,filename).write_text(source,encoding='utf-8')
        args=['docker','run','--rm','--network','none','--memory','256m','--cpus','1',
              '--pids-limit','64','--read-only','--tmpfs','/tmp:rw,exec,nosuid,size=128m',
              '--security-opt','no-new-privileges','--cap-drop','ALL','-i',
              '-v',f'{folder}:/workspace:ro',image,'sh','-lc',command]
        try:
            result=subprocess.run(args,input=stdin_text,text=True,capture_output=True,timeout=15,check=False)
        except subprocess.TimeoutExpired as exc:
            partial=''.join(str(value or '') for value in (exc.stdout,exc.stderr))[:50000]
            return {'output':partial+'\nExecution timed out.','exit_code':124,'success':False}
        output=(result.stdout+result.stderr)[:50000]
        return {'output':output or '(Program finished with no output.)','exit_code':result.returncode,'success':result.returncode==0}

def execute(language,source,stdin_text):
    if language not in CAPABILITIES:raise RuntimeError(f'{language} is not enabled on this worker.')
    if language=='android':return build_android_apk(source)
    if BACKEND=='docker':return execute_with_docker(language,source,stdin_text)
    if BACKEND!='piston':raise RuntimeError('CODE_RUNNER_BACKEND must be piston or docker.')
    filenames={'c':'main.c','c++':'main.cpp','java':'Main.java','python':'main.py','php':'main.php'}
    payload={'language':language,'version':'*','files':[{'name':filenames.get(language,'main.txt'),'content':source}],
             'stdin':stdin_text,'compile_timeout':8000,'run_timeout':3000,'compile_cpu_time':8000,
             'run_cpu_time':3000,'compile_memory_limit':268435456,'run_memory_limit':134217728}
    req=Request(PISTON_URL,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=20) as response:data=json.loads(response.read(250000).decode())
    compile_step=data.get('compile') or {};run_step=data.get('run') or {}
    output=''.join(str(x or '') for x in (compile_step.get('stdout'),compile_step.get('stderr'),run_step.get('stdout'),run_step.get('stderr')))[:50000]
    code=run_step.get('code') if run_step else compile_step.get('code')
    success=compile_step.get('code') in (0,None) and run_step.get('code') in (0,None)
    return {'output':output or '(Program finished with no output.)','exit_code':code,'success':success}

def run_worker(number):
    failures=0
    while not stop_event.is_set():
        try:
            result=api('/api/code-runner/claim',{},allow_empty=True)
            failures=0
            if not result:stop_event.wait(POLL_SECONDS);continue
            job=result['job'];completion={'claim_token':job['claim_token']}
            try:completion.update(execute(job['language'],job['source'],job.get('stdin') or ''))
            except Exception as exc:completion['error']=(str(exc) or 'Compilation failed safely.')[:2000]
            api(f"/api/code-runner/jobs/{int(job['id'])}/complete",completion)
        except Exception as exc:
            failures=min(failures+1,6)
            print(f'[worker {number}] {exc}',flush=True)
            traceback.print_exc()
            stop_event.wait(min(30,2**failures))

def stop_worker(*_):stop_event.set()

if __name__=='__main__':
    if not SERVER_URL.startswith('https://'):raise SystemExit('CODE_RUNNER_SERVER_URL must use HTTPS.')
    if len(RUNNER_TOKEN)<32:raise SystemExit('CODE_RUNNER_TOKEN must contain at least 32 characters.')
    signal.signal(signal.SIGTERM,stop_worker);signal.signal(signal.SIGINT,stop_worker)
    if not CAPABILITIES:raise SystemExit('CODE_RUNNER_CAPABILITIES must enable at least one supported language.')
    if BACKEND=='docker' and 'android' in CAPABILITIES and not os.getenv('ANDROID_DOCKER_IMAGE','').strip():raise SystemExit('ANDROID_DOCKER_IMAGE is required when the Docker fallback claims Android jobs.')
    health=api('/api/code-runner/health')
    print(f"Connected securely to {SERVER_URL} (server {health.get('version')}) as {RUNNER_NAME}; backend={BACKEND}; capabilities={','.join(CAPABILITIES)}.",flush=True)
    threads=[threading.Thread(target=run_worker,args=(i+1,),daemon=True) for i in range(WORKERS)]
    for thread in threads:thread.start()
    while not stop_event.is_set():time.sleep(.5)
    for thread in threads:thread.join(timeout=5)
