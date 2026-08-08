import os, csv, io, random, socket, secrets, sys
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session as web_session, flash, jsonify, abort, send_file
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, UniqueConstraint, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, scoped_session, sessionmaker, joinedload
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

app=Flask(
    __name__,
    template_folder=str(RESOURCE_DIR/'templates'),
    static_folder=str(RESOURCE_DIR/'static')
)
app.secret_key=secret
cookie_secure=os.getenv('COOKIE_SECURE','1' if APP_MODE=='online' else '0').strip().lower() in {'1','true','yes','on'}
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=cookie_secure,MAX_CONTENT_LENGTH=3*1024*1024)
if APP_MODE=='online': app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1,x_port=1)

engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
DB=scoped_session(sessionmaker(bind=engine,autoflush=False,expire_on_commit=False))

class Base(DeclarativeBase): pass
class Admin(Base):
    __tablename__='admins'; id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); username:Mapped[str]=mapped_column(String,unique=True,nullable=False); password_hash:Mapped[str]=mapped_column(String,nullable=False)
class Student(Base):
    __tablename__='students'; id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); roll_no:Mapped[str]=mapped_column(String,unique=True,nullable=False); name:Mapped[str]=mapped_column(String,nullable=False); password_hash:Mapped[str]=mapped_column(String,nullable=False); created_at:Mapped[str]=mapped_column(String,nullable=False)
class Exam(Base):
    __tablename__='exams'; id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); title:Mapped[str]=mapped_column(String,nullable=False); duration_minutes:Mapped[int]=mapped_column(Integer,nullable=False); is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False); created_at:Mapped[str]=mapped_column(String,nullable=False)
class Question(Base):
    __tablename__='questions'; id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False); question:Mapped[str]=mapped_column(String,nullable=False); option_a:Mapped[str]=mapped_column(String,nullable=False); option_b:Mapped[str]=mapped_column(String,nullable=False); option_c:Mapped[str]=mapped_column(String,nullable=False); option_d:Mapped[str]=mapped_column(String,nullable=False); correct_answer:Mapped[str]=mapped_column(String(1),nullable=False); marks:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
class Attempt(Base):
    __tablename__='attempts'; __table_args__=(UniqueConstraint('student_id','exam_id'),); id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); student_id:Mapped[int]=mapped_column(ForeignKey('students.id'),nullable=False); exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False); started_at:Mapped[str]=mapped_column(String,nullable=False); end_at:Mapped[str]=mapped_column(String,nullable=False); submitted_at:Mapped[str|None]=mapped_column(String,nullable=True); status:Mapped[str]=mapped_column(String,nullable=False,default='in_progress'); score:Mapped[int|None]=mapped_column(Integer,nullable=True); total_marks:Mapped[int|None]=mapped_column(Integer,nullable=True); question_order:Mapped[str]=mapped_column(String,nullable=False)
class Answer(Base):
    __tablename__='answers'; __table_args__=(UniqueConstraint('attempt_id','question_id'),); id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); attempt_id:Mapped[int]=mapped_column(ForeignKey('attempts.id'),nullable=False); question_id:Mapped[int]=mapped_column(ForeignKey('questions.id'),nullable=False); selected_answer:Mapped[str|None]=mapped_column(String(1),nullable=True); saved_at:Mapped[str]=mapped_column(String,nullable=False)

def now_dt(): return datetime.now().astimezone()
def now_iso(): return now_dt().isoformat(timespec='seconds')
def parse_dt(value): return datetime.fromisoformat(value)

def init_db():
    Base.metadata.create_all(engine)
    s=DB()
    try:
        # Online deployments intentionally sync the configured administrator password.
        # Source-based offline development keeps the historical default behavior.
        # The packaged V2.02 desktop build uses first-run setup instead, so no default
        # administrator credential is shipped inside the downloadable executable.
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
        if not supplied or not secrets.compare_digest(str(supplied),str(web_session.get('_csrf_token',''))): abort(400,'Security token validation failed. Refresh the page and try again.')

@app.context_processor
def globals_for_templates():
    return {
        'csrf_token':web_session.get('_csrf_token',''),
        'web_session':web_session,
        'is_online':APP_MODE=='online',
        'app_version':APP_VERSION
    }


@app.before_request
def offline_first_run_guard():
    if not needs_offline_setup():
        return None
    allowed={'setup_admin','static','health'}
    if request.endpoint not in allowed:
        return redirect(url_for('setup_admin'))
    return None

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options','nosniff')
    response.headers.setdefault('X-Frame-Options','DENY')
    response.headers.setdefault('Referrer-Policy','same-origin')
    response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    return response

