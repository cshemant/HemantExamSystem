import os, csv, io, random, socket, secrets, sys, json, math, sqlite3, tempfile, shutil
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session as web_session, flash, jsonify, abort, send_file, after_this_request
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, UniqueConstraint, select, func, or_, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker
from sqlalchemy.exc import IntegrityError
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font

RESOURCE_DIR=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DATA_DIR=Path(os.getenv('EXAM_DATA_DIR', str(RESOURCE_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True,exist_ok=True)
load_dotenv(RESOURCE_DIR/'.env')

APP_VERSION='2.02'
OFFLINE_RELEASE_FILENAME='LearnWithHemant_Offline_Exam_V2.02_Windows.zip'
DEFAULT_OFFLINE_DOWNLOAD_URL=(
    'https://github.com/cshemant/HemantExamSystem/releases/download/v2.02/'
    + OFFLINE_RELEASE_FILENAME
)
OFFLINE_DOWNLOAD_URL=os.getenv('OFFLINE_DOWNLOAD_URL',DEFAULT_OFFLINE_DOWNLOAD_URL).strip() or DEFAULT_OFFLINE_DOWNLOAD_URL
OFFLINE_REQUIRE_SETUP=os.getenv('OFFLINE_REQUIRE_SETUP','0').strip().lower() in {'1','true','yes','on'}

APP_MODE=os.getenv('APP_MODE','offline').strip().lower()
if APP_MODE not in {'offline','online'}: raise RuntimeError('APP_MODE must be offline or online')

def normalize_database_url(raw):
    if not raw:
        return f"sqlite:///{(DATA_DIR/'exam.db').as_posix()}"
    raw=raw.strip()
    if raw.startswith('postgres://'):
        raw='postgresql+psycopg://'+raw[len('postgres://'):]
    elif raw.startswith('postgresql://'):
        raw='postgresql+psycopg://'+raw[len('postgresql://'):]
    return raw

DATABASE_URL=normalize_database_url(os.getenv('DATABASE_URL'))
if APP_MODE=='online' and not DATABASE_URL.startswith('postgresql'):
    raise RuntimeError('Online mode requires a PostgreSQL DATABASE_URL.')

secret=os.getenv('SECRET_KEY','').strip()
admin_password=os.getenv('ADMIN_PASSWORD','').strip()
admin_username=os.getenv('ADMIN_USERNAME','admin').strip() or 'admin'
if APP_MODE=='online':
    if len(secret)<24: raise RuntimeError('Online mode requires a strong SECRET_KEY (24+ characters).')
    if len(admin_password)<10: raise RuntimeError('Online mode requires ADMIN_PASSWORD with at least 10 characters.')
if not secret:
    secret='offline-development-secret-change-me'
if not admin_password and not OFFLINE_REQUIRE_SETUP:
    admin_password='Admin@123'

app=Flask(__name__,template_folder=str(RESOURCE_DIR/'templates'),static_folder=str(RESOURCE_DIR/'static'))
app.secret_key=secret
cookie_secure=os.getenv('COOKIE_SECURE','1' if APP_MODE=='online' else '0').strip().lower() in {'1','true','yes','on'}
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=cookie_secure,MAX_CONTENT_LENGTH=10*1024*1024)
if APP_MODE=='online': app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1,x_port=1)

engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
DB=scoped_session(sessionmaker(bind=engine,autoflush=False,expire_on_commit=False))

class Base(DeclarativeBase): pass

class Admin(Base):
    __tablename__='admins'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    username:Mapped[str]=mapped_column(String,unique=True,nullable=False)
    password_hash:Mapped[str]=mapped_column(String,nullable=False)

class Faculty(Base):
    __tablename__='faculty_users'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    username:Mapped[str]=mapped_column(String,unique=True,nullable=False)
    name:Mapped[str]=mapped_column(String,nullable=False)
    password_hash:Mapped[str]=mapped_column(String,nullable=False)
    is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class Student(Base):
    __tablename__='students'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    roll_no:Mapped[str]=mapped_column(String,unique=True,nullable=False)
    name:Mapped[str]=mapped_column(String,nullable=False)
    password_hash:Mapped[str]=mapped_column(String,nullable=False)
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class Exam(Base):
    __tablename__='exams'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    title:Mapped[str]=mapped_column(String,nullable=False)
    duration_minutes:Mapped[int]=mapped_column(Integer,nullable=False)
    is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class Question(Base):
    __tablename__='questions'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    question:Mapped[str]=mapped_column(String,nullable=False)
    option_a:Mapped[str]=mapped_column(String,nullable=False)
    option_b:Mapped[str]=mapped_column(String,nullable=False)
    option_c:Mapped[str]=mapped_column(String,nullable=False)
    option_d:Mapped[str]=mapped_column(String,nullable=False)
    correct_answer:Mapped[str]=mapped_column(String(1),nullable=False)
    marks:Mapped[int]=mapped_column(Integer,nullable=False,default=1)

