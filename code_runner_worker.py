"""Bounded background worker for queued student code execution jobs."""
import os
import signal
import threading
import time
from datetime import timedelta

from sqlalchemy import delete, update

from app import DB, CodeRunJob, execute_student_code, now_dt, now_iso

def configured_worker_count():
    """Read concurrency from settings while retaining a safe upper bound."""
    try:
        requested=int(os.getenv('CODE_RUNNER_WORKERS','2'))
    except (TypeError,ValueError):
        requested=2
    return max(1,min(10,requested))

WORKERS=configured_worker_count()
POLL_SECONDS=max(0.2,min(5.0,float(os.getenv('CODE_RUNNER_QUEUE_POLL_SECONDS','0.5'))))
stop_event=threading.Event()

def cleanup_old_jobs():
    cutoff=(now_dt()-timedelta(days=7)).isoformat(timespec='seconds')
    s=DB()
    try:
        s.execute(delete(CodeRunJob).where(CodeRunJob.status.in_(['completed','failed']),CodeRunJob.completed_at!='',CodeRunJob.completed_at<cutoff));s.commit()
    except Exception:s.rollback()
    finally:DB.remove()

def claim_job():
    s=DB()
    try:
        row=s.query(CodeRunJob.id).filter(CodeRunJob.status=='queued').order_by(CodeRunJob.id.asc()).first()
        if not row:return None
        claimed=s.execute(update(CodeRunJob).where(CodeRunJob.id==row.id,CodeRunJob.status=='queued').values(status='running',started_at=now_iso()))
        s.commit()
        if claimed.rowcount!=1:return None
        return row.id
    except Exception:
        s.rollback();return None
    finally:DB.remove()

def finish_job(job_id,result=None,error=''):
    s=DB()
    try:
        job=s.get(CodeRunJob,job_id)
        if not job:return
        if error:
            job.status='failed';job.error=error[:2000];job.success=False
        else:
            job.status='completed';job.output=(result.get('output') or '')[:50000];job.exit_code=result.get('exit_code');job.success=bool(result.get('success'))
        # Source/input are only needed while queued; erase them after execution
        # so the database does not grow with student programs.
        job.source_code='';job.stdin_text='';job.completed_at=now_iso();s.commit()
    except Exception:s.rollback()
    finally:DB.remove()

def run_worker():
    idle_cycles=0
    while not stop_event.is_set():
        job_id=claim_job()
        if not job_id:
            idle_cycles+=1
            if idle_cycles>=120:cleanup_old_jobs();idle_cycles=0
            stop_event.wait(POLL_SECONDS);continue
        idle_cycles=0
        s=DB()
        try:
            job=s.get(CodeRunJob,job_id)
            language,source,stdin_text=job.language,job.source_code,job.stdin_text
        finally:DB.remove()
        try:finish_job(job_id,result=execute_student_code(language,source,stdin_text))
        except Exception as exc:finish_job(job_id,error=str(exc) or 'Code execution failed safely.')

def stop_worker(_signum=None,_frame=None):stop_event.set()

if __name__=='__main__':
    signal.signal(signal.SIGTERM,stop_worker);signal.signal(signal.SIGINT,stop_worker)
    threads=[threading.Thread(target=run_worker,name=f'code-runner-{index+1}',daemon=True) for index in range(WORKERS)]
    for thread in threads:thread.start()
    while not stop_event.is_set():time.sleep(0.5)
    for thread in threads:thread.join(timeout=5)