@app.route('/setup',methods=['GET','POST'])
def setup_admin():
    if not needs_offline_setup():
        return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form.get('username','').strip()
        password=request.form.get('password','')
        confirm=request.form.get('confirm_password','')
        if len(username)<3:
            flash('Administrator username must contain at least 3 characters.','error')
        elif len(password)<10:
            flash('Administrator password must contain at least 10 characters.','error')
        elif password!=confirm:
            flash('Passwords do not match.','error')
        else:
            s=DB()
            try:
                s.add(Admin(username=username,password_hash=generate_password_hash(password)))
                s.commit()
                flash('Administrator account created. You can now sign in.')
                return redirect(url_for('home'))
            except IntegrityError:
                s.rollback()
                flash('That administrator username is already in use.','error')
    return render_template('setup.html',login_page=True)

@app.route('/download/offline')
def offline_download():
    if APP_MODE!='online':
        return redirect(url_for('home'))
    parsed=urlparse(OFFLINE_DOWNLOAD_URL)
    if parsed.scheme not in {'https','http'} or not parsed.netloc:
        abort(503,'Offline download is temporarily unavailable.')
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

def student_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if web_session.get('role')!='student': return redirect(url_for('home'))
        return fn(*a,**kw)
    return inner

def get_attempt(s,student_id,exam_id): return s.scalar(select(Attempt).where(Attempt.student_id==student_id,Attempt.exam_id==exam_id))

def save_answer_record(s,attempt_id,question_id,answer):
    row=s.scalar(select(Answer).where(Answer.attempt_id==attempt_id,Answer.question_id==question_id))
    if row: row.selected_answer=answer; row.saved_at=now_iso()
    else: s.add(Answer(attempt_id=attempt_id,question_id=question_id,selected_answer=answer,saved_at=now_iso()))

def finalize_attempt(s,attempt):
    if attempt.status=='submitted': return attempt
    questions=s.scalars(select(Question).where(Question.exam_id==attempt.exam_id)).all()
    saved=s.scalars(select(Answer).where(Answer.attempt_id==attempt.id)).all(); amap={a.question_id:a.selected_answer for a in saved}
    attempt.score=sum(q.marks for q in questions if amap.get(q.id)==q.correct_answer)
    attempt.total_marks=sum(q.marks for q in questions); attempt.status='submitted'; attempt.submitted_at=now_iso(); s.commit(); return attempt

@app.route('/',methods=['GET','POST'])
def home():
    if web_session.get('role')=='admin': return redirect(url_for('admin_dashboard'))
    if web_session.get('role')=='student': return redirect(url_for('student_dashboard'))
    if request.method=='POST':
        s=DB(); typ=request.form.get('login_type')
        if typ=='admin':
            row=s.scalar(select(Admin).where(Admin.username==request.form.get('username','').strip()))
            if row and check_password_hash(row.password_hash,request.form.get('password','')):
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role='admin',user_id=row.id); return redirect(url_for('admin_dashboard'))
        else:
            row=s.scalar(select(Student).where(Student.roll_no==request.form.get('roll_no','').strip()))
            if row and check_password_hash(row.password_hash,request.form.get('password','')):
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role='student',user_id=row.id); return redirect(url_for('student_dashboard'))
        flash('Invalid login credentials.','error')
    return render_template('login.html',login_page=True)

@app.route('/logout')
def logout():
    web_session.clear(); return redirect(url_for('home'))

@app.route('/health')
def health():
    try:
        s=DB(); s.execute(select(1)); return jsonify(status='ok',mode=APP_MODE,database='postgresql' if DATABASE_URL.startswith('postgresql') else 'sqlite')
    except Exception as e: return jsonify(status='error'),503

@app.route('/admin')
@admin_required
def admin_dashboard():
    s=DB(); stats={'students':s.scalar(select(func.count()).select_from(Student)),'exams':s.scalar(select(func.count()).select_from(Exam)),'questions':s.scalar(select(func.count()).select_from(Question)),'attempts':s.scalar(select(func.count()).select_from(Attempt))}; return render_template('admin_dashboard.html',stats=stats)

@app.route('/admin/students',methods=['GET','POST'])
@admin_required
def students():
    s=DB()
    if request.method=='POST':
        roll=request.form.get('roll_no','').strip(); name=request.form.get('name','').strip(); pw=request.form.get('password','')
        if not roll or not name or not pw: flash('All student fields are required.','error')
        else:
            try:s.add(Student(roll_no=roll,name=name,password_hash=generate_password_hash(pw),created_at=now_iso()));s.commit();flash('Student added.')
            except IntegrityError:s.rollback();flash('Roll number already exists.','error')
    rows=s.scalars(select(Student).order_by(Student.roll_no)).all();return render_template('students.html',students=rows)


