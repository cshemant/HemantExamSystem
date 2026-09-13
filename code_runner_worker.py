"""Token-authenticated remote compiler worker; never connects to the database."""
import json, os, platform, signal, threading, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from android_build_worker import build_android_apk

SERVER_URL=os.getenv('CODE_RUNNER_SERVER_URL','').strip().rstrip('/')
RUNNER_TOKEN=os.getenv('CODE_RUNNER_TOKEN','').strip()
PISTON_URL=os.getenv('CODE_RUNNER_API_URL','http://127.0.0.1:2000/api/v2/execute').strip()
WORKERS=max(1,min(4,int(os.getenv('CODE_RUNNER_WORKERS','1'))))
POLL_SECONDS=max(.3,min(5,float(os.getenv('CODE_RUNNER_QUEUE_POLL_SECONDS','.7'))))
RUNNER_NAME=os.getenv('CODE_RUNNER_NAME',platform.node() or 'windows-runner')[:80]
stop_event=threading.Event()

def api(path,payload=None,allow_empty=False):
    data=None if payload is None else json.dumps(payload).encode()
    req=Request(SERVER_URL+path,data=data,headers={
        'Authorization':'Bearer '+RUNNER_TOKEN,'Content-Type':'application/json',
        'Accept':'application/json','X-Runner-Name':RUNNER_NAME,
    },method='GET' if payload is None else 'POST')
    try:
        with urlopen(req,timeout=25) as response:
            raw=response.read(250000)
            if allow_empty and not raw:return None
            return json.loads(raw.decode())
    except HTTPError as exc:
        if allow_empty and exc.code==204:return None
        detail=exc.read(500).decode('utf-8','replace')
        raise RuntimeError(f'Server API {exc.code}: {detail}') from exc
    except (URLError,TimeoutError) as exc:raise RuntimeError(f'Server connection failed: {exc}') from exc

def execute(language,source,stdin_text):
    if language=='android':return build_android_apk(source)
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
            stop_event.wait(min(30,2**failures))

def stop_worker(*_):stop_event.set()

if __name__=='__main__':
    if not SERVER_URL.startswith('https://'):raise SystemExit('CODE_RUNNER_SERVER_URL must use HTTPS.')
    if len(RUNNER_TOKEN)<32:raise SystemExit('CODE_RUNNER_TOKEN must contain at least 32 characters.')
    signal.signal(signal.SIGTERM,stop_worker);signal.signal(signal.SIGINT,stop_worker)
    health=api('/api/code-runner/health')
    print(f"Connected securely to {SERVER_URL} (server {health.get('version')}) as {RUNNER_NAME}.",flush=True)
    threads=[threading.Thread(target=run_worker,args=(i+1,),daemon=True) for i in range(WORKERS)]
    for thread in threads:thread.start()
    while not stop_event.is_set():time.sleep(.5)
    for thread in threads:thread.join(timeout=5)