class Attempt(Base):
    __tablename__='attempts'
    __table_args__=(UniqueConstraint('student_id','exam_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    student_id:Mapped[int]=mapped_column(ForeignKey('students.id'),nullable=False)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    started_at:Mapped[str]=mapped_column(String,nullable=False)
    end_at:Mapped[str]=mapped_column(String,nullable=False)
    submitted_at:Mapped[str|None]=mapped_column(String,nullable=True)
    status:Mapped[str]=mapped_column(String,nullable=False,default='in_progress')
    score:Mapped[int|None]=mapped_column(Integer,nullable=True)
    total_marks:Mapped[int|None]=mapped_column(Integer,nullable=True)
    question_order:Mapped[str]=mapped_column(String,nullable=False)

class Answer(Base):
    __tablename__='answers'
    __table_args__=(UniqueConstraint('attempt_id','question_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    attempt_id:Mapped[int]=mapped_column(ForeignKey('attempts.id'),nullable=False)
    question_id:Mapped[int]=mapped_column(ForeignKey('questions.id'),nullable=False)
    selected_answer:Mapped[str|None]=mapped_column(String(1),nullable=True)
    saved_at:Mapped[str]=mapped_column(String,nullable=False)

class BankQuestion(Base):
    __tablename__='bank_questions'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    subject:Mapped[str]=mapped_column(String,nullable=False,default='General')
    course_semester:Mapped[str]=mapped_column(String,nullable=False,default='')
    unit:Mapped[str]=mapped_column(String,nullable=False,default='')
    topic:Mapped[str]=mapped_column(String,nullable=False,default='')
    question_type:Mapped[str]=mapped_column(String,nullable=False,default='MCQ')
    question:Mapped[str]=mapped_column(String,nullable=False)
    option_a:Mapped[str]=mapped_column(String,nullable=False)
    option_b:Mapped[str]=mapped_column(String,nullable=False)
    option_c:Mapped[str]=mapped_column(String,nullable=False)
    option_d:Mapped[str]=mapped_column(String,nullable=False)
    correct_answer:Mapped[str]=mapped_column(String(1),nullable=False)
    marks:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    difficulty:Mapped[str]=mapped_column(String,nullable=False,default='Medium')
    bloom_level:Mapped[str]=mapped_column(String,nullable=False,default='Understand')
    co_mapping:Mapped[str]=mapped_column(String,nullable=False,default='')
    tags:Mapped[str]=mapped_column(String,nullable=False,default='')
    status:Mapped[str]=mapped_column(String,nullable=False,default='draft')
    version:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    created_by:Mapped[str]=mapped_column(String,nullable=False,default='admin')
    created_at:Mapped[str]=mapped_column(String,nullable=False)
    updated_at:Mapped[str]=mapped_column(String,nullable=False)

class QuestionRevision(Base):
    __tablename__='question_revisions'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    bank_question_id:Mapped[int]=mapped_column(ForeignKey('bank_questions.id'),nullable=False)
    version:Mapped[int]=mapped_column(Integer,nullable=False)
    snapshot_json:Mapped[str]=mapped_column(String,nullable=False)
    changed_by:Mapped[str]=mapped_column(String,nullable=False)
    changed_at:Mapped[str]=mapped_column(String,nullable=False)

class ExamBankMap(Base):
    __tablename__='exam_bank_map'
    __table_args__=(UniqueConstraint('exam_id','bank_question_id'),UniqueConstraint('exam_question_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    exam_question_id:Mapped[int]=mapped_column(ForeignKey('questions.id'),nullable=False)
    bank_question_id:Mapped[int]=mapped_column(ForeignKey('bank_questions.id'),nullable=False)

class ExamConfig(Base):
    __tablename__='exam_configs'
    __table_args__=(UniqueConstraint('exam_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    subject:Mapped[str]=mapped_column(String,nullable=False,default='')
    course_semester:Mapped[str]=mapped_column(String,nullable=False,default='')
    question_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    pool_size:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    easy_pct:Mapped[int]=mapped_column(Integer,nullable=False,default=30)
    medium_pct:Mapped[int]=mapped_column(Integer,nullable=False,default=50)
    hard_pct:Mapped[int]=mapped_column(Integer,nullable=False,default=20)
    unit_weights:Mapped[str]=mapped_column(String,nullable=False,default='')
    randomize_questions:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    shuffle_options:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    require_fullscreen:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    tab_switch_limit:Mapped[int]=mapped_column(Integer,nullable=False,default=3)
    last_generation_summary:Mapped[str]=mapped_column(String,nullable=False,default='')
    updated_at:Mapped[str]=mapped_column(String,nullable=False)

class AttemptQuestion(Base):
    __tablename__='attempt_questions'
    __table_args__=(UniqueConstraint('attempt_id','question_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    attempt_id:Mapped[int]=mapped_column(ForeignKey('attempts.id'),nullable=False)
    question_id:Mapped[int]=mapped_column(ForeignKey('questions.id'),nullable=False)
    position:Mapped[int]=mapped_column(Integer,nullable=False)
    option_order:Mapped[str]=mapped_column(String,nullable=False,default='ABCD')

class IntegrityEvent(Base):
    __tablename__='integrity_events'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    attempt_id:Mapped[int]=mapped_column(ForeignKey('attempts.id'),nullable=False)
    event_type:Mapped[str]=mapped_column(String,nullable=False)
    details:Mapped[str]=mapped_column(String,nullable=False,default='')
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class AuditLog(Base):
    __tablename__='audit_logs'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    actor:Mapped[str]=mapped_column(String,nullable=False)
    action:Mapped[str]=mapped_column(String,nullable=False)
    entity_type:Mapped[str]=mapped_column(String,nullable=False,default='')
    entity_id:Mapped[str]=mapped_column(String,nullable=False,default='')
    details:Mapped[str]=mapped_column(String,nullable=False,default='')
    created_at:Mapped[str]=mapped_column(String,nullable=False)


def now_dt(): return datetime.now().astimezone()
def now_iso(): return now_dt().isoformat(timespec='seconds')
def parse_dt(value): return datetime.fromisoformat(value)

def actor_label(s=None):
    role=web_session.get('role','system')
    uid=web_session.get('user_id')
    if role=='admin':
        return f"admin:{web_session.get('username',admin_username)}"
    if role=='faculty' and uid:
        s=s or DB(); row=s.get(Faculty,uid)
        return f'faculty:{row.username if row else uid}'
    if role=='student' and uid:
        return f'student:{uid}'
    return role

def audit_event(s,action,entity_type='',entity_id='',details=''):
    s.add(AuditLog(actor=actor_label(s),action=action,entity_type=str(entity_type or ''),entity_id=str(entity_id or ''),details=str(details or '')[:1500],created_at=now_iso()))

PRELOADED_BANK_FILE=RESOURCE_DIR/'preloaded_question_banks.json'
_PRELOADED_BANK_CACHE=None

def load_preloaded_question_banks():
    global _PRELOADED_BANK_CACHE
    if _PRELOADED_BANK_CACHE is None:
        try:
            payload=json.loads(PRELOADED_BANK_FILE.read_text(encoding='utf-8'))
            packs=payload.get('packs',[]) if isinstance(payload,dict) else []
            _PRELOADED_BANK_CACHE={str(p.get('slug')):p for p in packs if p.get('slug') and p.get('subject')}
        except Exception:
            _PRELOADED_BANK_CACHE={}
    return _PRELOADED_BANK_CACHE

def activate_preloaded_pack(s,pack):
    marker=f"preloaded:{pack['slug']}"
    existing=set(s.scalars(select(BankQuestion.question).where(BankQuestion.created_by==marker)).all())
    added=0
    for row in pack.get('questions',[]):
        question=(row.get('question') or '').strip()
        if not question or question in existing:
            continue
        ans=(row.get('correct_answer') or 'A').upper()
        if ans not in {'A','B','C','D'}:
            ans='A'
        bq=BankQuestion(
            subject=(row.get('subject') or pack.get('subject') or 'General').strip(),
            course_semester=(row.get('course_semester') or pack.get('course_semester') or '').strip(),
            unit=str(row.get('unit') or '').strip(),
            topic=(row.get('topic') or row.get('unit_title') or '').strip(),
            question_type='MCQ',
            question=question,
            option_a=str(row.get('option_a') or '').strip(),
            option_b=str(row.get('option_b') or '').strip(),
            option_c=str(row.get('option_c') or '').strip(),
            option_d=str(row.get('option_d') or '').strip(),
            correct_answer=ans,
            marks=max(1,int(row.get('marks') or 1)),
            difficulty=canonical_difficulty(row.get('difficulty')),
            bloom_level=canonical_bloom(row.get('bloom_level')),
            co_mapping=str(row.get('co_mapping') or '').strip(),
            tags=(str(row.get('tags') or '').strip()+f',preloaded:{pack["slug"]}').strip(','),
            status='approved',
            version=1,
            created_by=marker,
            created_at=now_iso(),
            updated_at=now_iso()
        )
        s.add(bq); added+=1
    return added,len(existing)

def preloaded_pack_statuses(s):
    output=[]
    for pack in load_preloaded_question_banks().values():
        marker=f"preloaded:{pack['slug']}"
        active=s.scalar(select(func.count()).select_from(BankQuestion).where(BankQuestion.created_by==marker)) or 0
        item=dict(pack)
        item['active_count']=int(active)
        item['is_active']=active>=int(pack.get('question_count') or 0) and int(pack.get('question_count') or 0)>0
        item['is_partial']=active>0 and not item['is_active']
        output.append(item)
    output.sort(key=lambda p:(p.get('category',''),p.get('subject','')))
    return output

def init_db():
    Base.metadata.create_all(engine)
    s=DB()
    try:
        if APP_MODE=='online' or not OFFLINE_REQUIRE_SETUP:
            admin=s.scalar(select(Admin).where(Admin.username==admin_username))
            if not admin:
                s.add(Admin(username=admin_username,password_hash=generate_password_hash(admin_password)))
            elif admin_password and not check_password_hash(admin.password_hash,admin_password):
                admin.password_hash=generate_password_hash(admin_password)
            s.commit()
    except IntegrityError:
        s.rollback()

def needs_offline_setup():
    if APP_MODE!='offline' or not OFFLINE_REQUIRE_SETUP:
        return False
    s=DB()
    return (s.scalar(select(func.count()).select_from(Admin)) or 0)==0

init_db()

@app.teardown_appcontext
def cleanup(_exc=None): DB.remove()

@app.before_request
def csrf_and_session_setup():
    if '_csrf_token' not in web_session: web_session['_csrf_token']=secrets.token_urlsafe(32)
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        supplied=request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not supplied or not secrets.compare_digest(str(supplied),str(web_session.get('_csrf_token',''))):
            abort(400,'Security token validation failed. Refresh the page and try again.')

@app.context_processor
def globals_for_templates():
    return {'csrf_token':web_session.get('_csrf_token',''),'web_session':web_session,'is_online':APP_MODE=='online','app_version':APP_VERSION}

@app.before_request
def offline_first_run_guard():
    if not needs_offline_setup(): return None
    allowed={'setup_admin','static','health'}
    if request.endpoint not in allowed: return redirect(url_for('setup_admin'))
    return None

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options','nosniff')
    response.headers.setdefault('X-Frame-Options','DENY')
    response.headers.setdefault('Referrer-Policy','same-origin')
    response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    response.headers.setdefault('Cache-Control','no-store' if request.path.startswith('/admin') or request.path.startswith('/student') else 'no-cache')
    return response

@app.route('/setup',methods=['GET','POST'])
def setup_admin():
    if not needs_offline_setup(): return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(username)<3: flash('Administrator username must contain at least 3 characters.','error')
        elif len(password)<10: flash('Administrator password must contain at least 10 characters.','error')
        elif password!=confirm: flash('Passwords do not match.','error')
        else:
            s=DB()
            try:
                s.add(Admin(username=username,password_hash=generate_password_hash(password))); s.commit(); flash('Administrator account created. You can now sign in.'); return redirect(url_for('home'))
            except IntegrityError:
                s.rollback(); flash('That administrator username is already in use.','error')
    return render_template('setup.html',login_page=True)

@app.route('/download/offline')
def offline_download():
    if APP_MODE!='online': return redirect(url_for('home'))
    parsed=urlparse(OFFLINE_DOWNLOAD_URL)
    if parsed.scheme not in {'https','http'} or not parsed.netloc: abort(503,'Offline download is temporarily unavailable.')
    return redirect(OFFLINE_DOWNLOAD_URL,code=302)

@app.template_filter('dt')
def format_dt(v):
    if not v:return '-'
    try:return parse_dt(v).strftime('%d %b %Y, %I:%M %p')
    except Exception:return v

def admin_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if web_session.get('role')!='admin': return redirect(url_for('home'))
        return fn(*a,**kw)
    return inner

def staff_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if web_session.get('role') not in {'admin','faculty'}: return redirect(url_for('home'))
        return fn(*a,**kw)
    return inner

def student_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if web_session.get('role')!='student': return redirect(url_for('home'))
        return fn(*a,**kw)
    return inner

def get_attempt(s,student_id,exam_id): return s.scalar(select(Attempt).where(Attempt.student_id==student_id,Attempt.exam_id==exam_id))

def student_exam_display_title(s, exam):
    """Return a clean student-facing title and distinguish duplicate Ready Exams as Part 1, Part 2, etc."""
    raw=(exam.title or '').strip()
    suffix=' - Ready Exam'
    if not raw.endswith(suffix):
        return raw
    base=raw[:-len(suffix)].strip()
    siblings=s.scalars(select(Exam).where(Exam.title==raw).order_by(Exam.id.asc())).all()
    if len(siblings)<=1:
        return base
    for idx,row in enumerate(siblings,1):
        if row.id==exam.id:
            return f"{base} - Part {idx}"
    return base

def result_performance(score,total_marks):
    total=total_marks or 0
    pct=round(((score or 0)/total)*100) if total else 0
    if pct>=90:
        return pct,'Outstanding','outstanding'
    if pct>=75:
        return pct,'Very Good','very-good'
    if pct>=60:
        return pct,'Good','good'
    if pct>=40:
        return pct,'Average','average'
    return pct,'Poor','poor'

def get_exam_config(s,exam_id,create=False):
    cfg=s.scalar(select(ExamConfig).where(ExamConfig.exam_id==exam_id))
    if not cfg and create:
        cfg=ExamConfig(exam_id=exam_id,question_count=0,pool_size=0,easy_pct=30,medium_pct=50,hard_pct=20,unit_weights='',randomize_questions=True,shuffle_options=True,require_fullscreen=False,tab_switch_limit=3,last_generation_summary='',updated_at=now_iso())
        s.add(cfg); s.flush()
    return cfg

def attempt_question_ids(s,attempt):
    rows=s.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id==attempt.id).order_by(AttemptQuestion.position)).all()
    if rows: return [r.question_id for r in rows]
    return [int(x) for x in (attempt.question_order or '').split(',') if x]

def save_answer_record(s,attempt_id,question_id,answer):
    row=s.scalar(select(Answer).where(Answer.attempt_id==attempt_id,Answer.question_id==question_id))
    if row: row.selected_answer=answer; row.saved_at=now_iso()
    else: s.add(Answer(attempt_id=attempt_id,question_id=question_id,selected_answer=answer,saved_at=now_iso()))

def finalize_attempt(s,attempt):
    if attempt.status=='submitted': return attempt
    qids=attempt_question_ids(s,attempt)
    questions=s.scalars(select(Question).where(Question.id.in_(qids))).all() if qids else []
    saved=s.scalars(select(Answer).where(Answer.attempt_id==attempt.id)).all(); amap={a.question_id:a.selected_answer for a in saved}
    attempt.score=sum(q.marks for q in questions if amap.get(q.id)==q.correct_answer)
    attempt.total_marks=sum(q.marks for q in questions); attempt.status='submitted'; attempt.submitted_at=now_iso(); s.commit(); return attempt

def canonical_difficulty(value):
    v=(value or 'Medium').strip().lower()
    return {'easy':'Easy','medium':'Medium','hard':'Hard'}.get(v,'Medium')

def canonical_bloom(value):
    allowed=['Remember','Understand','Apply','Analyze','Evaluate','Create']
    v=(value or 'Understand').strip().lower()
    for item in allowed:
        if item.lower()==v: return item
    return 'Understand'

def parse_unit_weights(text):
    text=(text or '').strip()
    if not text: return {}
    result={}
    for part in text.replace(';',',').split(','):
        part=part.strip()
        if not part: continue
        if ':' not in part: raise ValueError('Use unit distribution like 1:20, 2:30, 3:50.')
        unit,weight=part.split(':',1)
        unit=unit.strip()
        if unit.lower().startswith('unit '): unit=unit[5:].strip()
        try: weight=int(weight.strip())
        except ValueError as exc: raise ValueError('Unit weights must be whole numbers.') from exc
        if not unit or weight<0: raise ValueError('Unit distribution contains an invalid value.')
        result[unit]=weight
    if result and sum(result.values())<=0: raise ValueError('Unit distribution must contain a positive weight.')
    return result

def allocate_counts(total,weights):
    weights={str(k):max(0,float(v)) for k,v in weights.items() if float(v)>=0}
    if total<=0 or not weights or sum(weights.values())<=0: return {k:0 for k in weights}
    s=sum(weights.values()); raw={k:total*v/s for k,v in weights.items()}; out={k:int(math.floor(v)) for k,v in raw.items()}
    remainder=total-sum(out.values())
    for k,_ in sorted(raw.items(),key=lambda item:item[1]-math.floor(item[1]),reverse=True)[:remainder]: out[k]+=1
    return out

def choose_blueprint_questions(candidates,total,unit_weights,diff_weights):
    pool=list(candidates); random.shuffle(pool); total=min(total,len(pool))
    unit_targets=allocate_counts(total,unit_weights) if unit_weights else {}
    diff_targets=allocate_counts(total,diff_weights)
    selected=[]; unit_counts={k:0 for k in unit_targets}; diff_counts={k:0 for k in diff_targets}
    while len(selected)<total and pool:
        best_score=None; best=[]
        for q in pool:
            unit_key=(q.unit or '').strip()
            diff=canonical_difficulty(q.difficulty)
            unit_need=(unit_targets.get(unit_key,0)-unit_counts.get(unit_key,0)) if unit_targets else 0
            diff_need=diff_targets.get(diff,0)-diff_counts.get(diff,0)
            score=(4 if unit_need>0 else 0)+(3 if diff_need>0 else 0)+random.random()
            if unit_targets and unit_key not in unit_targets: score-=3
            if best_score is None or score>best_score: best_score=score; best=[q]
            elif abs(score-best_score)<1e-9: best.append(q)
        chosen=random.choice(best); pool.remove(chosen); selected.append(chosen)
        if chosen.unit in unit_counts: unit_counts[chosen.unit]+=1
        diff=canonical_difficulty(chosen.difficulty); diff_counts[diff]=diff_counts.get(diff,0)+1
    return selected,unit_targets,diff_targets,unit_counts,diff_counts

def copy_bank_question_to_exam(s,bq,exam_id):
    if s.scalar(select(ExamBankMap).where(ExamBankMap.exam_id==exam_id,ExamBankMap.bank_question_id==bq.id)): return False
    q=Question(exam_id=exam_id,question=bq.question,option_a=bq.option_a,option_b=bq.option_b,option_c=bq.option_c,option_d=bq.option_d,correct_answer=bq.correct_answer,marks=bq.marks)
    s.add(q); s.flush(); s.add(ExamBankMap(exam_id=exam_id,exam_question_id=q.id,bank_question_id=bq.id)); return True

def _cell_text(value):
    if value is None:return ''
    if isinstance(value,float) and value.is_integer():return str(int(value))
    return str(value).strip()

def _canonical_header(value):
    key=_cell_text(value).lower().replace('-','_').replace(' ','_')
    while '__' in key:key=key.replace('__','_')
    aliases={
        'roll':'roll_no','rollno':'roll_no','roll_number':'roll_no','student_id':'roll_no','registration_no':'roll_no','registration_number':'roll_no','enrollment_no':'roll_no','enrollment_number':'roll_no',
        'student_name':'name','full_name':'name','candidate_name':'name','pass':'password','login_password':'password','student_password':'password',
        'semester':'course_semester','course':'course_semester','co':'co_mapping','bloom':'bloom_level','answer':'correct_answer','correct':'correct_answer','type':'question_type'
    }
    return aliases.get(key,key)

def _rows_from_upload(upload):
    filename=(upload.filename or '').lower(); raw=upload.read()
    if not raw: raise ValueError('The uploaded file is empty.')
    if filename.endswith('.csv'):
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:raise ValueError('CSV must be UTF-8 encoded.') from exc
        all_rows=list(csv.reader(io.StringIO(text)))
    elif filename.endswith('.xlsx'):
        try:
            wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True); ws=wb.active; all_rows=[list(r) for r in ws.iter_rows(values_only=True)]
        except Exception as exc:raise ValueError('The Excel file could not be read. Please upload a valid .xlsx file.') from exc
    else: raise ValueError('Please upload a CSV or Excel (.xlsx) file.')
    if not all_rows:raise ValueError('The uploaded file has no rows.')
    headers=[_canonical_header(v) for v in all_rows[0]]; rows=[]
    for row_number,row in enumerate(all_rows[1:],start=2):
        values={headers[i]:_cell_text(row[i] if i<len(row) else '') for i in range(len(headers)) if headers[i]}
        if any(values.values()): values['_row_number']=row_number; rows.append(values)
    return headers,rows

@app.route('/',methods=['GET','POST'])
def home():
    if web_session.get('role') in {'admin','faculty'}: return redirect(url_for('admin_dashboard'))
    if web_session.get('role')=='student': return redirect(url_for('student_dashboard'))
    if request.method=='POST':
        s=DB(); typ=request.form.get('login_type')
        if typ=='admin':
            username=request.form.get('username','').strip(); password=request.form.get('password','')
            row=s.scalar(select(Admin).where(Admin.username==username))
            role='admin'
            if not row:
                row=s.scalar(select(Faculty).where(Faculty.username==username,Faculty.is_active==True)); role='faculty'
            if row and check_password_hash(row.password_hash,password):
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role=role,user_id=row.id,username=row.username)
                audit_event(s,'staff_login','user',row.id,role); s.commit(); return redirect(url_for('admin_dashboard'))
        else:
            row=s.scalar(select(Student).where(Student.roll_no==request.form.get('roll_no','').strip()))
            if row and check_password_hash(row.password_hash,request.form.get('password','')):
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role='student',user_id=row.id,username=row.roll_no); return redirect(url_for('student_dashboard'))
        flash('Invalid login credentials.','error')
    return render_template('login.html',login_page=True)

@app.route('/logout')
def logout(): web_session.clear(); return redirect(url_for('home'))

@app.route('/health')
def health():
    try:
        s=DB(); s.execute(select(1)); return jsonify(status='ok',mode=APP_MODE,database='postgresql' if DATABASE_URL.startswith('postgresql') else 'sqlite')
    except Exception:return jsonify(status='error'),503

@app.route('/admin')
@staff_required
def admin_dashboard():
    s=DB(); stats={
        'students':s.scalar(select(func.count()).select_from(Student)) or 0,
        'exams':s.scalar(select(func.count()).select_from(Exam)) or 0,
        'questions':s.scalar(select(func.count()).select_from(Question)) or 0,
        'bank_questions':s.scalar(select(func.count()).select_from(BankQuestion)) or 0,
        'attempts':s.scalar(select(func.count()).select_from(Attempt)) or 0,
        'approved':s.scalar(select(func.count()).select_from(BankQuestion).where(BankQuestion.status=='approved')) or 0
    }
    return render_template('admin_dashboard.html',stats=stats)

@app.route('/admin/students',methods=['GET','POST'])
@staff_required
def students():
    s=DB()
    if request.method=='POST':
        roll=request.form.get('roll_no','').strip(); name=request.form.get('name','').strip(); pw=request.form.get('password','')
        if not roll or not name or not pw: flash('All student fields are required.','error')
        else:
            try:
                st=Student(roll_no=roll,name=name,password_hash=generate_password_hash(pw),created_at=now_iso()); s.add(st); s.flush(); audit_event(s,'student_created','student',st.id,roll); s.commit(); flash('Student added.')
            except IntegrityError:s.rollback();flash('Roll number already exists.','error')
    rows=s.scalars(select(Student).order_by(Student.roll_no)).all(); return render_template('students.html',students=rows)

@app.route('/admin/students/import',methods=['POST'])
@staff_required
def import_students():
    upload=request.files.get('student_file')
    if not upload or not upload.filename: flash('Choose a CSV or Excel (.xlsx) file.','error'); return redirect(url_for('students'))
    try: headers,rows=_rows_from_upload(upload)
    except ValueError as exc: flash(str(exc),'error'); return redirect(url_for('students'))
    required={'roll_no','name','password'}
    if not required.issubset(set(headers)): flash('Required columns are: roll_no, name, password.','error'); return redirect(url_for('students'))
    s=DB(); existing=set(s.scalars(select(Student.roll_no)).all()); seen=set(); added=duplicates=invalid=0
    for row in rows:
        roll=row.get('roll_no','').strip(); name=row.get('name','').strip(); password=row.get('password','')
        if not roll or not name or not password: invalid+=1; continue
        if roll in existing or roll in seen: duplicates+=1; continue
        s.add(Student(roll_no=roll,name=name,password_hash=generate_password_hash(password),created_at=now_iso())); seen.add(roll); added+=1
    try:
        audit_event(s,'students_bulk_import','student','',f'added={added}, duplicates={duplicates}, invalid={invalid}'); s.commit()
    except IntegrityError:s.rollback();flash('Import could not be completed because one or more roll numbers conflict with existing students.','error');return redirect(url_for('students'))
    parts=[f'Imported {added} student login'+('' if added==1 else 's')+'.']
    if duplicates:parts.append(f'Skipped {duplicates} duplicate roll number'+('' if duplicates==1 else 's')+'.')
    if invalid:parts.append(f'Skipped {invalid} incomplete row'+('' if invalid==1 else 's')+'.')
    flash(' '.join(parts)); return redirect(url_for('students'))

@app.route('/admin/students/template/<fmt>')
@staff_required
def student_import_template(fmt):
    headers=['roll_no','name','password']
    if fmt=='csv':
        out=io.StringIO(newline=''); writer=csv.writer(out); writer.writerow(headers); data=io.BytesIO(out.getvalue().encode('utf-8-sig')); return send_file(data,mimetype='text/csv',as_attachment=True,download_name='student_import_template.csv')
    if fmt=='xlsx':
        wb=Workbook(); ws=wb.active; ws.title='Students'; ws.append(headers)
        for cell in ws[1]:cell.font=Font(bold=True)
        ws.column_dimensions['A'].width=18;ws.column_dimensions['B'].width=28;ws.column_dimensions['C'].width=22
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='student_import_template.xlsx')
    abort(404)

@app.route('/admin/question-bank',methods=['GET','POST'])
@staff_required
def question_bank():
    s=DB()
    if request.method=='POST':
        question=request.form.get('question','').strip(); ans=request.form.get('correct_answer','A').upper()
        if not question: flash('Question text is required.','error')
        elif ans not in {'A','B','C','D'}: flash('Correct answer must be A, B, C or D.','error')
        else:
            try: marks=max(1,int(request.form.get('marks','1')))
            except ValueError: marks=1
            status='approved' if web_session.get('role')=='admin' and request.form.get('status')=='approved' else 'draft'
            bq=BankQuestion(
                subject=request.form.get('subject','General').strip() or 'General',course_semester=request.form.get('course_semester','').strip(),unit=request.form.get('unit','').strip(),topic=request.form.get('topic','').strip(),question_type='MCQ',question=question,
                option_a=request.form.get('option_a','').strip(),option_b=request.form.get('option_b','').strip(),option_c=request.form.get('option_c','').strip(),option_d=request.form.get('option_d','').strip(),correct_answer=ans,marks=marks,
                difficulty=canonical_difficulty(request.form.get('difficulty')),bloom_level=canonical_bloom(request.form.get('bloom_level')),co_mapping=request.form.get('co_mapping','').strip(),tags=request.form.get('tags','').strip(),status=status,version=1,created_by=actor_label(s),created_at=now_iso(),updated_at=now_iso())
            s.add(bq); s.flush(); audit_event(s,'bank_question_created','bank_question',bq.id,status); s.commit(); flash('Question added to the bank.')
            return redirect(url_for('question_bank'))
    q=(request.args.get('q') or '').strip(); subject=(request.args.get('subject') or '').strip(); unit=(request.args.get('unit') or '').strip(); difficulty=(request.args.get('difficulty') or '').strip(); status=(request.args.get('status') or '').strip()
    stmt=select(BankQuestion)
    if q: stmt=stmt.where(or_(BankQuestion.question.ilike(f'%{q}%'),BankQuestion.topic.ilike(f'%{q}%'),BankQuestion.tags.ilike(f'%{q}%')))
    if subject: stmt=stmt.where(BankQuestion.subject==subject)
    if unit: stmt=stmt.where(BankQuestion.unit==unit)
    if difficulty: stmt=stmt.where(BankQuestion.difficulty==canonical_difficulty(difficulty))
    if status: stmt=stmt.where(BankQuestion.status==status)
    rows=s.scalars(stmt.order_by(BankQuestion.id.desc())).all()
    subjects=s.scalars(select(BankQuestion.subject).distinct().order_by(BankQuestion.subject)).all(); units=s.scalars(select(BankQuestion.unit).where(BankQuestion.unit!='').distinct().order_by(BankQuestion.unit)).all(); exams_list=s.scalars(select(Exam).order_by(Exam.id.desc())).all()
    usage=dict(s.execute(select(ExamBankMap.bank_question_id,func.count(func.distinct(ExamBankMap.exam_id))).group_by(ExamBankMap.bank_question_id)).all())
    preloaded_packs=preloaded_pack_statuses(s)
    preloaded_categories=sorted({p.get('category','General') for p in preloaded_packs})
    return render_template('question_bank.html',questions=rows,subjects=subjects,units=units,exams=exams_list,usage=usage,filters={'q':q,'subject':subject,'unit':unit,'difficulty':difficulty,'status':status},preloaded_packs=preloaded_packs,preloaded_categories=preloaded_categories)



@app.route('/admin/question-bank/preloaded/export/<fmt>')
@staff_required
def export_preloaded_question_banks(fmt):
    headers=['subject','course_semester','unit','topic','question','option_a','option_b','option_c','option_d','correct_answer','marks','difficulty','bloom_level','co_mapping','tags']
    rows=[]
    for pack in load_preloaded_question_banks().values():
        for q in pack.get('questions',[]):
            rows.append([q.get(h,'') for h in headers])
    if fmt=='csv':
        out=io.StringIO(newline=''); writer=csv.writer(out); writer.writerow(headers); writer.writerows(rows)
        data=io.BytesIO(out.getvalue().encode('utf-8-sig'))
        return send_file(data,mimetype='text/csv',as_attachment=True,download_name='preloaded_engineering_question_banks.csv')
    if fmt=='xlsx':
        wb=Workbook(); ws=wb.active; ws.title='Question Banks'; ws.append(headers)
        for cell in ws[1]: cell.font=Font(bold=True)
        for row in rows: ws.append(row)
        widths={'A':34,'B':24,'C':8,'D':28,'E':58,'F':45,'G':45,'H':45,'I':45,'J':14,'K':9,'L':12,'M':16,'N':12,'O':34}
        for col,width in widths.items(): ws.column_dimensions[col].width=width
        data=io.BytesIO(); wb.save(data); data.seek(0)
        return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='preloaded_engineering_question_banks.xlsx')
    abort(404)

@app.route('/admin/question-bank/preloaded/<slug>/activate',methods=['POST'])
@staff_required
def activate_preloaded_question_bank(slug):
    pack=load_preloaded_question_banks().get(slug)
    if not pack: abort(404)
    s=DB()
    try:
        added,existing=activate_preloaded_pack(s,pack)
        audit_event(s,'preloaded_question_bank_activated','question_bank',slug,f'subject={pack["subject"]}, added={added}, existing={existing}')
        s.commit()
    except Exception as exc:
        s.rollback(); flash(f'Could not activate the preloaded bank: {exc}','error')
        return redirect(url_for('question_bank'))
    if added:
        flash(f'Activated {pack["subject"]}: {added} approved questions across {pack.get("unit_count",5)} units.')
    else:
        flash(f'{pack["subject"]} is already activated.')
    return redirect(url_for('question_bank',subject=pack['subject'],status='approved'))

@app.route('/admin/question-bank/preloaded/category/activate',methods=['POST'])
@staff_required
def activate_preloaded_category():
    category=(request.form.get('category') or '').strip()
    packs=[p for p in load_preloaded_question_banks().values() if p.get('category')==category]
    if not packs:
        flash('No preloaded subject banks were found for that category.','error')
        return redirect(url_for('question_bank'))
    s=DB(); total=0
    try:
        for pack in packs:
            added,_=activate_preloaded_pack(s,pack); total+=added
        audit_event(s,'preloaded_category_activated','question_bank','',f'category={category}, added={total}')
        s.commit()
    except Exception as exc:
        s.rollback(); flash(f'Could not activate the category: {exc}','error')
        return redirect(url_for('question_bank'))
    flash(f'Activated {category}: {total} new approved questions from {len(packs)} subject bank(s).')
    return redirect(url_for('question_bank'))

@app.route('/admin/question-bank/preloaded/<slug>/quick-exam',methods=['POST'])
@staff_required
def create_exam_from_preloaded_bank(slug):
    pack=load_preloaded_question_banks().get(slug)
    if not pack: abort(404)
    s=DB()
    try:
        added,_=activate_preloaded_pack(s,pack)
        if added: s.flush()
        marker=f'preloaded:{slug}'
        bank_rows=s.scalars(select(BankQuestion).where(BankQuestion.created_by==marker,BankQuestion.status=='approved').order_by(BankQuestion.unit,BankQuestion.id)).all()
        if not bank_rows:
            flash('This subject bank has no approved questions.','error'); s.rollback()
            return redirect(url_for('question_bank'))
        title=f"{pack['subject']} - Ready Exam"
        duration=20
        exam=Exam(title=title,duration_minutes=duration,is_active=False,created_at=now_iso())
        s.add(exam); s.flush()
        cfg=get_exam_config(s,exam.id,create=True)
        cfg.subject=pack['subject']; cfg.course_semester=pack.get('course_semester','')
        cfg.question_count=min(10,len(bank_rows)); cfg.pool_size=len(bank_rows)
        cfg.easy_pct=30; cfg.medium_pct=40; cfg.hard_pct=30
        unit_numbers=sorted({(q.unit or '').strip() for q in bank_rows if (q.unit or '').strip()})
        cfg.unit_weights=json.dumps({u:1 for u in unit_numbers},ensure_ascii=False)
        cfg.randomize_questions=True; cfg.shuffle_options=True; cfg.require_fullscreen=False; cfg.tab_switch_limit=3
        cfg.last_generation_summary=f"Ready-made pool from {pack['subject']}: {len(bank_rows)} approved questions; each student receives {cfg.question_count}."
        cfg.updated_at=now_iso()
        for bq in bank_rows:
            copy_bank_question_to_exam(s,bq,exam.id)
        audit_event(s,'ready_exam_created','exam',exam.id,f'preloaded={slug}, pool={len(bank_rows)}, per_student={cfg.question_count}')
        s.commit()
        flash(f'Created "{title}" with {len(bank_rows)}-question pool. Each student will receive {cfg.question_count} randomized questions. Review it, then click Activate.')
        return redirect(url_for('exams'))
    except Exception as exc:
        s.rollback(); flash(f'Could not create the ready exam: {exc}','error')
        return redirect(url_for('question_bank'))

@app.route('/admin/question-bank/preloaded/<slug>/unit-set/<unit>/<set_code>/quick-exam',methods=['POST'])
@staff_required
def create_unit_set_exam_from_preloaded_bank(slug,unit,set_code):
    pack=load_preloaded_question_banks().get(slug)
    if not pack: abort(404)
    set_code=str(set_code or '').upper()
    unit=str(unit or '').strip()
    configured=next((p for p in pack.get('paper_sets',[]) if str(p.get('unit'))==unit and str(p.get('set_code','')).upper()==set_code),None)
    if not configured:
        abort(404)
    s=DB()
    try:
        added,_=activate_preloaded_pack(s,pack)
        if added: s.flush()
        marker=f'preloaded:{slug}'
        set_marker=f'paper-set-{set_code.lower()}'
        bank_rows=s.scalars(select(BankQuestion).where(
            BankQuestion.created_by==marker,
            BankQuestion.status=='approved',
            BankQuestion.unit==unit,
            BankQuestion.tags.contains(set_marker)
        ).order_by(BankQuestion.id)).all()
        expected=int(configured.get('question_count') or 0)
        if expected and len(bank_rows)!=expected:
            flash(f'Unit {unit} Set {set_code} is incomplete: expected {expected} questions but found {len(bank_rows)}.','error')
            s.rollback(); return redirect(url_for('question_bank'))
        if not bank_rows:
            flash(f'No approved questions were found for Unit {unit} Set {set_code}.','error')
            s.rollback(); return redirect(url_for('question_bank'))
        title=f"{pack['subject']} - Unit {unit} - Set {set_code}"
        duration=max(5,int(configured.get('duration_minutes') or 15))
        exam=Exam(title=title,duration_minutes=duration,is_active=False,created_at=now_iso())
        s.add(exam); s.flush()
        cfg=get_exam_config(s,exam.id,create=True)
        cfg.subject=pack['subject']; cfg.course_semester=pack.get('course_semester','')
        cfg.question_count=len(bank_rows); cfg.pool_size=len(bank_rows)
        easy=sum(1 for x in bank_rows if canonical_difficulty(x.difficulty)=='Easy')
        medium=sum(1 for x in bank_rows if canonical_difficulty(x.difficulty)=='Medium')
        hard=sum(1 for x in bank_rows if canonical_difficulty(x.difficulty)=='Hard')
        total=max(1,len(bank_rows))
        cfg.easy_pct=round(easy*100/total); cfg.medium_pct=round(medium*100/total); cfg.hard_pct=max(0,100-cfg.easy_pct-cfg.medium_pct)
        cfg.unit_weights=json.dumps({unit:1},ensure_ascii=False)
        cfg.randomize_questions=False; cfg.shuffle_options=False; cfg.require_fullscreen=False; cfg.tab_switch_limit=3
        cfg.last_generation_summary=f"Prepared Unit {unit} Set {set_code}: {len(bank_rows)} fixed syllabus-aligned MCQs."
        cfg.updated_at=now_iso()
        for bq in bank_rows:
            copy_bank_question_to_exam(s,bq,exam.id)
        audit_event(s,'unit_set_exam_created','exam',exam.id,f'preloaded={slug}, unit={unit}, set={set_code}, questions={len(bank_rows)}')
        s.commit()
        flash(f'Created "{title}" with {len(bank_rows)} fixed questions. Review it, then click Activate.')
        return redirect(url_for('exams'))
    except Exception as exc:
        s.rollback(); flash(f'Could not create Unit {unit} Set {set_code}: {exc}','error')
        return redirect(url_for('question_bank'))

@app.route('/admin/question-bank/import',methods=['POST'])
@staff_required
def import_question_bank():
    upload=request.files.get('question_file')
    if not upload or not upload.filename: flash('Choose a CSV or Excel (.xlsx) file.','error');return redirect(url_for('question_bank'))
    try: headers,rows=_rows_from_upload(upload)
    except ValueError as exc: flash(str(exc),'error');return redirect(url_for('question_bank'))
    required={'subject','question','option_a','option_b','option_c','option_d','correct_answer','marks'}
    if not required.issubset(set(headers)): flash('Question bank file is missing required columns. Download the template and try again.','error');return redirect(url_for('question_bank'))
    s=DB(); added=invalid=0
    for r in rows:
        ans=(r.get('correct_answer') or '').upper().strip(); question=(r.get('question') or '').strip()
        if not question or ans not in {'A','B','C','D'}: invalid+=1;continue
        try:marks=max(1,int(r.get('marks') or 1))
        except ValueError:marks=1
        requested_status=(r.get('status') or 'draft').lower(); status='approved' if web_session.get('role')=='admin' and requested_status=='approved' else 'draft'
        s.add(BankQuestion(subject=(r.get('subject') or 'General').strip() or 'General',course_semester=(r.get('course_semester') or '').strip(),unit=(r.get('unit') or '').strip(),topic=(r.get('topic') or '').strip(),question_type='MCQ',question=question,option_a=(r.get('option_a') or '').strip(),option_b=(r.get('option_b') or '').strip(),option_c=(r.get('option_c') or '').strip(),option_d=(r.get('option_d') or '').strip(),correct_answer=ans,marks=marks,difficulty=canonical_difficulty(r.get('difficulty')),bloom_level=canonical_bloom(r.get('bloom_level')),co_mapping=(r.get('co_mapping') or '').strip(),tags=(r.get('tags') or '').strip(),status=status,version=1,created_by=actor_label(s),created_at=now_iso(),updated_at=now_iso()));added+=1
    audit_event(s,'question_bank_bulk_import','bank_question','',f'added={added}, invalid={invalid}');s.commit();flash(f'Imported {added} question(s).'+(f' Skipped {invalid} invalid row(s).' if invalid else ''));return redirect(url_for('question_bank'))

@app.route('/admin/question-bank/template/<fmt>')
@staff_required
def question_bank_template(fmt):
    headers=['subject','course_semester','unit','topic','question','option_a','option_b','option_c','option_d','correct_answer','marks','difficulty','bloom_level','co_mapping','tags','status']
    example=['Mobile Application Development','B.Tech CSE / Sem 5','2','Activity Lifecycle','Which callback is called when an Activity is first created?','onStart()','onCreate()','onResume()','onPause()','B','1','Medium','Understand','CO2','activity,lifecycle','approved']
    if fmt=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out);writer.writerow(headers);writer.writerow(example);data=io.BytesIO(out.getvalue().encode('utf-8-sig'));return send_file(data,mimetype='text/csv',as_attachment=True,download_name='question_bank_template.csv')
    if fmt=='xlsx':
        wb=Workbook();ws=wb.active;ws.title='Question Bank';ws.append(headers);ws.append(example)
        for cell in ws[1]:cell.font=Font(bold=True)
        for col,width in {'A':28,'B':24,'C':10,'D':24,'E':58,'F':26,'G':26,'H':26,'I':26,'J':15,'K':10,'L':14,'M':16,'N':14,'O':26,'P':12}.items():ws.column_dimensions[col].width=width
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='question_bank_template.xlsx')
    abort(404)

@app.route('/admin/question-bank/<int:question_id>/edit',methods=['GET','POST'])
@staff_required
def edit_bank_question(question_id):
    s=DB();q=s.get(BankQuestion,question_id)
    if not q:abort(404)
    revisions=s.scalars(select(QuestionRevision).where(QuestionRevision.bank_question_id==q.id).order_by(QuestionRevision.id.desc())).all()
    if request.method=='POST':
        snapshot={c.name:getattr(q,c.name) for c in BankQuestion.__table__.columns if c.name not in {'id','updated_at'}}
        s.add(QuestionRevision(bank_question_id=q.id,version=q.version,snapshot_json=json.dumps(snapshot,ensure_ascii=False),changed_by=actor_label(s),changed_at=now_iso()))
        q.subject=request.form.get('subject','General').strip() or 'General';q.course_semester=request.form.get('course_semester','').strip();q.unit=request.form.get('unit','').strip();q.topic=request.form.get('topic','').strip();q.question=request.form.get('question','').strip();q.option_a=request.form.get('option_a','').strip();q.option_b=request.form.get('option_b','').strip();q.option_c=request.form.get('option_c','').strip();q.option_d=request.form.get('option_d','').strip();q.correct_answer=request.form.get('correct_answer','A').upper()
        try:q.marks=max(1,int(request.form.get('marks','1')))
        except ValueError:q.marks=1
        q.difficulty=canonical_difficulty(request.form.get('difficulty'));q.bloom_level=canonical_bloom(request.form.get('bloom_level'));q.co_mapping=request.form.get('co_mapping','').strip();q.tags=request.form.get('tags','').strip();q.version+=1;q.updated_at=now_iso()
        if web_session.get('role')=='admin':q.status=request.form.get('status','draft') if request.form.get('status') in {'draft','approved'} else 'draft'
        else:q.status='draft'
        audit_event(s,'bank_question_edited','bank_question',q.id,f'version={q.version}, status={q.status}');s.commit();flash('Question updated. Previous version was preserved.');return redirect(url_for('edit_bank_question',question_id=q.id))
    return render_template('question_bank_edit.html',question=q,revisions=revisions)

@app.route('/admin/question-bank/<int:question_id>/approve',methods=['POST'])
@admin_required
def approve_bank_question(question_id):
    s=DB();q=s.get(BankQuestion,question_id)
    if not q:abort(404)
    q.status='approved';q.updated_at=now_iso();audit_event(s,'bank_question_approved','bank_question',q.id,q.subject);s.commit();flash('Question approved.');return redirect(request.referrer or url_for('question_bank'))

@app.route('/admin/question-bank/add-to-exam',methods=['POST'])
@staff_required
def bank_add_to_exam():
    try:exam_id=int(request.form.get('exam_id','0'))
    except ValueError:exam_id=0
    ids=[]
    for v in request.form.getlist('question_ids'):
        try:ids.append(int(v))
        except ValueError:pass
    s=DB();exam=s.get(Exam,exam_id)
    if not exam or not ids:flash('Select an exam and at least one bank question.','error');return redirect(url_for('question_bank'))
    rows=s.scalars(select(BankQuestion).where(BankQuestion.id.in_(ids),BankQuestion.status=='approved')).all();added=0
    for q in rows:
        if copy_bank_question_to_exam(s,q,exam_id):added+=1
    audit_event(s,'bank_questions_added_to_exam','exam',exam_id,f'added={added}');s.commit();flash(f'Added {added} approved question(s) to {exam.title}.');return redirect(url_for('questions',exam_id=exam_id))

@app.route('/admin/exams',methods=['GET','POST'])
@staff_required
def exams():
    s=DB()
    if request.method=='POST':
        try:duration=max(1,int(request.form.get('duration','30')))
        except ValueError:duration=30
        title=request.form.get('title','').strip()
        if title:
            e=Exam(title=title,duration_minutes=duration,is_active=False,created_at=now_iso());s.add(e);s.flush();get_exam_config(s,e.id,create=True);audit_event(s,'exam_created','exam',e.id,title);s.commit();flash('Exam created.')
    raw=s.execute(select(Exam,func.count(Question.id)).outerjoin(Question,Question.exam_id==Exam.id).group_by(Exam.id).order_by(Exam.id.desc())).all();rows=[]
    for e,count in raw:
        cfg=get_exam_config(s,e.id);target=(cfg.question_count if cfg and cfg.question_count else count)
        rows.append(type('ExamRow',(),{'id':e.id,'title':e.title,'duration_minutes':e.duration_minutes,'is_active':e.is_active,'question_count':count,'student_question_count':min(target,count) if count else 0})())
    return render_template('exams.html',exams=rows)

@app.route('/admin/exam/<int:exam_id>/toggle',methods=['POST'])
@staff_required
def toggle_exam(exam_id):
    s=DB();e=s.get(Exam,exam_id)
    if e:
        if not e.is_active and (s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==exam_id)) or 0)==0:flash('Add questions before activating this exam.','error');return redirect(url_for('exams'))
        e.is_active=not bool(e.is_active);audit_event(s,'exam_activated' if e.is_active else 'exam_deactivated','exam',e.id,e.title);s.commit()
    return redirect(url_for('exams'))

