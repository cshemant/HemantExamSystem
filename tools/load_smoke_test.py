"""Small readiness/load smoke test. It does NOT certify a concurrency limit.

Usage: python tools/load_smoke_test.py http://127.0.0.1:8080 --requests 500 --concurrency 50
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen
import argparse, statistics, time

parser=argparse.ArgumentParser();parser.add_argument('base_url');parser.add_argument('--requests',type=int,default=200);parser.add_argument('--concurrency',type=int,default=25);args=parser.parse_args()
url=args.base_url.rstrip('/')+'/health'

def hit(_):
    start=time.perf_counter()
    try:
        with urlopen(url,timeout=5) as r:
            ok=(r.status==200);r.read()
    except Exception:
        ok=False
    return ok,(time.perf_counter()-start)*1000

with ThreadPoolExecutor(max_workers=max(1,args.concurrency)) as pool:
    results=[f.result() for f in as_completed([pool.submit(hit,i) for i in range(max(1,args.requests))])]
lat=[x[1] for x in results];ok=sum(1 for x in results if x[0])
print(f'Requests: {len(results)} | Success: {ok} | Failures: {len(results)-ok}')
print(f'Latency ms: avg={statistics.mean(lat):.1f} p95={sorted(lat)[max(0,int(len(lat)*.95)-1)]:.1f} max={max(lat):.1f}')
if ok!=len(results):raise SystemExit(1)