def _student_cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _canonical_student_header(value):
    key=_student_cell_text(value).lower().replace('-', '_').replace(' ', '_')
    while '__' in key:
        key=key.replace('__','_')
    aliases={
        'roll':'roll_no','rollno':'roll_no','roll_number':'roll_no','student_id':'roll_no',
        'registration_no':'roll_no','registration_number':'roll_no','enrollment_no':'roll_no','enrollment_number':'roll_no',
        'student_name':'name','full_name':'name','candidate_name':'name',
        'pass':'password','login_password':'password','student_password':'password'
    }
    return aliases.get(key,key)


def _student_rows_from_upload(upload):
    filename=(upload.filename or '').lower()
    raw=upload.read()
    if not raw:
        raise ValueError('The uploaded file is empty.')

    if filename.endswith('.csv'):
        try:
            text=raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('CSV must be UTF-8 encoded.') from exc
        reader=csv.reader(io.StringIO(text))
        all_rows=list(reader)
    elif filename.endswith('.xlsx'):
        try:
            wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            ws=wb.active
            all_rows=[list(r) for r in ws.iter_rows(values_only=True)]
        except Exception as exc:
            raise ValueError('The Excel file could not be read. Please upload a valid .xlsx file.') from exc
    else:
        raise ValueError('Please upload a CSV or Excel (.xlsx) file.')

    if not all_rows:
        raise ValueError('The uploaded file has no rows.')

    headers=[_canonical_student_header(v) for v in all_rows[0]]
    required={'roll_no','name','password'}
    if not required.issubset(set(headers)):
        raise ValueError('Required columns are: roll_no, name, password.')

    index={name:headers.index(name) for name in required}
    rows=[]
    for row_number,row in enumerate(all_rows[1:],start=2):
        values={}
        for key,col in index.items():
            values[key]=_student_cell_text(row[col] if col < len(row) else '')
        if not any(values.values()):
            continue
        values['row_number']=row_number
        rows.append(values)
    return rows


@app.route('/admin/students/import',methods=['POST'])
@admin_required
def import_students():
    upload=request.files.get('student_file')
    if not upload or not upload.filename:
        flash('Choose a CSV or Excel (.xlsx) file.','error')
        return redirect(url_for('students'))

    try:
        rows=_student_rows_from_upload(upload)
    except ValueError as exc:
        flash(str(exc),'error')
        return redirect(url_for('students'))

    s=DB()
    existing=set(s.scalars(select(Student.roll_no)).all())
    seen=set()
    added=0
    duplicates=0
    invalid=0

    for row in rows:
        roll=row['roll_no'].strip()
        name=row['name'].strip()
        password=row['password']
        if not roll or not name or not password:
            invalid+=1
            continue
        if roll in existing or roll in seen:
            duplicates+=1
            continue
        s.add(Student(
            roll_no=roll,
            name=name,
            password_hash=generate_password_hash(password),
            created_at=now_iso()
        ))
        seen.add(roll)
        added+=1

    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        flash('Import could not be completed because one or more roll numbers conflict with existing students.','error')
        return redirect(url_for('students'))

    parts=[f'Imported {added} student login' + ('' if added==1 else 's') + '.']
    if duplicates: parts.append(f'Skipped {duplicates} duplicate roll number' + ('' if duplicates==1 else 's') + '.')
    if invalid: parts.append(f'Skipped {invalid} incomplete row' + ('' if invalid==1 else 's') + '.')
    flash(' '.join(parts))
    return redirect(url_for('students'))


@app.route('/admin/students/template/<fmt>')
@admin_required
def student_import_template(fmt):
    headers=['roll_no','name','password']
    if fmt=='csv':
        out=io.StringIO(newline='')
        writer=csv.writer(out)
        writer.writerow(headers)
        data=io.BytesIO(out.getvalue().encode('utf-8-sig'))
        return send_file(data,mimetype='text/csv',as_attachment=True,download_name='student_import_template.csv')
    if fmt=='xlsx':
        wb=Workbook()
        ws=wb.active
        ws.title='Students'
        ws.append(headers)
        for cell in ws[1]: cell.font=Font(bold=True)
        ws.column_dimensions['A'].width=18
        ws.column_dimensions['B'].width=28
        ws.column_dimensions['C'].width=22
        data=io.BytesIO(); wb.save(data); data.seek(0)
        return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='student_import_template.xlsx')
    abort(404)