@app.route('/admin/exam/<int:exam_id>/builder',methods=['GET','POST'])
@staff_required
def exam_builder(exam_id):
    s=DB();exam=s.get(Exam,exam_id)
    if not exam:abort(404)
    cfg=get_exam_config(s,exam_id,create=True)
    if request.method=='POST':
        action=request.form.get('action','save')
        try:
            qcount=max(1,int(request.form.get('question_count','20')));pool_size=max(qcount,int(request.form.get('pool_size',str(qcount))))
            easy=max(0,int(request.form.get('easy_pct','30')));medium=max(0,int(request.form.get('medium_pct','50')));hard=max(0,int(request.form.get('hard_pct','20')));tab_limit=max(0,int(request.form.get('tab_switch_limit','3')))
        except ValueError:flash('Blueprint numeric values are invalid.','error');return redirect(url_for('exam_builder',exam_id=exam_id))
        if easy+medium+hard!=100:flash('Difficulty distribution must total 100%.','error');return redirect(url_for('exam_builder',exam_id=exam_id))
        try:unit_weights=parse_unit_weights(request.form.get('unit_weights',''))
        except ValueError as exc:flash(str(exc),'error');return redirect(url_for('exam_builder',exam_id=exam_id))
        cfg.subject=request.form.get('subject','').strip();cfg.course_semester=request.form.get('course_semester','').strip();cfg.question_count=qcount;cfg.pool_size=pool_size;cfg.easy_pct=easy;cfg.medium_pct=medium;cfg.hard_pct=hard;cfg.unit_weights=json.dumps(unit_weights,ensure_ascii=False);cfg.randomize_questions=request.form.get('randomize_questions')=='on';cfg.shuffle_options=request.form.get('shuffle_options')=='on';cfg.require_fullscreen=request.form.get('require_fullscreen')=='on';cfg.tab_switch_limit=tab_limit;cfg.updated_at=now_iso();s.flush()
        if action=='generate':
            if (s.scalar(select(func.count()).select_from(Attempt).where(Attempt.exam_id==exam_id)) or 0)>0:flash('This exam already has attempts. The question pool is locked to protect result integrity.','error');s.rollback();return redirect(url_for('exam_builder',exam_id=exam_id))
            stmt=select(BankQuestion).where(BankQuestion.status=='approved')
            if cfg.subject:stmt=stmt.where(BankQuestion.subject==cfg.subject)
            if cfg.course_semester:stmt=stmt.where(BankQuestion.course_semester==cfg.course_semester)
            candidates=s.scalars(stmt).all()
            if unit_weights:candidates=[q for q in candidates if (q.unit or '').strip() in unit_weights]
            selected,ut,dt,uc,dc=choose_blueprint_questions(candidates,pool_size,unit_weights,{'Easy':easy,'Medium':medium,'Hard':hard})
            maps=s.scalars(select(ExamBankMap).where(ExamBankMap.exam_id==exam_id)).all(); mapped_qids=[m.exam_question_id for m in maps]
            for m in maps:s.delete(m)
            s.flush()
            for qid in mapped_qids:
                q=s.get(Question,qid)
                if q:s.delete(q)
            s.flush();added=0
            for bq in selected:
                if copy_bank_question_to_exam(s,bq,exam_id):added+=1
            summary=f'Generated pool: {added}/{pool_size}. Difficulty actual: Easy {dc.get("Easy",0)}, Medium {dc.get("Medium",0)}, Hard {dc.get("Hard",0)}.'
            if unit_weights:summary+=' Units: '+', '.join(f'{k}={uc.get(k,0)}' for k in unit_weights)+'.'
            if added<pool_size:summary+=' Bank does not yet contain enough approved questions for the requested blueprint.'
            cfg.last_generation_summary=summary;audit_event(s,'exam_pool_generated','exam',exam_id,summary);s.commit();flash(summary);return redirect(url_for('exam_builder',exam_id=exam_id))
        audit_event(s,'exam_blueprint_saved','exam',exam_id,f'questions={qcount}, pool={pool_size}');s.commit();flash('Exam blueprint and integrity settings saved.');return redirect(url_for('exam_builder',exam_id=exam_id))
    subjects=s.scalars(select(BankQuestion.subject).where(BankQuestion.status=='approved').distinct().order_by(BankQuestion.subject)).all();pool_count=s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==exam_id)) or 0;attempt_count=s.scalar(select(func.count()).select_from(Attempt).where(Attempt.exam_id==exam_id)) or 0
    try:unit_weights_display=', '.join(f'{k}:{v}' for k,v in json.loads(cfg.unit_weights or '{}').items())
    except Exception:unit_weights_display=''
    return render_template('exam_builder.html',exam=exam,cfg=cfg,subjects=subjects,pool_count=pool_count,attempt_count=attempt_count,unit_weights_display=unit_weights_display)

@app.route('/admin/exam/<int:exam_id>/questions',methods=['GET','POST'])
@staff_required
def questions(exam_id):
    s=DB();exam=s.get(Exam,exam_id)
    if not exam:abort(404)
    if request.method=='POST':
        try:marks=max(1,int(request.form.get('marks','1')))
        except ValueError:marks=1
        ans=request.form.get('correct_answer','A').upper()
        if ans not in {'A','B','C','D'}:ans='A'
        q=Question(exam_id=exam_id,question=request.form.get('question','').strip(),option_a=request.form.get('option_a','').strip(),option_b=request.form.get('option_b','').strip(),option_c=request.form.get('option_c','').strip(),option_d=request.form.get('option_d','').strip(),correct_answer=ans,marks=marks);s.add(q);s.flush();audit_event(s,'exam_question_added','exam',exam_id,f'question_id={q.id}');s.commit();flash('Question added.')
    qs=s.scalars(select(Question).where(Question.exam_id==exam_id).order_by(Question.id)).all();mapped=set(s.scalars(select(ExamBankMap.exam_question_id).where(ExamBankMap.exam_id==exam_id)).all());return render_template('questions.html',exam=exam,questions=qs,mapped=mapped)

@app.route('/admin/exam/<int:exam_id>/import',methods=['POST'])
@staff_required
def import_questions(exam_id):
    f=request.files.get('csv_file')
    if not f:flash('Choose a CSV file.','error');return redirect(url_for('questions',exam_id=exam_id))
    try:text=f.stream.read().decode('utf-8-sig')
    except UnicodeDecodeError:flash('CSV must be UTF-8 encoded.','error');return redirect(url_for('questions',exam_id=exam_id))
    reader=csv.DictReader(io.StringIO(text));required={'question','option_a','option_b','option_c','option_d','correct_answer','marks'}
    if not required.issubset(set(reader.fieldnames or [])):flash('CSV columns are incorrect. Use sample_questions.csv.','error');return redirect(url_for('questions',exam_id=exam_id))
    s=DB();count=0
    for r in reader:
        ans=(r.get('correct_answer') or '').strip().upper()
        if ans not in {'A','B','C','D'}:continue
        try:marks=max(1,int(r.get('marks') or 1))
        except ValueError:marks=1
        if not (r.get('question') or '').strip():continue
        s.add(Question(exam_id=exam_id,question=r['question'].strip(),option_a=(r.get('option_a') or '').strip(),option_b=(r.get('option_b') or '').strip(),option_c=(r.get('option_c') or '').strip(),option_d=(r.get('option_d') or '').strip(),correct_answer=ans,marks=marks));count+=1
    audit_event(s,'exam_questions_csv_import','exam',exam_id,f'count={count}');s.commit();flash(f'Imported {count} questions.');return redirect(url_for('questions',exam_id=exam_id))