@app.route('/admin/exams',methods=['GET','POST'])
@admin_required
def exams():
    s=DB()
    if request.method=='POST':
        try: duration=max(1,int(request.form.get('duration','30')))
        except ValueError: duration=30
        title=request.form.get('title','').strip()
        if title:s.add(Exam(title=title,duration_minutes=duration,is_active=False,created_at=now_iso()));s.commit();flash('Exam created.')
    raw=s.execute(select(Exam,func.count(Question.id)).outerjoin(Question,Question.exam_id==Exam.id).group_by(Exam.id).order_by(Exam.id.desc())).all(); rows=[]
    for e,count in raw:
        rows.append(type('ExamRow',(),{'id':e.id,'title':e.title,'duration_minutes':e.duration_minutes,'is_active':e.is_active,'question_count':count})())
    return render_template('exams.html',exams=rows)

@app.route('/admin/exam/<int:exam_id>/toggle',methods=['POST'])
@admin_required
def toggle_exam(exam_id):
    s=DB(); e=s.get(Exam,exam_id)
    if e:e.is_active=not bool(e.is_active);s.commit()
    return redirect(url_for('exams'))

@app.route('/admin/exam/<int:exam_id>/questions',methods=['GET','POST'])
@admin_required
def questions(exam_id):
    s=DB(); exam=s.get(Exam,exam_id)
    if not exam: abort(404)
    if request.method=='POST':
        try: marks=max(1,int(request.form.get('marks','1')))
        except ValueError: marks=1
        ans=request.form.get('correct_answer','A').upper()
        if ans not in {'A','B','C','D'}: ans='A'
        s.add(Question(exam_id=exam_id,question=request.form.get('question','').strip(),option_a=request.form.get('option_a','').strip(),option_b=request.form.get('option_b','').strip(),option_c=request.form.get('option_c','').strip(),option_d=request.form.get('option_d','').strip(),correct_answer=ans,marks=marks));s.commit();flash('Question added.')
    qs=s.scalars(select(Question).where(Question.exam_id==exam_id).order_by(Question.id)).all();return render_template('questions.html',exam=exam,questions=qs)

@app.route('/admin/exam/<int:exam_id>/import',methods=['POST'])
@admin_required
def import_questions(exam_id):
    f=request.files.get('csv_file')
    if not f: flash('Choose a CSV file.','error');return redirect(url_for('questions',exam_id=exam_id))
    try:text=f.stream.read().decode('utf-8-sig')
    except UnicodeDecodeError: flash('CSV must be UTF-8 encoded.','error');return redirect(url_for('questions',exam_id=exam_id))
    reader=csv.DictReader(io.StringIO(text)); required={'question','option_a','option_b','option_c','option_d','correct_answer','marks'}
    if not required.issubset(set(reader.fieldnames or [])): flash('CSV columns are incorrect. Use sample_questions.csv.','error');return redirect(url_for('questions',exam_id=exam_id))
    s=DB(); count=0
    for r in reader:
        ans=(r.get('correct_answer') or '').strip().upper()
        if ans not in {'A','B','C','D'}: continue
        try:marks=max(1,int(r.get('marks') or 1))
        except ValueError:marks=1
        if not (r.get('question') or '').strip():continue
        s.add(Question(exam_id=exam_id,question=r['question'].strip(),option_a=(r.get('option_a') or '').strip(),option_b=(r.get('option_b') or '').strip(),option_c=(r.get('option_c') or '').strip(),option_d=(r.get('option_d') or '').strip(),correct_answer=ans,marks=marks));count+=1
    s.commit();flash(f'Imported {count} questions.');return redirect(url_for('questions',exam_id=exam_id))

@app.route('/admin/results')
@admin_required
def results():
    s=DB(); raw=s.execute(select(Attempt,Student,Exam).join(Student,Student.id==Attempt.student_id).join(Exam,Exam.id==Attempt.exam_id).order_by(Attempt.id.desc())).all();rows=[]
    for a,st,e in raw:
        rows.append(type('ResultRow',(),{'roll_no':st.roll_no,'name':st.name,'title':e.title,'status':a.status,'score':a.score,'total_marks':a.total_marks,'started_at':a.started_at,'submitted_at':a.submitted_at})())
    return render_template('results.html',rows=rows)