def result_rows(s,exam_id=None):
    stmt=select(Attempt,Student,Exam).join(Student,Student.id==Attempt.student_id).join(Exam,Exam.id==Attempt.exam_id)
    if exam_id:stmt=stmt.where(Exam.id==exam_id)
    raw=s.execute(stmt.order_by(Attempt.id.desc())).all();rows=[]
    violation_counts=dict(s.execute(select(IntegrityEvent.attempt_id,func.count(IntegrityEvent.id)).group_by(IntegrityEvent.attempt_id)).all())
    for a,st,e in raw:
        rows.append(type('ResultRow',(),{'attempt_id':a.id,'roll_no':st.roll_no,'name':st.name,'title':e.title,'exam_id':e.id,'status':a.status,'score':a.score,'total_marks':a.total_marks,'started_at':a.started_at,'submitted_at':a.submitted_at,'violations':violation_counts.get(a.id,0)})())
    return rows

@app.route('/admin/results')
@staff_required
def results():
    s=DB();exam_id=request.args.get('exam_id',type=int);rows=result_rows(s,exam_id);exams_list=s.scalars(select(Exam).order_by(Exam.title)).all();return render_template('results.html',rows=rows,exams=exams_list,selected_exam_id=exam_id)

@app.route('/admin/results/export/<fmt>')
@staff_required
def export_results(fmt):
    s=DB();exam_id=request.args.get('exam_id',type=int);rows=result_rows(s,exam_id);headers=['roll_no','name','exam','status','score','total_marks','integrity_events','started','submitted']
    matrix=[[r.roll_no,r.name,r.title,r.status,r.score if r.score is not None else '',r.total_marks if r.total_marks is not None else '',r.violations,r.started_at,r.submitted_at or ''] for r in rows]
    suffix=f'_exam_{exam_id}' if exam_id else '_all'
    if fmt=='csv':
        out=io.StringIO(newline='');w=csv.writer(out);w.writerow(headers);w.writerows(matrix);data=io.BytesIO(out.getvalue().encode('utf-8-sig'));return send_file(data,mimetype='text/csv',as_attachment=True,download_name=f'exam_results{suffix}.csv')
    if fmt=='xlsx':
        wb=Workbook();ws=wb.active;ws.title='Results';ws.append(headers)
        for row in matrix:ws.append(row)
        for cell in ws[1]:cell.font=Font(bold=True)
        widths=[16,28,30,14,10,12,16,24,24]
        for idx,width in enumerate(widths,1):ws.column_dimensions[chr(64+idx)].width=width
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=f'exam_results{suffix}.xlsx')
    abort(404)

@app.route('/admin/analytics')
@staff_required
def analytics():
    s=DB();bank=s.scalars(select(BankQuestion).order_by(BankQuestion.subject,BankQuestion.unit,BankQuestion.id)).all();maps=s.scalars(select(ExamBankMap)).all();bank_by_exam_q={m.exam_question_id:m.bank_question_id for m in maps};exam_q_ids=list(bank_by_exam_q)
    qcorrect={q.id:q.correct_answer for q in (s.scalars(select(Question).where(Question.id.in_(exam_q_ids))).all() if exam_q_ids else [])};attempts=s.scalars(select(Attempt).where(Attempt.status=='submitted')).all();attempt_pct={a.id:((a.score or 0)/(a.total_marks or 1)) for a in attempts};submitted_ids=set(attempt_pct)
    stats={q.id:{'responses':0,'correct':0,'samples':[]} for q in bank}
    if exam_q_ids and submitted_ids:
        answers=s.scalars(select(Answer).where(Answer.question_id.in_(exam_q_ids),Answer.attempt_id.in_(submitted_ids))).all()
        for a in answers:
            bid=bank_by_exam_q.get(a.question_id)
            if bid not in stats:continue
            ok=a.selected_answer==qcorrect.get(a.question_id);stats[bid]['responses']+=1;stats[bid]['correct']+=1 if ok else 0;stats[bid]['samples'].append((attempt_pct.get(a.attempt_id,0),1 if ok else 0))
    usage=dict(s.execute(select(ExamBankMap.bank_question_id,func.count(func.distinct(ExamBankMap.exam_id))).group_by(ExamBankMap.bank_question_id)).all());rows=[]
    for q in bank:
        st=stats[q.id];rate=(st['correct']/st['responses']) if st['responses'] else None;disc=None
        samples=sorted(st['samples'],key=lambda x:x[0])
        if len(samples)>=6:
            n=max(1,round(len(samples)*0.27));bottom=samples[:n];top=samples[-n:];disc=(sum(x[1] for x in top)/n)-(sum(x[1] for x in bottom)/n)
        observed='-' if rate is None else ('Easy' if rate>=0.75 else 'Medium' if rate>=0.4 else 'Hard')
        rows.append(type('AnalyticsRow',(),{'id':q.id,'subject':q.subject,'unit':q.unit,'topic':q.topic,'question':q.question,'declared_difficulty':q.difficulty,'times_used':usage.get(q.id,0),'responses':st['responses'],'correct_rate':rate,'observed_difficulty':observed,'discrimination':disc})())
    return render_template('analytics.html',rows=rows)