@app.route('/student')
@student_required
def student_dashboard():
    s=DB(); st=s.get(Student,web_session['user_id']); exams_list=s.scalars(select(Exam).where(Exam.is_active==True).order_by(Exam.id.desc())).all(); rows=[]
    for e in exams_list:
        count=s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==e.id)); att=get_attempt(s,st.id,e.id)
        rows.append(type('StudentExamRow',(),{'id':e.id,'title':e.title,'duration_minutes':e.duration_minutes,'question_count':count,'attempt_status':att.status if att else None})())
    return render_template('student_dashboard.html',student=st,exams=rows)

@app.route('/student/exam/<int:exam_id>')
@student_required
def take_exam(exam_id):
    s=DB(); exam=s.scalar(select(Exam).where(Exam.id==exam_id,Exam.is_active==True))
    if not exam: flash('Exam is not active.','error');return redirect(url_for('student_dashboard'))
    attempt=get_attempt(s,web_session['user_id'],exam_id)
    if attempt and attempt.status=='submitted':return redirect(url_for('submitted',exam_id=exam_id))
    if not attempt:
        qids=list(s.scalars(select(Question.id).where(Question.exam_id==exam_id)).all())
        if not qids: flash('This exam has no questions.','error');return redirect(url_for('student_dashboard'))
        random.shuffle(qids); started=now_dt(); end=started+timedelta(minutes=exam.duration_minutes); attempt=Attempt(student_id=web_session['user_id'],exam_id=exam_id,started_at=started.isoformat(timespec='seconds'),end_at=end.isoformat(timespec='seconds'),status='in_progress',question_order=','.join(map(str,qids)));s.add(attempt);s.commit()
    end_dt=parse_dt(attempt.end_at)
    if now_dt()>=end_dt: finalize_attempt(s,attempt);return redirect(url_for('submitted',exam_id=exam_id))
    qids=[int(x) for x in attempt.question_order.split(',') if x]; qrows=s.scalars(select(Question).where(Question.id.in_(qids))).all();qmap={q.id:q for q in qrows};ordered=[qmap[i] for i in qids if i in qmap]; saved=s.scalars(select(Answer).where(Answer.attempt_id==attempt.id)).all();answers={a.question_id:a.selected_answer for a in saved};return render_template('exam.html',exam=exam,questions=ordered,answers=answers,end_epoch=end_dt.timestamp())

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
    if not s.scalar(select(Question.id).where(Question.id==qid,Question.exam_id==exam_id)):return jsonify(error='Question not part of exam'),400
    save_answer_record(s,attempt.id,qid,ans);s.commit();return jsonify(saved=True)

@app.route('/student/exam/<int:exam_id>/submit',methods=['POST'])
@student_required
def submit_exam(exam_id):
    s=DB();attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not attempt:flash('Attempt not found.','error');return redirect(url_for('student_dashboard'))
    if attempt.status!='submitted':
        for key,value in request.form.items():
            if key.startswith('q_') and value in {'A','B','C','D'}:
                try:qid=int(key[2:])
                except ValueError:continue
                if s.scalar(select(Question.id).where(Question.id==qid,Question.exam_id==exam_id)):save_answer_record(s,attempt.id,qid,value)
        s.commit();finalize_attempt(s,attempt)
    return redirect(url_for('submitted',exam_id=exam_id))

@app.route('/student/submitted/<int:exam_id>')
@student_required
def submitted(exam_id):
    s=DB();exam=s.get(Exam,exam_id);attempt=get_attempt(s,web_session['user_id'],exam_id)
    if not exam or not attempt:abort(404)
    if attempt.status!='submitted' and now_dt()>=parse_dt(attempt.end_at):finalize_attempt(s,attempt)
    return render_template('submitted.html',exam=exam,attempt=attempt)

@app.errorhandler(400)
def bad_request(e): return render_template('error.html',heading='Invalid or expired request',message=getattr(e,'description','Please refresh the page and try again.')),400
@app.errorhandler(404)
def not_found(e): return render_template('error.html',heading='Page not found',message='The requested exam resource could not be found.'),404

if __name__=='__main__':
    port=int(os.getenv('PORT','8080'))
    try:local_ip=socket.gethostbyname(socket.gethostname())
    except Exception:local_ip='SERVER-IP'
    print('='*64);print(f'LEARN WITH HEMANT — EXAM SYSTEM V{APP_VERSION}');print(f"Mode: {'ONLINE' if APP_MODE=='online' else 'OFFLINE / LAN'}");print(f"Database: {'PostgreSQL' if DATABASE_URL.startswith('postgresql') else 'SQLite'}");print('Server: http://127.0.0.1:%s'%port)
    if APP_MODE=='offline':print(f'LAN URL: http://{local_ip}:{port}')
    print('='*64);app.run(host='0.0.0.0',port=port,debug=False,threaded=True)