@app.route('/admin/faculty',methods=['GET','POST'])
@admin_required
def faculty_users():
    s=DB()
    if request.method=='POST':
        username=request.form.get('username','').strip();name=request.form.get('name','').strip();password=request.form.get('password','')
        if len(username)<3 or not name or len(password)<10:flash('Faculty name, a 3+ character username and a 10+ character password are required.','error')
        else:
            try:
                row=Faculty(username=username,name=name,password_hash=generate_password_hash(password),is_active=True,created_at=now_iso());s.add(row);s.flush();audit_event(s,'faculty_created','faculty',row.id,username);s.commit();flash('Faculty login created.')
            except IntegrityError:s.rollback();flash('That faculty username already exists.','error')
    rows=s.scalars(select(Faculty).order_by(Faculty.username)).all();return render_template('faculty.html',faculty=rows)

@app.route('/admin/faculty/<int:faculty_id>/toggle',methods=['POST'])
@admin_required
def toggle_faculty(faculty_id):
    s=DB();row=s.get(Faculty,faculty_id)
    if row:row.is_active=not row.is_active;audit_event(s,'faculty_enabled' if row.is_active else 'faculty_disabled','faculty',row.id,row.username);s.commit()
    return redirect(url_for('faculty_users'))

@app.route('/admin/audit')
@admin_required
def audit_logs():
    s=DB();rows=s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(300)).all();return render_template('audit.html',rows=rows)

@app.route('/admin/system')
@admin_required
def system_tools(): return render_template('system.html',offline=(APP_MODE=='offline'))

@app.route('/admin/system/backup')
@admin_required
def system_backup():
    if APP_MODE!='offline':abort(400,'Direct database backup is available only in offline mode.')
    db_path=DATA_DIR/'exam.db'
    if not db_path.exists():abort(404)
    tmp=tempfile.NamedTemporaryFile(prefix='lwh_exam_backup_',suffix='.db',delete=False);tmp.close()
    src=sqlite3.connect(str(db_path));dst=sqlite3.connect(tmp.name)
    try:src.backup(dst)
    finally:dst.close();src.close()
    @after_this_request
    def cleanup_backup(response):
        try:os.unlink(tmp.name)
        except OSError:pass
        return response
    stamp=now_dt().strftime('%Y%m%d_%H%M');return send_file(tmp.name,as_attachment=True,download_name=f'LearnWithHemant_Exam_Backup_{stamp}.db',mimetype='application/octet-stream')

@app.route('/admin/system/restore',methods=['POST'])
@admin_required
def system_restore():
    if APP_MODE!='offline':abort(400,'Direct database restore is available only in offline mode.')
    upload=request.files.get('backup_file')
    if not upload or not upload.filename:flash('Choose a .db backup file.','error');return redirect(url_for('system_tools'))
    fd,temp_name=tempfile.mkstemp(prefix='lwh_restore_',suffix='.db'); os.close(fd); temp=Path(temp_name)
    try:
        upload.save(temp)
        conn=sqlite3.connect(str(temp));tables={r[0] for r in conn.execute("select name from sqlite_master where type='table'").fetchall()};conn.close()
        if not {'admins','students','exams','questions','attempts','answers'}.issubset(tables):raise ValueError('This is not a valid Learn with Hemant exam backup.')
        DB.remove();engine.dispose();shutil.copy2(temp,DATA_DIR/'exam.db');init_db();rs=DB();audit_event(rs,'offline_backup_restored','system','',upload.filename or 'backup.db');rs.commit();flash('Backup restored successfully. Refresh the page and verify the data before conducting an exam.')
    except Exception as exc:flash(f'Restore failed: {exc}','error')
    finally:
        try:temp.unlink()
        except OSError:pass
    return redirect(url_for('system_tools'))

@app.route('/student')
@student_required
def student_dashboard():
    s=DB();st=s.get(Student,web_session['user_id']);exams_list=s.scalars(select(Exam).where(Exam.is_active==True).order_by(Exam.id.desc())).all();rows=[]
    for e in exams_list:
        pool_count=s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==e.id)) or 0;cfg=get_exam_config(s,e.id);display_count=min(cfg.question_count,pool_count) if cfg and cfg.question_count else pool_count;att=get_attempt(s,st.id,e.id)
        rows.append(type('StudentExamRow',(),{'id':e.id,'title':e.title,'display_title':student_exam_display_title(s,e),'duration_minutes':e.duration_minutes,'question_count':display_count,'attempt_status':att.status if att else None})())
    return render_template('student_dashboard.html',student=st,exams=rows)

@app.route('/student/exam/<int:exam_id>')
@student_required
def take_exam(exam_id):
    s=DB();exam=s.scalar(select(Exam).where(Exam.id==exam_id,Exam.is_active==True))
    if not exam:flash('Exam is not active.','error');return redirect(url_for('student_dashboard'))
    cfg=get_exam_config(s,exam_id);attempt=get_attempt(s,web_session['user_id'],exam_id)
    if attempt and attempt.status=='submitted':return redirect(url_for('submitted',exam_id=exam_id))
    if not attempt:
        qids=list(s.scalars(select(Question.id).where(Question.exam_id==exam_id).order_by(Question.id)).all())
        if not qids:flash('This exam has no questions.','error');return redirect(url_for('student_dashboard'))
        target=min((cfg.question_count if cfg and cfg.question_count else len(qids)),len(qids))
        if cfg is None or cfg.randomize_questions:qids=random.sample(qids,target)
        else:qids=qids[:target]
        started=now_dt();end=started+timedelta(minutes=exam.duration_minutes);attempt=Attempt(student_id=web_session['user_id'],exam_id=exam_id,started_at=started.isoformat(timespec='seconds'),end_at=end.isoformat(timespec='seconds'),status='in_progress',question_order=','.join(map(str,qids)));s.add(attempt);s.flush()
        for pos,qid in enumerate(qids,1):
            keys=list('ABCD')
            if cfg and cfg.shuffle_options:random.shuffle(keys)
            s.add(AttemptQuestion(attempt_id=attempt.id,question_id=qid,position=pos,option_order=''.join(keys)))
        s.commit()
    end_dt=parse_dt(attempt.end_at)
    if now_dt()>=end_dt:finalize_attempt(s,attempt);return redirect(url_for('submitted',exam_id=exam_id))
    aq_rows=s.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id==attempt.id).order_by(AttemptQuestion.position)).all()
    if not aq_rows:
        qids=[int(x) for x in attempt.question_order.split(',') if x]
        for pos,qid in enumerate(qids,1):s.add(AttemptQuestion(attempt_id=attempt.id,question_id=qid,position=pos,option_order='ABCD'))
        s.commit();aq_rows=s.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id==attempt.id).order_by(AttemptQuestion.position)).all()
    qids=[x.question_id for x in aq_rows];qrows=s.scalars(select(Question).where(Question.id.in_(qids))).all();qmap={q.id:q for q in qrows};views=[]
    for aq in aq_rows:
        q=qmap.get(aq.question_id)
        if not q:continue
        text={'A':q.option_a,'B':q.option_b,'C':q.option_c,'D':q.option_d};display=[(chr(65+i),key,text[key]) for i,key in enumerate(aq.option_order or 'ABCD')]
        views.append(type('QuestionView',(),{'id':q.id,'question':q.question,'display_options':display})())
    saved=s.scalars(select(Answer).where(Answer.attempt_id==attempt.id)).all();answers={a.question_id:a.selected_answer for a in saved}
    return render_template('exam.html',exam=exam,display_title=student_exam_display_title(s,exam),questions=views,answers=answers,end_epoch=end_dt.timestamp(),cfg=cfg)

@app.route('/student/save-answer',methods=['POST'])
@student_required
def save_answer():
    data=request.get_json(silent=True) or {}
    try:exam_id=int(data.get('exam_id'));qid=int(data.get('question_id'))
    except Exception:return jsonify(error='Invalid request'),400
    ans=str(data.get('answer','')).upper()
    if ans not in {'A','B','C','D'}:return jsonify(error='Invalid answer'),400
    s=DB();attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not attempt:return jsonify(error='Attempt not found'),404
    if attempt.status=='submitted':return jsonify(saved=False,submitted=True)
    if now_dt()>=parse_dt(attempt.end_at):finalize_attempt(s,attempt);return jsonify(saved=False,submitted=True)
    if qid not in attempt_question_ids(s,attempt):return jsonify(error='Question not part of this attempt'),400
    save_answer_record(s,attempt.id,qid,ans);s.commit();return jsonify(saved=True)

@app.route('/student/integrity-event',methods=['POST'])
@student_required
def integrity_event():
    data=request.get_json(silent=True) or {}
    try:exam_id=int(data.get('exam_id'))
    except Exception:return jsonify(saved=False),400
    event_type=str(data.get('event_type',''))[:50]
    if event_type not in {'tab_hidden','fullscreen_exit'}:return jsonify(saved=False),400
    s=DB();attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not attempt or attempt.status=='submitted':return jsonify(saved=False),404
    s.add(IntegrityEvent(attempt_id=attempt.id,event_type=event_type,details=str(data.get('details',''))[:250],created_at=now_iso()));s.commit();count=s.scalar(select(func.count()).select_from(IntegrityEvent).where(IntegrityEvent.attempt_id==attempt.id)) or 0;return jsonify(saved=True,count=count)

@app.route('/student/exam/<int:exam_id>/submit',methods=['POST'])
@student_required
def submit_exam(exam_id):
    s=DB();attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not attempt:flash('Attempt not found.','error');return redirect(url_for('student_dashboard'))
    allowed=set(attempt_question_ids(s,attempt))
    if attempt.status!='submitted':
        for key,value in request.form.items():
            if key.startswith('q_') and value in {'A','B','C','D'}:
                try:qid=int(key[2:])
                except ValueError:continue
                if qid in allowed:save_answer_record(s,attempt.id,qid,value)
        s.commit();finalize_attempt(s,attempt)
    return redirect(url_for('submitted',exam_id=exam_id))

@app.route('/student/submitted/<int:exam_id>')
@student_required
def submitted(exam_id):
    s=DB();exam=s.get(Exam,exam_id);attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not exam or not attempt:abort(404)
    if attempt.status!='submitted' and now_dt()>=parse_dt(attempt.end_at):finalize_attempt(s,attempt)
    violations=s.scalar(select(func.count()).select_from(IntegrityEvent).where(IntegrityEvent.attempt_id==attempt.id)) or 0
    percentage,grade,grade_class=result_performance(attempt.score,attempt.total_marks)
    return render_template('submitted.html',exam=exam,display_title=student_exam_display_title(s,exam),attempt=attempt,violations=violations,percentage=percentage,grade=grade,grade_class=grade_class)

@app.errorhandler(400)
def bad_request(e):return render_template('error.html',heading='Invalid or expired request',message=getattr(e,'description','Please refresh the page and try again.')),400
@app.errorhandler(404)
def not_found(e):return render_template('error.html',heading='Page not found',message='The requested exam resource could not be found.'),404

if __name__=='__main__':
    port=int(os.getenv('PORT','8080'))
    try:local_ip=socket.gethostbyname(socket.gethostname())
    except Exception:local_ip='SERVER-IP'
    print('='*64);print(f'LEARN WITH HEMANT — EXAM SYSTEM V{APP_VERSION}');print(f"Mode: {'ONLINE' if APP_MODE=='online' else 'OFFLINE / LAN'}");print(f"Database: {'PostgreSQL' if DATABASE_URL.startswith('postgresql') else 'SQLite'}");print('Server: http://127.0.0.1:%s'%port)
    if APP_MODE=='offline':print(f'LAN URL: http://{local_ip}:{port}')
    print('='*64);app.run(host='0.0.0.0',port=port,debug=False,threaded=True)
