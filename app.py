import os, csv, io, random, socket, secrets, sys, json, math, sqlite3, tempfile, shutil, base64, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session as web_session, flash, jsonify, abort, send_file, after_this_request
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, UniqueConstraint, Text, select, func, or_, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker
from sqlalchemy.exc import IntegrityError
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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
SESSION_TIMEOUT_MINUTES=max(10,int(os.getenv('SESSION_TIMEOUT_MINUTES','45')))
BACKUP_KDF_ITERATIONS=max(100000,int(os.getenv('BACKUP_KDF_ITERATIONS','390000')))

# All user-facing dates/times use an explicit timezone so cloud hosts such as
# Render (which commonly run in UTC) and offline Windows builds show the same time.
APP_TIMEZONE=os.getenv('APP_TIMEZONE','Asia/Kolkata').strip() or 'Asia/Kolkata'
try:
    DISPLAY_TZ=ZoneInfo(APP_TIMEZONE)
except Exception:
    # Safe fallback for Indian deployments if the configured zone is unavailable.
    DISPLAY_TZ=timezone(timedelta(hours=5,minutes=30))

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
# SUPER_ADMIN_USERNAME is the preferred setting. ADMIN_USERNAME remains supported
# for backwards compatibility with existing deployments.
super_admin_username=(os.getenv('SUPER_ADMIN_USERNAME') or os.getenv('ADMIN_USERNAME') or 'admin').strip() or 'admin'
legacy_admin_username=os.getenv('LEGACY_ADMIN_USERNAME','admin').strip() or 'admin'
# Existing deployments already use ADMIN_PASSWORD, so keep it as the fallback.
# SUPER_ADMIN_PASSWORD may be set later if a separate secret is preferred.
admin_password=(os.getenv('SUPER_ADMIN_PASSWORD') or os.getenv('ADMIN_PASSWORD') or '').strip()
# Compatibility alias used by older helper code.
admin_username=super_admin_username
if APP_MODE=='online':
    if len(secret)<24: raise RuntimeError('Online mode requires a strong SECRET_KEY (24+ characters).')
    if len(admin_password)<10: raise RuntimeError('Online mode requires SUPER_ADMIN_PASSWORD or ADMIN_PASSWORD with at least 10 characters.')
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

class SubjectCatalog(Base):
    __tablename__='subject_catalog'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    name:Mapped[str]=mapped_column(String,unique=True,nullable=False)
    category:Mapped[str]=mapped_column(String,nullable=False,default='Custom / Other')
    course_semester:Mapped[str]=mapped_column(String,nullable=False,default='')
    is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_by:Mapped[str]=mapped_column(String,nullable=False,default='system')
    created_at:Mapped[str]=mapped_column(String,nullable=False)

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

class InstitutionProfile(Base):
    __tablename__='institution_profile'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    institution_name:Mapped[str]=mapped_column(String,nullable=False,default='Learn with Hemant')
    short_name:Mapped[str]=mapped_column(String,nullable=False,default='Learn with Hemant')
    system_name:Mapped[str]=mapped_column(String,nullable=False,default='Exam System')
    department:Mapped[str]=mapped_column(String,nullable=False,default='')
    academic_year:Mapped[str]=mapped_column(String,nullable=False,default='')
    admin_email:Mapped[str]=mapped_column(String,nullable=False,default='')
    exam_controller:Mapped[str]=mapped_column(String,nullable=False,default='')
    contact_phone:Mapped[str]=mapped_column(String,nullable=False,default='')
    logo_data:Mapped[str]=mapped_column(Text,nullable=False,default='')
    updated_at:Mapped[str]=mapped_column(String,nullable=False)

class FacultyRole(Base):
    __tablename__='faculty_roles'
    __table_args__=(UniqueConstraint('faculty_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    faculty_id:Mapped[int]=mapped_column(ForeignKey('faculty_users.id'),nullable=False)
    role:Mapped[str]=mapped_column(String,nullable=False,default='faculty')
    department:Mapped[str]=mapped_column(String,nullable=False,default='')
    updated_at:Mapped[str]=mapped_column(String,nullable=False)

class AcademicGroup(Base):
    __tablename__='academic_groups'
    __table_args__=(UniqueConstraint('department','program','semester','section','academic_year'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    department:Mapped[str]=mapped_column(String,nullable=False,default='')
    program:Mapped[str]=mapped_column(String,nullable=False)
    semester:Mapped[str]=mapped_column(String,nullable=False)
    section:Mapped[str]=mapped_column(String,nullable=False)
    academic_year:Mapped[str]=mapped_column(String,nullable=False,default='')
    is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class StudentGroup(Base):
    __tablename__='student_groups'
    __table_args__=(UniqueConstraint('student_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    student_id:Mapped[int]=mapped_column(ForeignKey('students.id'),nullable=False)
    group_id:Mapped[int]=mapped_column(ForeignKey('academic_groups.id'),nullable=False)
    assigned_at:Mapped[str]=mapped_column(String,nullable=False)

class ExamSession(Base):
    __tablename__='exam_sessions'
    __table_args__=(UniqueConstraint('exam_id','group_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    group_id:Mapped[int]=mapped_column(ForeignKey('academic_groups.id'),nullable=False)
    scheduled_start:Mapped[str]=mapped_column(String,nullable=False,default='')
    scheduled_end:Mapped[str]=mapped_column(String,nullable=False,default='')
    venue:Mapped[str]=mapped_column(String,nullable=False,default='')
    created_at:Mapped[str]=mapped_column(String,nullable=False)

class ExamApproval(Base):
    __tablename__='exam_approvals'
    __table_args__=(UniqueConstraint('exam_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id'),nullable=False)
    status:Mapped[str]=mapped_column(String,nullable=False,default='draft')
    requested_by:Mapped[str]=mapped_column(String,nullable=False,default='')
    requested_at:Mapped[str]=mapped_column(String,nullable=False,default='')
    reviewed_by:Mapped[str]=mapped_column(String,nullable=False,default='')
    reviewed_at:Mapped[str]=mapped_column(String,nullable=False,default='')
    comments:Mapped[str]=mapped_column(String,nullable=False,default='')


def now_dt():
    """Current application time in the configured institutional timezone."""
    return datetime.now(DISPLAY_TZ)

def now_iso():
    return now_dt().isoformat(timespec='seconds')

def parse_dt(value):
    """Parse stored timestamps and attach the configured timezone to legacy naive values."""
    dt=datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=DISPLAY_TZ)

def display_dt(value):
    """Convert any stored timestamp (UTC/local/legacy) to the display timezone."""
    return parse_dt(value).astimezone(DISPLAY_TZ)

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

ROLE_LABELS={'super_admin':'Super Admin','exam_controller':'Exam Controller','hod':'HOD','faculty':'Faculty'}
APPROVER_ROLES={'super_admin','exam_controller','hod'}


def get_institution(s=None,create=True):
    s=s or DB()
    row=s.scalar(select(InstitutionProfile).order_by(InstitutionProfile.id.asc()))
    if not row and create:
        row=InstitutionProfile(institution_name='Learn with Hemant',short_name='Learn with Hemant',system_name='Exam System',department='',academic_year='',admin_email='',exam_controller='',contact_phone='',logo_data='',updated_at=now_iso())
        s.add(row);s.flush()
    return row


def current_staff_role(s=None):
    if web_session.get('role')=='admin': return 'super_admin'
    if web_session.get('role')!='faculty': return web_session.get('role','')
    s=s or DB(); uid=web_session.get('user_id')
    row=s.scalar(select(FacultyRole).where(FacultyRole.faculty_id==uid)) if uid else None
    return row.role if row and row.role in ROLE_LABELS else 'faculty'


def can_approve_exams(s=None): return current_staff_role(s) in APPROVER_ROLES

def can_approve_content(s=None): return current_staff_role(s) in APPROVER_ROLES

def can_manage_staff_passwords(s=None):
    """Super Admin can reset any staff password; HOD can reset Faculty passwords only."""
    return current_staff_role(s) in {'super_admin','hod'}


def get_exam_approval(s,exam_id,create=True):
    row=s.scalar(select(ExamApproval).where(ExamApproval.exam_id==exam_id))
    if not row and create:
        row=ExamApproval(exam_id=exam_id,status='draft',requested_by='',requested_at='',reviewed_by='',reviewed_at='',comments='')
        s.add(row);s.flush()
    return row


def group_label(group):
    if not group:return 'Unassigned'
    bits=[group.program]
    if group.semester:bits.append(f'Sem {group.semester}')
    if group.section:bits.append(f'Section {group.section}')
    label=' · '.join(bits)
    return f'{label} ({group.academic_year})' if group.academic_year else label


def student_group(s,student_id):
    return s.execute(select(AcademicGroup).join(StudentGroup,StudentGroup.group_id==AcademicGroup.id).where(StudentGroup.student_id==student_id)).scalar_one_or_none()


def find_or_create_group(s,department,program,semester,section,academic_year):
    department=(department or '').strip();program=(program or '').strip();semester=(semester or '').strip();section=(section or '').strip();academic_year=(academic_year or '').strip()
    if not program or not semester or not section:return None
    row=s.scalar(select(AcademicGroup).where(AcademicGroup.department==department,AcademicGroup.program==program,AcademicGroup.semester==semester,AcademicGroup.section==section,AcademicGroup.academic_year==academic_year))
    if not row:
        row=AcademicGroup(department=department,program=program,semester=semester,section=section,academic_year=academic_year,is_active=True,created_at=now_iso());s.add(row);s.flush()
    return row


def assign_student_group(s,student_id,group_id):
    row=s.scalar(select(StudentGroup).where(StudentGroup.student_id==student_id))
    if group_id:
        if row:row.group_id=group_id;row.assigned_at=now_iso()
        else:s.add(StudentGroup(student_id=student_id,group_id=group_id,assigned_at=now_iso()))
    elif row:s.delete(row)


def parse_local_schedule(value):
    value=(value or '').strip()
    if not value:return ''
    try:return datetime.fromisoformat(value).strftime('%Y-%m-%dT%H:%M:%S')
    except ValueError:raise ValueError('Schedule date/time is invalid.')


def exam_access_for_student(s,student_id,exam):
    sessions=s.scalars(select(ExamSession).where(ExamSession.exam_id==exam.id)).all()
    if not sessions:return True,'Available',None
    membership=s.scalar(select(StudentGroup).where(StudentGroup.student_id==student_id))
    if not membership:return False,'Not assigned to your batch/section',None
    matched=next((x for x in sessions if x.group_id==membership.group_id),None)
    if not matched:return False,'Not assigned to your batch/section',None
    now=now_dt().replace(tzinfo=None)
    if matched.scheduled_start:
        start=datetime.fromisoformat(matched.scheduled_start)
        if now<start:return False,f'Scheduled for {start.strftime("%d %b, %I:%M %p")}',matched
    if matched.scheduled_end:
        end=datetime.fromisoformat(matched.scheduled_end)
        if now>end:return False,'Exam window closed',matched
    return True,'Available',matched


def local_lan_ip():
    """Return the IPv4 address used by the machine's current default LAN route.

    The UDP connect does not send application data; it asks the OS which local
    interface would be used for that route. This keeps the Exam Centre URL in
    sync when the server laptop moves between Wi-Fi/LAN/hotspot networks.
    """
    probes=(('8.8.8.8',80),('1.1.1.1',80),('192.0.2.1',80))
    for host,port in probes:
        sock=None
        try:
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            sock.connect((host,port))
            ip=sock.getsockname()[0]
            if ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                return ip
        except OSError:
            pass
        finally:
            if sock:
                try:sock.close()
                except OSError:pass
    try:
        candidates=[]
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET,socket.SOCK_DGRAM):
            ip=info[4][0]
            if ip and not ip.startswith('127.') and not ip.startswith('169.254.') and ip not in candidates:
                candidates.append(ip)
        private=next((ip for ip in candidates if ip.startswith('10.') or ip.startswith('192.168.') or (ip.startswith('172.') and 16<=int(ip.split('.')[1])<=31)),None)
        return private or (candidates[0] if candidates else 'SERVER-IP')
    except Exception:
        return 'SERVER-IP'


def qr_data_uri(text):
    img=qrcode.make(text);buf=io.BytesIO();img.save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')


def backup_key(password,salt):
    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=BACKUP_KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))


def encrypt_backup_bytes(raw,password):
    salt=os.urandom(16);token=Fernet(backup_key(password,salt)).encrypt(raw)
    return b'LWHBK1'+salt+token


def decrypt_backup_bytes(raw,password):
    if not raw.startswith(b'LWHBK1') or len(raw)<23:raise ValueError('This is not a valid encrypted Learn with Hemant backup.')
    salt=raw[6:22]
    try:return Fernet(backup_key(password,salt)).decrypt(raw[22:])
    except InvalidToken as exc:raise ValueError('Backup password is incorrect or the backup is damaged.') from exc

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
    ensure_subject_catalog_entry(s,pack.get('subject',''),pack.get('category','Engineering'),pack.get('course_semester',''),'preloaded-library')
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

def ensure_subject_catalog_entry(s,name,category='Custom / Other',course_semester='',created_by='system',reactivate=True):
    name=(name or '').strip()
    if not name:
        return None
    category=(category or '').strip() or 'Custom / Other'
    course_semester=(course_semester or '').strip()
    row=s.scalar(select(SubjectCatalog).where(func.lower(SubjectCatalog.name)==name.lower()))
    if row:
        # Preserve a faculty-defined category, but upgrade generic placeholders when better metadata arrives.
        if (not row.category or row.category in {'Custom / Other','Imported / Other','General'}) and category not in {'Custom / Other','Imported / Other','General'}:
            row.category=category
        if not row.course_semester and course_semester:
            row.course_semester=course_semester
        if reactivate:
            row.is_active=True
        return row
    row=SubjectCatalog(name=name,category=category,course_semester=course_semester,is_active=True,created_by=created_by or 'system',created_at=now_iso())
    s.add(row)
    return row

def seed_subject_catalog(s):
    # Register all bundled subjects so the faculty form can use a categorized subject selector immediately.
    for pack in load_preloaded_question_banks().values():
        ensure_subject_catalog_entry(s,pack.get('subject',''),pack.get('category','Engineering'),pack.get('course_semester',''),'preloaded-library',False)
    # Preserve subjects already present in older databases even if they were created before this feature existed.
    for subject,course in s.execute(select(BankQuestion.subject,BankQuestion.course_semester).distinct()).all():
        ensure_subject_catalog_entry(s,subject,'Custom / Other',course,'legacy-question-bank',False)
    s.flush()

def subject_catalog_groups(s,include_inactive=False):
    stmt=select(SubjectCatalog)
    if not include_inactive:
        stmt=stmt.where(SubjectCatalog.is_active==True)
    rows=s.scalars(stmt.order_by(SubjectCatalog.category,SubjectCatalog.name)).all()
    grouped=[]
    current=None
    for row in rows:
        if current is None or current['category']!=row.category:
            current={'category':row.category,'subjects':[]}
            grouped.append(current)
        current['subjects'].append(row)
    return grouped

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

def ensure_super_admin_identity(s):
    """Ensure one configured Super Admin login and optionally demote legacy ``admin``.

    When SUPER_ADMIN_USERNAME differs from LEGACY_ADMIN_USERNAME (``admin`` by
    default), the old Admin record is converted into an ordinary Faculty account
    using the *same password hash*. This preserves the legacy username/password
    while moving Super Admin authority to the newly configured username.
    """
    super_admin=s.scalar(select(Admin).where(Admin.username==super_admin_username))
    if not super_admin:
        super_admin=Admin(username=super_admin_username,password_hash=generate_password_hash(admin_password))
        s.add(super_admin)
        s.flush()
    elif admin_password and not check_password_hash(super_admin.password_hash,admin_password):
        super_admin.password_hash=generate_password_hash(admin_password)

    if legacy_admin_username==super_admin_username:
        return

    legacy=s.scalar(select(Admin).where(Admin.username==legacy_admin_username))
    if not legacy:
        return

    faculty=s.scalar(select(Faculty).where(Faculty.username==legacy_admin_username))
    if faculty:
        # The legacy Admin identity wins if the same username already exists in
        # faculty_users, because the user's requirement is to preserve the old
        # Admin credentials while changing only its role.
        faculty.password_hash=legacy.password_hash
        faculty.is_active=True
    else:
        faculty=Faculty(
            username=legacy.username,
            name=legacy.username.replace('.', ' ').replace('_', ' ').strip().title() or 'Faculty',
            password_hash=legacy.password_hash,
            is_active=True,
            created_at=now_iso(),
        )
        s.add(faculty)
        s.flush()

    role_row=s.scalar(select(FacultyRole).where(FacultyRole.faculty_id==faculty.id))
    if role_row:
        role_row.role='faculty'
        role_row.updated_at=now_iso()
    else:
        s.add(FacultyRole(faculty_id=faculty.id,role='faculty',department='',updated_at=now_iso()))

    # Removing the old row is essential: staff login checks Admin before Faculty,
    # so leaving it here would still grant the legacy username Super Admin rights.
    s.delete(legacy)


def init_db():
    Base.metadata.create_all(engine)
    s=DB()
    try:
        seed_subject_catalog(s)
        if APP_MODE=='online' or not OFFLINE_REQUIRE_SETUP:
            ensure_super_admin_identity(s)
            get_institution(s,create=True)
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
    now_ts=int(time.time())
    if web_session.get('role'):
        last=int(web_session.get('_last_activity',now_ts))
        if now_ts-last>SESSION_TIMEOUT_MINUTES*60:
            web_session.clear();web_session['_csrf_token']=secrets.token_urlsafe(32);flash('Your session expired after inactivity. Please sign in again.','error')
            if request.endpoint not in {'home','static','health'}:return redirect(url_for('home'))
        else:web_session['_last_activity']=now_ts
    if '_csrf_token' not in web_session: web_session['_csrf_token']=secrets.token_urlsafe(32)
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        supplied=request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not supplied or not secrets.compare_digest(str(supplied),str(web_session.get('_csrf_token',''))):
            abort(400,'Security token validation failed. Refresh the page and try again.')

@app.context_processor
def globals_for_templates():
    try:
        s=DB();institution=get_institution(s,create=True);staff_role=current_staff_role(s) if web_session.get('role') in {'admin','faculty'} else web_session.get('role','')
    except Exception:
        institution=None;staff_role=web_session.get('role','')
    return {'csrf_token':web_session.get('_csrf_token',''),'web_session':web_session,'is_online':APP_MODE=='online','app_version':APP_VERSION,'institution':institution,'staff_role':staff_role,'staff_role_label':ROLE_LABELS.get(staff_role,staff_role.replace('_',' ').title() if staff_role else '')}

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
                inst=get_institution(s,create=True)
                inst.institution_name=request.form.get('institution_name','').strip() or 'Learn with Hemant'
                inst.short_name=request.form.get('short_name','').strip() or inst.institution_name
                inst.system_name=request.form.get('system_name','').strip() or 'Examination Management System'
                inst.department=request.form.get('department','').strip();inst.academic_year=request.form.get('academic_year','').strip();inst.admin_email=request.form.get('admin_email','').strip();inst.exam_controller=request.form.get('exam_controller','').strip();inst.updated_at=now_iso()
                s.add(Admin(username=username,password_hash=generate_password_hash(password))); s.commit(); flash('Institution and administrator account created. You can now sign in.'); return redirect(url_for('home'))
            except IntegrityError:
                s.rollback(); flash('That administrator username is already in use.','error')
    return render_template('setup.html',login_page=True)

@app.route('/download/offline')
def offline_download():
    parsed=urlparse(OFFLINE_DOWNLOAD_URL)
    if parsed.scheme not in {'https','http'} or not parsed.netloc: abort(503,'Offline download is temporarily unavailable.')
    return redirect(OFFLINE_DOWNLOAD_URL,code=302)

@app.template_filter('dt')
def format_dt(v):
    if not v:return '-'
    try:return display_dt(v).strftime('%d %b %Y, %I:%M %p')
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

def approver_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if web_session.get('role') not in {'admin','faculty'}:return redirect(url_for('home'))
        if not can_approve_exams(DB()):abort(403)
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
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role=role,user_id=row.id,username=row.username,_last_activity=int(time.time()))
                audit_event(s,'staff_login','user',row.id,role); s.commit(); return redirect(url_for('admin_dashboard'))
        else:
            row=s.scalar(select(Student).where(Student.roll_no==request.form.get('roll_no','').strip()))
            if row and check_password_hash(row.password_hash,request.form.get('password','')):
                csrf=web_session.get('_csrf_token'); web_session.clear(); web_session['_csrf_token']=csrf; web_session.update(role='student',user_id=row.id,username=row.roll_no,_last_activity=int(time.time())); return redirect(url_for('student_dashboard'))
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
                st=Student(roll_no=roll,name=name,password_hash=generate_password_hash(pw),created_at=now_iso()); s.add(st); s.flush();
                try:group_id=int(request.form.get('group_id','0') or 0)
                except ValueError:group_id=0
                if group_id and s.get(AcademicGroup,group_id):assign_student_group(s,st.id,group_id)
                audit_event(s,'student_created','student',st.id,roll); s.commit(); flash('Student added.')
            except IntegrityError:s.rollback();flash('Roll number already exists.','error')
    rows=s.scalars(select(Student).order_by(Student.roll_no)).all();groups=s.scalars(select(AcademicGroup).where(AcademicGroup.is_active==True).order_by(AcademicGroup.program,AcademicGroup.semester,AcademicGroup.section)).all();membership=dict(s.execute(select(StudentGroup.student_id,StudentGroup.group_id)).all());group_map={g.id:g for g in groups};return render_template('students.html',students=rows,groups=groups,membership=membership,group_map=group_map,group_label=group_label)

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
        st=Student(roll_no=roll,name=name,password_hash=generate_password_hash(password),created_at=now_iso());s.add(st);s.flush()
        group=find_or_create_group(s,row.get('department',''),row.get('program',''),row.get('semester',''),row.get('section',''),row.get('academic_year',''))
        if group:assign_student_group(s,st.id,group.id)
        seen.add(roll); added+=1
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
    headers=['roll_no','name','password','department','program','semester','section','academic_year']
    if fmt=='csv':
        out=io.StringIO(newline=''); writer=csv.writer(out); writer.writerow(headers); data=io.BytesIO(out.getvalue().encode('utf-8-sig')); return send_file(data,mimetype='text/csv',as_attachment=True,download_name='student_import_template.csv')
    if fmt=='xlsx':
        wb=Workbook(); ws=wb.active; ws.title='Students'; ws.append(headers)
        for cell in ws[1]:cell.font=Font(bold=True)
        ws.column_dimensions['A'].width=18;ws.column_dimensions['B'].width=28;ws.column_dimensions['C'].width=22
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='student_import_template.xlsx')
    abort(404)


@app.route('/admin/groups',methods=['GET','POST'])
@staff_required
def academic_groups():
    s=DB()
    if request.method=='POST':
        action=request.form.get('action','create')
        if action=='create':
            group=find_or_create_group(s,request.form.get('department',''),request.form.get('program',''),request.form.get('semester',''),request.form.get('section',''),request.form.get('academic_year',''))
            if not group:flash('Program, semester and section are required.','error')
            else:audit_event(s,'academic_group_created','group',group.id,group_label(group));s.commit();flash('Batch / section created.')
        elif action=='assign':
            try:student_id=int(request.form.get('student_id','0'));group_id=int(request.form.get('group_id','0'))
            except ValueError:student_id=group_id=0
            if s.get(Student,student_id) and s.get(AcademicGroup,group_id):assign_student_group(s,student_id,group_id);audit_event(s,'student_group_assigned','student',student_id,f'group={group_id}');s.commit();flash('Student batch / section updated.')
        return redirect(url_for('academic_groups'))
    groups=s.scalars(select(AcademicGroup).order_by(AcademicGroup.academic_year.desc(),AcademicGroup.program,AcademicGroup.semester,AcademicGroup.section)).all()
    counts=dict(s.execute(select(StudentGroup.group_id,func.count()).group_by(StudentGroup.group_id)).all())
    students_list=s.scalars(select(Student).order_by(Student.roll_no)).all();memberships=dict(s.execute(select(StudentGroup.student_id,StudentGroup.group_id)).all())
    return render_template('groups.html',groups=groups,counts=counts,students=students_list,memberships=memberships,group_label=group_label)

@app.route('/admin/groups/<int:group_id>/toggle',methods=['POST'])
@staff_required
def toggle_group(group_id):
    s=DB();row=s.get(AcademicGroup,group_id)
    if row:row.is_active=not row.is_active;audit_event(s,'academic_group_enabled' if row.is_active else 'academic_group_disabled','group',row.id,group_label(row));s.commit()
    return redirect(url_for('academic_groups'))

@app.route('/admin/question-bank',methods=['GET','POST'])
@staff_required
def question_bank():
    s=DB()
    seed_subject_catalog(s)
    if request.method=='POST':
        question=request.form.get('question','').strip(); ans=request.form.get('correct_answer','A').upper()
        subject_name=request.form.get('subject','').strip()
        catalog_subject=s.scalar(select(SubjectCatalog).where(SubjectCatalog.name==subject_name,SubjectCatalog.is_active==True)) if subject_name else None
        if not question: flash('Question text is required.','error')
        elif not catalog_subject: flash('Choose a subject from the Subject Catalog, or add your custom subject first.','error')
        elif ans not in {'A','B','C','D'}: flash('Correct answer must be A, B, C or D.','error')
        else:
            try: marks=max(1,int(request.form.get('marks','1')))
            except ValueError: marks=1
            status='approved' if can_approve_content(s) and request.form.get('status')=='approved' else 'draft'
            course_semester=request.form.get('course_semester','').strip() or catalog_subject.course_semester
            bq=BankQuestion(
                subject=catalog_subject.name,course_semester=course_semester,unit=request.form.get('unit','').strip(),topic=request.form.get('topic','').strip(),question_type='MCQ',question=question,
                option_a=request.form.get('option_a','').strip(),option_b=request.form.get('option_b','').strip(),option_c=request.form.get('option_c','').strip(),option_d=request.form.get('option_d','').strip(),correct_answer=ans,marks=marks,
                difficulty=canonical_difficulty(request.form.get('difficulty')),bloom_level=canonical_bloom(request.form.get('bloom_level')),co_mapping=request.form.get('co_mapping','').strip(),tags=request.form.get('tags','').strip(),status=status,version=1,created_by=actor_label(s),created_at=now_iso(),updated_at=now_iso())
            s.add(bq); s.flush(); audit_event(s,'bank_question_created','bank_question',bq.id,f'status={status}, subject={catalog_subject.name}, category={catalog_subject.category}'); s.commit(); flash('Question added to the bank.')
            return redirect(url_for('question_bank',subject=catalog_subject.name)+'#subject-workspace')
    q=(request.args.get('q') or '').strip(); category=(request.args.get('category') or '').strip(); subject=(request.args.get('subject') or '').strip(); unit=(request.args.get('unit') or '').strip(); difficulty=(request.args.get('difficulty') or '').strip(); status=(request.args.get('status') or '').strip()
    catalog_rows=s.scalars(select(SubjectCatalog).where(SubjectCatalog.is_active==True).order_by(SubjectCatalog.category,SubjectCatalog.name)).all()
    catalog_map={row.name:row for row in catalog_rows}
    stmt=select(BankQuestion)
    if q: stmt=stmt.where(or_(BankQuestion.question.ilike(f'%{q}%'),BankQuestion.topic.ilike(f'%{q}%'),BankQuestion.tags.ilike(f'%{q}%')))
    if category:
        category_subjects=[row.name for row in catalog_rows if row.category==category]
        stmt=stmt.where(BankQuestion.subject.in_(category_subjects)) if category_subjects else stmt.where(BankQuestion.id==-1)
    if subject: stmt=stmt.where(BankQuestion.subject==subject)
    if unit: stmt=stmt.where(BankQuestion.unit==unit)
    if difficulty: stmt=stmt.where(BankQuestion.difficulty==canonical_difficulty(difficulty))
    if status: stmt=stmt.where(BankQuestion.status==status)
    rows=s.scalars(stmt.order_by(BankQuestion.id.desc())).all()
    units=s.scalars(select(BankQuestion.unit).where(BankQuestion.unit!='').distinct().order_by(BankQuestion.unit)).all(); exams_list=s.scalars(select(Exam).order_by(Exam.id.desc())).all()
    usage=dict(s.execute(select(ExamBankMap.bank_question_id,func.count(func.distinct(ExamBankMap.exam_id))).group_by(ExamBankMap.bank_question_id)).all())
    question_counts=dict(s.execute(select(BankQuestion.subject,func.count()).group_by(BankQuestion.subject)).all())
    preloaded_packs=preloaded_pack_statuses(s)
    preloaded_categories=sorted({p.get('category','General') for p in preloaded_packs})
    catalog_groups=subject_catalog_groups(s)
    catalog_categories=sorted({row.category for row in catalog_rows})
    selected_catalog_subject=catalog_map.get(subject) if subject else None
    selected_subject_stats=None
    if selected_catalog_subject:
        approved_count=s.scalar(select(func.count()).select_from(BankQuestion).where(BankQuestion.subject==selected_catalog_subject.name,BankQuestion.status=='approved')) or 0
        draft_count=s.scalar(select(func.count()).select_from(BankQuestion).where(BankQuestion.subject==selected_catalog_subject.name,BankQuestion.status=='draft')) or 0
        selected_subject_stats={'total':approved_count+draft_count,'approved':approved_count,'draft':draft_count}
    return render_template('question_bank.html',questions=rows,subjects=catalog_rows,subject_groups=catalog_groups,catalog_categories=catalog_categories,catalog_map=catalog_map,question_counts=question_counts,selected_catalog_subject=selected_catalog_subject,selected_subject_stats=selected_subject_stats,units=units,exams=exams_list,usage=usage,filters={'q':q,'category':category,'subject':subject,'unit':unit,'difficulty':difficulty,'status':status},preloaded_packs=preloaded_packs,preloaded_categories=preloaded_categories)

@app.route('/admin/question-bank/subjects',methods=['POST'])
@staff_required
def add_subject_catalog():
    s=DB()
    name=(request.form.get('subject_name') or '').strip()
    category=(request.form.get('category') or '').strip()
    course=(request.form.get('course_semester') or '').strip()
    if not name:
        flash('Subject name is required.','error'); return redirect(url_for('question_bank'))
    if not category:
        flash('Assign a category before adding the subject.','error'); return redirect(url_for('question_bank'))
    existing=s.scalar(select(SubjectCatalog).where(func.lower(SubjectCatalog.name)==name.lower()))
    if existing:
        existing.category=category; existing.course_semester=course or existing.course_semester; existing.is_active=True
        audit_event(s,'subject_catalog_updated','subject',existing.id,f'name={existing.name}, category={category}')
        s.commit(); flash(f'Updated subject “{existing.name}” under {category}.')
        return redirect(url_for('question_bank',subject=existing.name)+'#subject-workspace')
    row=ensure_subject_catalog_entry(s,name,category,course,actor_label(s)); s.flush()
    audit_event(s,'subject_catalog_created','subject',row.id,f'name={row.name}, category={row.category}')
    s.commit(); flash(f'Added “{row.name}” under {row.category}. It is now available in the question form.')
    return redirect(url_for('question_bank',subject=row.name)+'#subject-workspace')

@app.route('/admin/question-bank/subjects/<int:subject_id>/toggle',methods=['POST'])
@approver_required
def toggle_subject_catalog(subject_id):
    s=DB(); row=s.get(SubjectCatalog,subject_id)
    if not row: abort(404)
    row.is_active=not row.is_active
    audit_event(s,'subject_catalog_activated' if row.is_active else 'subject_catalog_deactivated','subject',row.id,f'name={row.name}, category={row.category}')
    s.commit(); flash(f'{row.name} is now '+('active.' if row.is_active else 'hidden from new-question selection.'))
    return redirect(url_for('question_bank'))

@app.route('/admin/question-bank/subjects/<int:subject_id>/create-exam',methods=['POST'])
@staff_required
def create_exam_from_catalog_subject(subject_id):
    """Create an inactive draft exam from the approved questions of a catalog subject."""
    s=DB(); subject=s.get(SubjectCatalog,subject_id)
    if not subject: abort(404)
    if not subject.is_active:
        flash('This subject is not active in the Subject Catalog.','error')
        return redirect(url_for('question_bank'))

    bank_rows=s.scalars(select(BankQuestion).where(
        BankQuestion.subject==subject.name,
        BankQuestion.status=='approved'
    ).order_by(BankQuestion.unit,BankQuestion.id)).all()
    if not bank_rows:
        flash(f'Add and approve at least one question for {subject.name} before creating an exam.','error')
        return redirect(url_for('question_bank',subject=subject.name)+'#subject-workspace')

    try:
        duration=max(1,int(request.form.get('duration','20')))
    except ValueError:
        duration=20
    try:
        per_student=max(1,int(request.form.get('question_count','10')))
    except ValueError:
        per_student=10
    per_student=min(per_student,len(bank_rows))

    exam=Exam(title=subject.name,duration_minutes=duration,is_active=False,created_at=now_iso())
    s.add(exam); s.flush()
    cfg=get_exam_config(s,exam.id,create=True)
    cfg.subject=subject.name
    cfg.course_semester=subject.course_semester or ''
    cfg.question_count=per_student
    cfg.pool_size=len(bank_rows)

    easy=sum(1 for q in bank_rows if canonical_difficulty(q.difficulty)=='Easy')
    medium=sum(1 for q in bank_rows if canonical_difficulty(q.difficulty)=='Medium')
    total=max(1,len(bank_rows))
    cfg.easy_pct=round(easy*100/total)
    cfg.medium_pct=round(medium*100/total)
    cfg.hard_pct=max(0,100-cfg.easy_pct-cfg.medium_pct)
    units=sorted({(q.unit or '').strip() for q in bank_rows if (q.unit or '').strip()})
    cfg.unit_weights=json.dumps({u:1 for u in units},ensure_ascii=False)
    cfg.randomize_questions=True
    cfg.shuffle_options=True
    cfg.require_fullscreen=False
    cfg.tab_switch_limit=3
    cfg.last_generation_summary=f'Created from {subject.name}: {len(bank_rows)} approved bank questions; each student receives {per_student}.'
    cfg.updated_at=now_iso()
    get_exam_approval(s,exam.id,create=True)

    for bq in bank_rows:
        copy_bank_question_to_exam(s,bq,exam.id)

    audit_event(s,'catalog_subject_exam_created','exam',exam.id,f'subject={subject.name}, pool={len(bank_rows)}, per_student={per_student}')
    s.commit()
    flash(f'Created ready exam “{subject.name}” with {len(bank_rows)} approved questions. Review the blueprint, approve it, then activate it for students.')
    return redirect(url_for('exam_builder', exam_id=exam.id))


@app.route('/admin/question-bank/preloaded/export/<fmt>')
@staff_required
def export_preloaded_question_banks(fmt):
    headers=['category','subject','course_semester','unit','topic','question','option_a','option_b','option_c','option_d','correct_answer','marks','difficulty','bloom_level','co_mapping','tags']
    rows=[]
    for pack in load_preloaded_question_banks().values():
        for q in pack.get('questions',[]):
            row=dict(q)
            row['category']=pack.get('category','Engineering')
            row['subject']=row.get('subject') or pack.get('subject','')
            row['course_semester']=row.get('course_semester') or pack.get('course_semester','')
            rows.append([row.get(h,'') for h in headers])
    if fmt=='csv':
        out=io.StringIO(newline=''); writer=csv.writer(out); writer.writerow(headers); writer.writerows(rows)
        data=io.BytesIO(out.getvalue().encode('utf-8-sig'))
        return send_file(data,mimetype='text/csv',as_attachment=True,download_name='preloaded_engineering_question_banks.csv')
    if fmt=='xlsx':
        wb=Workbook(); ws=wb.active; ws.title='Question Banks'; ws.append(headers)
        for cell in ws[1]: cell.font=Font(bold=True)
        for row in rows: ws.append(row)
        widths={'A':22,'B':34,'C':24,'D':8,'E':28,'F':58,'G':45,'H':45,'I':45,'J':45,'K':14,'L':9,'M':12,'N':16,'O':12,'P':34}
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
    target_subject=(request.form.get('target_subject') or '').strip()
    redirect_url=url_for('question_bank',subject=target_subject)+'#subject-workspace' if target_subject else url_for('question_bank')
    if not upload or not upload.filename: flash('Choose a CSV or Excel (.xlsx) file.','error');return redirect(redirect_url)
    try: headers,rows=_rows_from_upload(upload)
    except ValueError as exc: flash(str(exc),'error');return redirect(redirect_url)
    s=DB()
    target_catalog=None
    if target_subject:
        target_catalog=s.scalar(select(SubjectCatalog).where(SubjectCatalog.name==target_subject,SubjectCatalog.is_active==True))
        if not target_catalog:
            flash('The selected Subject Catalog entry is not active.','error');return redirect(url_for('question_bank'))
    required={'question','option_a','option_b','option_c','option_d','correct_answer','marks'}
    if not target_catalog: required.add('subject')
    if not required.issubset(set(headers)):
        flash('Question bank file is missing required columns. Download the template and try again.','error');return redirect(redirect_url)
    added=invalid=0
    for r in rows:
        ans=(r.get('correct_answer') or '').upper().strip(); question=(r.get('question') or '').strip()
        if not question or ans not in {'A','B','C','D'}: invalid+=1;continue
        try:marks=max(1,int(r.get('marks') or 1))
        except ValueError:marks=1
        requested_status=(r.get('status') or 'draft').lower(); status='approved' if can_approve_content(s) and requested_status=='approved' else 'draft'
        if target_catalog:
            subject_name=target_catalog.name
            course=(r.get('course_semester') or '').strip() or target_catalog.course_semester
            category=target_catalog.category
        else:
            subject_name=(r.get('subject') or 'General').strip() or 'General'; course=(r.get('course_semester') or '').strip(); category=(r.get('category') or '').strip() or 'Imported / Other'
            ensure_subject_catalog_entry(s,subject_name,category,course,actor_label(s))
        s.add(BankQuestion(subject=subject_name,course_semester=course,unit=(r.get('unit') or '').strip(),topic=(r.get('topic') or '').strip(),question_type='MCQ',question=question,option_a=(r.get('option_a') or '').strip(),option_b=(r.get('option_b') or '').strip(),option_c=(r.get('option_c') or '').strip(),option_d=(r.get('option_d') or '').strip(),correct_answer=ans,marks=marks,difficulty=canonical_difficulty(r.get('difficulty')),bloom_level=canonical_bloom(r.get('bloom_level')),co_mapping=(r.get('co_mapping') or '').strip(),tags=(r.get('tags') or '').strip(),status=status,version=1,created_by=actor_label(s),created_at=now_iso(),updated_at=now_iso()));added+=1
    audit_event(s,'question_bank_bulk_import','bank_question','',f'added={added}, invalid={invalid}, target_subject={target_subject or "mixed"}')
    s.commit();flash(f'Imported {added} question(s).'+(f' Skipped {invalid} invalid row(s).' if invalid else ''));return redirect(redirect_url)

@app.route('/admin/question-bank/template/<fmt>')
@staff_required
def question_bank_template(fmt):
    headers=['category','subject','course_semester','unit','topic','question','option_a','option_b','option_c','option_d','correct_answer','marks','difficulty','bloom_level','co_mapping','tags','status']
    subject_name=(request.args.get('subject') or '').strip()
    category='Computer Science'; course='B.Tech CSE / Sem 5'
    if subject_name:
        s=DB(); row=s.scalar(select(SubjectCatalog).where(SubjectCatalog.name==subject_name,SubjectCatalog.is_active==True))
        if row: category=row.category; course=row.course_semester; subject_name=row.name
        else: subject_name=''
    example=[category,subject_name or 'Mobile Application Development',course or 'B.Tech CSE / Sem 5','1','Introduction','Replace this sample with your question','Option A','Option B','Option C','Option D','A','1','Medium','Understand','CO1','custom','approved']
    safe_name=''.join(ch if ch.isalnum() else '_' for ch in (subject_name or 'question_bank')).strip('_') or 'question_bank'
    if fmt=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out);writer.writerow(headers);writer.writerow(example);data=io.BytesIO(out.getvalue().encode('utf-8-sig'));return send_file(data,mimetype='text/csv',as_attachment=True,download_name=f'{safe_name}_question_bank_template.csv')
    if fmt=='xlsx':
        wb=Workbook();ws=wb.active;ws.title='Question Bank';ws.append(headers);ws.append(example)
        for cell in ws[1]:cell.font=Font(bold=True)
        for col,width in {'A':22,'B':28,'C':24,'D':10,'E':24,'F':58,'G':26,'H':26,'I':26,'J':26,'K':15,'L':10,'M':14,'N':16,'O':14,'P':26,'Q':12}.items():ws.column_dimensions[col].width=width
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=f'{safe_name}_question_bank_template.xlsx')
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
        subject_name=request.form.get('subject','').strip(); catalog_subject=s.scalar(select(SubjectCatalog).where(SubjectCatalog.name==subject_name,SubjectCatalog.is_active==True)); q.subject=catalog_subject.name if catalog_subject else q.subject;q.course_semester=request.form.get('course_semester','').strip() or (catalog_subject.course_semester if catalog_subject else q.course_semester);q.unit=request.form.get('unit','').strip();q.topic=request.form.get('topic','').strip();q.question=request.form.get('question','').strip();q.option_a=request.form.get('option_a','').strip();q.option_b=request.form.get('option_b','').strip();q.option_c=request.form.get('option_c','').strip();q.option_d=request.form.get('option_d','').strip();q.correct_answer=request.form.get('correct_answer','A').upper()
        try:q.marks=max(1,int(request.form.get('marks','1')))
        except ValueError:q.marks=1
        q.difficulty=canonical_difficulty(request.form.get('difficulty'));q.bloom_level=canonical_bloom(request.form.get('bloom_level'));q.co_mapping=request.form.get('co_mapping','').strip();q.tags=request.form.get('tags','').strip();q.version+=1;q.updated_at=now_iso()
        if can_approve_content(s):q.status=request.form.get('status','draft') if request.form.get('status') in {'draft','approved'} else 'draft'
        else:q.status='draft'
        audit_event(s,'bank_question_edited','bank_question',q.id,f'version={q.version}, status={q.status}');s.commit();flash('Question updated. Previous version was preserved.');return redirect(url_for('edit_bank_question',question_id=q.id))
    seed_subject_catalog(s); return render_template('question_bank_edit.html',question=q,revisions=revisions,subject_groups=subject_catalog_groups(s))

@app.route('/admin/question-bank/<int:question_id>/approve',methods=['POST'])
@approver_required
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
            e=Exam(title=title,duration_minutes=duration,is_active=False,created_at=now_iso());s.add(e);s.flush();get_exam_config(s,e.id,create=True);get_exam_approval(s,e.id,create=True);audit_event(s,'exam_created','exam',e.id,title);s.commit();flash('Exam created as draft.')
    raw=s.execute(select(Exam,func.count(Question.id)).outerjoin(Question,Question.exam_id==Exam.id).group_by(Exam.id).order_by(Exam.id.desc())).all();rows=[]
    for e,count in raw:
        cfg=get_exam_config(s,e.id);target=(cfg.question_count if cfg and cfg.question_count else count)
        approval=get_exam_approval(s,e.id,create=True);session_count=s.scalar(select(func.count()).select_from(ExamSession).where(ExamSession.exam_id==e.id)) or 0;rows.append(type('ExamRow',(),{'id':e.id,'title':e.title,'duration_minutes':e.duration_minutes,'is_active':e.is_active,'question_count':count,'student_question_count':min(target,count) if count else 0,'approval_status':approval.status,'session_count':session_count})())
    return render_template('exams.html',exams=rows)

@app.route('/admin/exam/<int:exam_id>/toggle',methods=['POST'])
@staff_required
def toggle_exam(exam_id):
    s=DB();e=s.get(Exam,exam_id)
    if e:
        if not e.is_active and (s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==exam_id)) or 0)==0:flash('Add questions before activating this exam.','error');return redirect(url_for('exams'))
        if not e.is_active:
            approval=get_exam_approval(s,exam_id,create=True)
            if approval.status!='approved':
                if can_approve_exams(s):
                    approval.status='approved';approval.reviewed_by=actor_label(s);approval.reviewed_at=now_iso();approval.comments='Approved during activation';audit_event(s,'exam_approved','exam',e.id,'approved during activation')
                else:
                    flash('This exam requires HOD / Exam Controller approval before activation. Use Request Approval first.','error');return redirect(url_for('exams'))
        e.is_active=not bool(e.is_active);audit_event(s,'exam_activated' if e.is_active else 'exam_deactivated','exam',e.id,e.title);s.commit()
    return redirect(url_for('exams'))


@app.route('/admin/exam/<int:exam_id>/approval/request',methods=['POST'])
@staff_required
def request_exam_approval(exam_id):
    s=DB();exam=s.get(Exam,exam_id)
    if not exam:abort(404)
    row=get_exam_approval(s,exam_id,create=True);row.status='pending';row.requested_by=actor_label(s);row.requested_at=now_iso();row.comments=request.form.get('comments','').strip()[:500];row.reviewed_by='';row.reviewed_at='';audit_event(s,'exam_approval_requested','exam',exam_id,row.comments);s.commit();flash('Exam sent for HOD / Exam Controller approval.');return redirect(request.referrer or url_for('exams'))

@app.route('/admin/exam/<int:exam_id>/approval/<decision>',methods=['POST'])
@approver_required
def review_exam_approval(exam_id,decision):
    if decision not in {'approve','reject'}:abort(404)
    s=DB();exam=s.get(Exam,exam_id)
    if not exam:abort(404)
    row=get_exam_approval(s,exam_id,create=True);row.status='approved' if decision=='approve' else 'rejected';row.reviewed_by=actor_label(s);row.reviewed_at=now_iso();row.comments=request.form.get('comments','').strip()[:500];audit_event(s,'exam_approved' if decision=='approve' else 'exam_rejected','exam',exam_id,row.comments);s.commit();flash('Exam approved.' if decision=='approve' else 'Exam returned for changes.');return redirect(request.referrer or url_for('exams'))

@app.route('/admin/exam/<int:exam_id>/session',methods=['POST'])
@staff_required
def save_exam_session(exam_id):
    s=DB();exam=s.get(Exam,exam_id)
    if not exam:abort(404)
    try:group_id=int(request.form.get('group_id','0'))
    except ValueError:group_id=0
    group=s.get(AcademicGroup,group_id)
    if not group:flash('Choose a valid batch / section.','error');return redirect(url_for('exam_builder',exam_id=exam_id))
    try:start=parse_local_schedule(request.form.get('scheduled_start',''));end=parse_local_schedule(request.form.get('scheduled_end',''))
    except ValueError as exc:flash(str(exc),'error');return redirect(url_for('exam_builder',exam_id=exam_id))
    if start and end and datetime.fromisoformat(end)<=datetime.fromisoformat(start):flash('Session end time must be after the start time.','error');return redirect(url_for('exam_builder',exam_id=exam_id))
    row=s.scalar(select(ExamSession).where(ExamSession.exam_id==exam_id,ExamSession.group_id==group_id))
    if row:row.scheduled_start=start;row.scheduled_end=end;row.venue=request.form.get('venue','').strip()
    else:s.add(ExamSession(exam_id=exam_id,group_id=group_id,scheduled_start=start,scheduled_end=end,venue=request.form.get('venue','').strip(),created_at=now_iso()))
    audit_event(s,'exam_session_saved','exam',exam_id,f'{group_label(group)}, {start or "any time"}, venue={request.form.get("venue","").strip()}');s.commit();flash('Exam batch / section session saved.');return redirect(url_for('exam_builder',exam_id=exam_id))

@app.route('/admin/exam/<int:exam_id>/session/<int:session_id>/delete',methods=['POST'])
@staff_required
def delete_exam_session(exam_id,session_id):
    s=DB();row=s.get(ExamSession,session_id)
    if row and row.exam_id==exam_id:s.delete(row);audit_event(s,'exam_session_deleted','exam',exam_id,f'session={session_id}');s.commit();flash('Exam session removed.')
    return redirect(url_for('exam_builder',exam_id=exam_id))

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
    groups=s.scalars(select(AcademicGroup).where(AcademicGroup.is_active==True).order_by(AcademicGroup.program,AcademicGroup.semester,AcademicGroup.section)).all();sessions=s.execute(select(ExamSession,AcademicGroup).join(AcademicGroup,AcademicGroup.id==ExamSession.group_id).where(ExamSession.exam_id==exam_id).order_by(ExamSession.scheduled_start)).all();approval=get_exam_approval(s,exam_id,create=True);return render_template('exam_builder.html',exam=exam,cfg=cfg,subjects=subjects,pool_count=pool_count,attempt_count=attempt_count,unit_weights_display=unit_weights_display,groups=groups,sessions=sessions,approval=approval,group_label=group_label,can_approve=can_approve_exams(s))

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

    # Load integrity activity once so the Results page can show a useful breakdown
    # without exposing those details on the student's result screen.
    integrity_by_attempt={}
    for ev in s.scalars(select(IntegrityEvent).order_by(IntegrityEvent.created_at,IntegrityEvent.id)).all():
        integrity_by_attempt.setdefault(ev.attempt_id,[]).append(ev)

    for a,st,e in raw:
        events=integrity_by_attempt.get(a.id,[])
        tab_switches=sum(1 for ev in events if ev.event_type=='tab_hidden')
        fullscreen_exits=sum(1 for ev in events if ev.event_type=='fullscreen_exit')
        pct,grade,_grade_class=result_performance(a.score,a.total_marks) if a.status=='submitted' else (0,'-','')
        grp=student_group(s,st.id)
        rows.append(type('ResultRow',(),{
            'attempt_id':a.id,
            'roll_no':st.roll_no,
            'name':st.name,
            'group_label':group_label(grp) if grp else 'Unassigned',
            'title':e.title,
            'exam_id':e.id,
            'status':a.status,
            'score':a.score,
            'total_marks':a.total_marks,
            'percentage':pct,
            'grade':grade,
            'started_at':a.started_at,
            'submitted_at':a.submitted_at,
            'violations':len(events),
            'tab_switches':tab_switches,
            'fullscreen_exits':fullscreen_exits,
            'integrity_events':events,
        })())
    return rows

@app.route('/admin/results')
@staff_required
def results():
    s=DB();exam_id=request.args.get('exam_id',type=int);rows=result_rows(s,exam_id);exams_list=s.scalars(select(Exam).order_by(Exam.title)).all();return render_template('results.html',rows=rows,exams=exams_list,selected_exam_id=exam_id)

@app.route('/admin/results/export/<fmt>')
@staff_required
def export_results(fmt):
    s=DB();exam_id=request.args.get('exam_id',type=int);rows=result_rows(s,exam_id);headers=['roll_no','name','batch_section','exam','status','score','total_marks','percentage','grade','tab_switches','fullscreen_exits','total_integrity_events','started','submitted']
    matrix=[[r.roll_no,r.name,r.group_label,r.title,r.status,r.score if r.score is not None else '',r.total_marks if r.total_marks is not None else '',r.percentage if r.status=='submitted' else '',r.grade if r.status=='submitted' else '',r.tab_switches,r.fullscreen_exits,r.violations,r.started_at,r.submitted_at or ''] for r in rows]
    suffix=f'_exam_{exam_id}' if exam_id else '_all'
    if fmt=='csv':
        out=io.StringIO(newline='');w=csv.writer(out);w.writerow(headers);w.writerows(matrix);data=io.BytesIO(out.getvalue().encode('utf-8-sig'));return send_file(data,mimetype='text/csv',as_attachment=True,download_name=f'exam_results{suffix}.csv')
    if fmt=='xlsx':
        wb=Workbook();ws=wb.active;ws.title='Results';ws.append(headers)
        for row in matrix:ws.append(row)
        for cell in ws[1]:cell.font=Font(bold=True)
        widths=[16,28,34,30,14,10,12,12,16,14,16,20,24,24]
        for idx,width in enumerate(widths,1):ws.column_dimensions[chr(64+idx)].width=width
        data=io.BytesIO();wb.save(data);data.seek(0);return send_file(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=f'exam_results{suffix}.xlsx')
    abort(404)


def _score_summary(percentages):
    if not percentages:return {'count':0,'average':0,'highest':0,'lowest':0,'pass_pct':0,'outstanding':0,'very_good':0,'good':0,'average_grade':0,'poor':0}
    vals=[float(x) for x in percentages];n=len(vals)
    return {'count':n,'average':round(sum(vals)/n,1),'highest':round(max(vals),1),'lowest':round(min(vals),1),'pass_pct':round(sum(1 for x in vals if x>=40)*100/n,1),'outstanding':sum(1 for x in vals if x>=90),'very_good':sum(1 for x in vals if 75<=x<90),'good':sum(1 for x in vals if 60<=x<75),'average_grade':sum(1 for x in vals if 40<=x<60),'poor':sum(1 for x in vals if x<40)}


def institutional_analytics_data(s):
    raw=s.execute(select(Attempt,Student,Exam).join(Student,Student.id==Attempt.student_id).join(Exam,Exam.id==Attempt.exam_id).where(Attempt.status=='submitted')).all()
    percentages=[];exam_pcts={};student_pcts={}
    for a,st,e in raw:
        pct=((a.score or 0)/(a.total_marks or 1))*100;percentages.append(pct);exam_pcts.setdefault(e.id,[]).append(pct);student_pcts.setdefault(st.id,[]).append(pct)
    overall=_score_summary(percentages)
    exam_rows=[]
    exams_all=s.scalars(select(Exam).order_by(Exam.id.desc())).all();total_students=s.scalar(select(func.count()).select_from(Student)) or 0
    for e in exams_all:
        sessions=s.scalars(select(ExamSession).where(ExamSession.exam_id==e.id)).all();group_ids={x.group_id for x in sessions}
        if group_ids:
            strength=s.scalar(select(func.count(func.distinct(StudentGroup.student_id))).where(StudentGroup.group_id.in_(group_ids))) or 0
        else:strength=total_students
        summary=_score_summary(exam_pcts.get(e.id,[]));appeared=summary['count'];exam_rows.append({'id':e.id,'title':e.title,'strength':int(strength),'appeared':appeared,'absent':max(0,int(strength)-appeared),'average':summary['average'],'highest':summary['highest'],'lowest':summary['lowest'],'pass_pct':summary['pass_pct']})
    group_rows=[];groups=s.scalars(select(AcademicGroup).order_by(AcademicGroup.program,AcademicGroup.semester,AcademicGroup.section)).all();membership=dict(s.execute(select(StudentGroup.student_id,StudentGroup.group_id)).all())
    for g in groups:
        student_ids=[sid for sid,gid in membership.items() if gid==g.id];vals=[]
        for sid in student_ids:vals.extend(student_pcts.get(sid,[]))
        summary=_score_summary(vals);group_rows.append({'label':group_label(g),'students':len(student_ids),'attempts':summary['count'],'average':summary['average'],'pass_pct':summary['pass_pct']})
    # Academic attainment from reusable bank metadata.
    maps=s.scalars(select(ExamBankMap)).all();bank_by_exam_q={m.exam_question_id:m.bank_question_id for m in maps};bank_ids=set(bank_by_exam_q.values());banks={b.id:b for b in (s.scalars(select(BankQuestion).where(BankQuestion.id.in_(bank_ids))).all() if bank_ids else [])};questions={q.id:q for q in (s.scalars(select(Question).where(Question.id.in_(list(bank_by_exam_q)))).all() if bank_by_exam_q else [])};submitted_ids={a.id for a,_,_ in raw};unit_stats={};co_stats={}
    if submitted_ids and bank_by_exam_q:
        answers=s.scalars(select(Answer).where(Answer.attempt_id.in_(submitted_ids),Answer.question_id.in_(list(bank_by_exam_q)))).all()
        for ans in answers:
            bank=banks.get(bank_by_exam_q.get(ans.question_id));q=questions.get(ans.question_id)
            if not bank or not q:continue
            ok=1 if ans.selected_answer==q.correct_answer else 0
            if bank.unit:
                key=f'{bank.subject} · Unit {bank.unit}';st=unit_stats.setdefault(key,[0,0]);st[0]+=1;st[1]+=ok
            if bank.co_mapping:
                key=f'{bank.subject} · {bank.co_mapping}';st=co_stats.setdefault(key,[0,0]);st[0]+=1;st[1]+=ok
    unit_rows=[{'label':k,'responses':v[0],'attainment':round(v[1]*100/v[0],1) if v[0] else 0} for k,v in sorted(unit_stats.items())]
    co_rows=[{'label':k,'responses':v[0],'attainment':round(v[1]*100/v[0],1) if v[0] else 0} for k,v in sorted(co_stats.items())]
    return overall,exam_rows,group_rows,unit_rows,co_rows

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
    overall,exam_rows,group_rows,unit_rows,co_rows=institutional_analytics_data(s);return render_template('analytics.html',rows=rows,overall=overall,exam_rows=exam_rows,group_rows=group_rows,unit_rows=unit_rows,co_rows=co_rows)


@app.route('/admin/institution',methods=['GET','POST'])
@admin_required
def institution_settings():
    s=DB();row=get_institution(s,create=True)
    if request.method=='POST':
        row.institution_name=request.form.get('institution_name','').strip() or 'Learn with Hemant';row.short_name=request.form.get('short_name','').strip() or row.institution_name;row.system_name=request.form.get('system_name','').strip() or 'Examination Management System';row.department=request.form.get('department','').strip();row.academic_year=request.form.get('academic_year','').strip();row.admin_email=request.form.get('admin_email','').strip();row.exam_controller=request.form.get('exam_controller','').strip();row.contact_phone=request.form.get('contact_phone','').strip()
        logo=request.files.get('logo_file')
        if logo and logo.filename:
            raw=logo.read();mime=(logo.mimetype or '').lower()
            if mime not in {'image/png','image/jpeg','image/webp'}:flash('Logo must be PNG, JPG or WebP.','error');return redirect(url_for('institution_settings'))
            if len(raw)>1024*1024:flash('Logo must be smaller than 1 MB.','error');return redirect(url_for('institution_settings'))
            row.logo_data=f'data:{mime};base64,'+base64.b64encode(raw).decode('ascii')
        if request.form.get('remove_logo')=='1':row.logo_data=''
        row.updated_at=now_iso();audit_event(s,'institution_profile_updated','system',row.id,row.institution_name);s.commit();flash('Institution branding and profile updated.');return redirect(url_for('institution_settings'))
    return render_template('institution.html',profile=row)

def exam_centre_network_details():
    port=int(os.getenv('PORT','8080'))
    lan_ip=local_lan_ip()
    student_url=request.url_root.rstrip('/') if APP_MODE=='online' else f'http://{lan_ip}:{port}'
    return {'mode':APP_MODE,'lan_ip':lan_ip,'port':port,'student_url':student_url,'qr_uri':qr_data_uri(student_url)}


@app.route('/admin/exam-centre')
@staff_required
def exam_centre():
    s=DB();network=exam_centre_network_details()
    stats={'students':s.scalar(select(func.count()).select_from(Student)) or 0,'active_exams':s.scalar(select(func.count()).select_from(Exam).where(Exam.is_active==True)) or 0,'in_progress':s.scalar(select(func.count()).select_from(Attempt).where(Attempt.status=='in_progress')) or 0}
    return render_template('exam_centre.html',mode=network['mode'],db_name='PostgreSQL' if DATABASE_URL.startswith('postgresql') else 'SQLite',student_url=network['student_url'],qr_uri=network['qr_uri'],lan_ip=network['lan_ip'],port=network['port'],stats=stats)


@app.route('/admin/exam-centre/network-info')
@staff_required
def exam_centre_network_info():
    response=jsonify(exam_centre_network_details())
    response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/admin/faculty',methods=['GET','POST'])
@staff_required
def faculty_users():
    s=DB();viewer_role=current_staff_role(s)
    if viewer_role not in {'super_admin','hod'}:
        abort(403)
    if request.method=='POST':
        # Only the Super Admin may create staff accounts or assign privileged roles.
        if viewer_role!='super_admin':
            abort(403)
        username=request.form.get('username','').strip();name=request.form.get('name','').strip();password=request.form.get('password','')
        if len(username)<3 or not name or len(password)<10:flash('Faculty name, a 3+ character username and a 10+ character password are required.','error')
        elif username.casefold()==super_admin_username.casefold():flash('That username is reserved for the Super Admin account.','error')
        else:
            try:
                role=request.form.get('staff_role','faculty') if request.form.get('staff_role') in {'faculty','hod','exam_controller'} else 'faculty'
                row=Faculty(username=username,name=name,password_hash=generate_password_hash(password),is_active=True,created_at=now_iso());s.add(row);s.flush();s.add(FacultyRole(faculty_id=row.id,role=role,department=request.form.get('department','').strip(),updated_at=now_iso()));audit_event(s,'faculty_created','faculty',row.id,f'{username}, role={role}');s.commit();flash('Staff login created.')
            except IntegrityError:s.rollback();flash('That faculty username already exists.','error')
    rows=s.scalars(select(Faculty).order_by(Faculty.username)).all()
    role_map={r.faculty_id:r for r in s.scalars(select(FacultyRole)).all()}
    # HOD users are deliberately shown Faculty accounts only. They cannot view or
    # manage another HOD, an Exam Controller, or the Super Admin account here.
    if viewer_role=='hod':
        rows=[f for f in rows if (role_map.get(f.id).role if role_map.get(f.id) else 'faculty')=='faculty']
    return render_template('faculty.html',faculty=rows,role_map=role_map,role_labels=ROLE_LABELS,viewer_role=viewer_role)

@app.route('/admin/faculty/<int:faculty_id>/password',methods=['POST'])
@staff_required
def reset_faculty_password(faculty_id):
    s=DB();actor_role=current_staff_role(s)
    if actor_role not in {'super_admin','hod'}:
        abort(403)
    target=s.get(Faculty,faculty_id)
    if not target:
        abort(404)
    target_role_row=s.scalar(select(FacultyRole).where(FacultyRole.faculty_id==faculty_id))
    target_role=target_role_row.role if target_role_row and target_role_row.role in ROLE_LABELS else 'faculty'
    if actor_role=='hod':
        # HOD may reset only ordinary Faculty accounts, never HOD/Controller/Super Admin.
        if target_role!='faculty':
            abort(403)
        if web_session.get('role')=='faculty' and int(web_session.get('user_id') or 0)==faculty_id:
            abort(403)
    password=request.form.get('new_password','')
    confirm=request.form.get('confirm_password','')
    if len(password)<10:
        flash('New password must contain at least 10 characters.','error')
        return redirect(url_for('faculty_users'))
    if password!=confirm:
        flash('New password and confirmation do not match.','error')
        return redirect(url_for('faculty_users'))
    target.password_hash=generate_password_hash(password)
    audit_event(s,'staff_password_reset','faculty',target.id,f'target={target.username}, role={target_role}')
    s.commit()
    flash(f'Password updated for {target.username}.')
    return redirect(url_for('faculty_users'))

@app.route('/admin/faculty/<int:faculty_id>/toggle',methods=['POST'])
@admin_required
def toggle_faculty(faculty_id):
    s=DB();row=s.get(Faculty,faculty_id)
    if row:row.is_active=not row.is_active;audit_event(s,'faculty_enabled' if row.is_active else 'faculty_disabled','faculty',row.id,row.username);s.commit()
    return redirect(url_for('faculty_users'))


@app.route('/admin/faculty/<int:faculty_id>/role',methods=['POST'])
@admin_required
def update_faculty_role(faculty_id):
    s=DB();faculty=s.get(Faculty,faculty_id)
    if not faculty:abort(404)
    role=request.form.get('staff_role','faculty')
    if role not in {'faculty','hod','exam_controller'}:flash('Invalid staff role.','error');return redirect(url_for('faculty_users'))
    row=s.scalar(select(FacultyRole).where(FacultyRole.faculty_id==faculty_id))
    if row:row.role=role;row.department=request.form.get('department','').strip();row.updated_at=now_iso()
    else:s.add(FacultyRole(faculty_id=faculty_id,role=role,department=request.form.get('department','').strip(),updated_at=now_iso()))
    audit_event(s,'faculty_role_updated','faculty',faculty_id,f'role={role}');s.commit();flash('Staff role updated.');return redirect(url_for('faculty_users'))

@app.route('/admin/audit')
@admin_required
def audit_logs():
    s=DB();rows=s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(300)).all();return render_template('audit.html',rows=rows)

@app.route('/admin/system')
@admin_required
def system_tools():
    s=DB();return render_template('system.html',offline=(APP_MODE=='offline'),institution=get_institution(s,create=True))

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


@app.route('/admin/system/backup/encrypted',methods=['POST'])
@admin_required
def system_backup_encrypted():
    if APP_MODE!='offline':abort(400,'Encrypted database backup is available only in offline mode.')
    password=request.form.get('backup_password','')
    if len(password)<10:flash('Use a backup password with at least 10 characters.','error');return redirect(url_for('system_tools'))
    db_path=DATA_DIR/'exam.db'
    if not db_path.exists():abort(404)
    tmp=tempfile.NamedTemporaryFile(prefix='lwh_exam_backup_',suffix='.db',delete=False);tmp.close();src=sqlite3.connect(str(db_path));dst=sqlite3.connect(tmp.name)
    try:src.backup(dst)
    finally:dst.close();src.close()
    try:raw=Path(tmp.name).read_bytes();payload=encrypt_backup_bytes(raw,password)
    finally:
        try:os.unlink(tmp.name)
        except OSError:pass
    s=DB();audit_event(s,'encrypted_backup_downloaded','system','','offline database');s.commit();data=io.BytesIO(payload);stamp=now_dt().strftime('%Y%m%d_%H%M');return send_file(data,as_attachment=True,download_name=f'ExamSystem_Encrypted_Backup_{stamp}.lwhbackup',mimetype='application/octet-stream')

@app.route('/admin/system/restore',methods=['POST'])
@admin_required
def system_restore():
    if APP_MODE!='offline':abort(400,'Direct database restore is available only in offline mode.')
    upload=request.files.get('backup_file')
    if not upload or not upload.filename:flash('Choose a .db or .lwhbackup backup file.','error');return redirect(url_for('system_tools'))
    fd,temp_name=tempfile.mkstemp(prefix='lwh_restore_',suffix='.db'); os.close(fd); temp=Path(temp_name)
    try:
        raw=upload.read()
        if upload.filename.lower().endswith('.lwhbackup') or raw.startswith(b'LWHBK1'):
            password=request.form.get('backup_password','')
            if not password:raise ValueError('Enter the backup password used when the encrypted backup was created.')
            raw=decrypt_backup_bytes(raw,password)
        temp.write_bytes(raw)
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
        allowed,access_label,session_row=exam_access_for_student(s,st.id,e)
        if access_label=='Not assigned to your batch/section':continue
        pool_count=s.scalar(select(func.count()).select_from(Question).where(Question.exam_id==e.id)) or 0;cfg=get_exam_config(s,e.id);display_count=min(cfg.question_count,pool_count) if cfg and cfg.question_count else pool_count;att=get_attempt(s,st.id,e.id)
        rows.append(type('StudentExamRow',(),{'id':e.id,'title':e.title,'display_title':student_exam_display_title(s,e),'duration_minutes':e.duration_minutes,'question_count':display_count,'attempt_status':att.status if att else None,'can_start':allowed,'access_label':access_label,'venue':session_row.venue if session_row else ''})())
    return render_template('student_dashboard.html',student=st,exams=rows)

@app.route('/student/exam/<int:exam_id>')
@student_required
def take_exam(exam_id):
    s=DB();exam=s.scalar(select(Exam).where(Exam.id==exam_id,Exam.is_active==True))
    if not exam:flash('Exam is not active.','error');return redirect(url_for('student_dashboard'))
    allowed,access_label,_session=exam_access_for_student(s,web_session['user_id'],exam)
    if not allowed:flash(access_label,'error');return redirect(url_for('student_dashboard'))
    cfg=get_exam_config(s,exam_id);attempt=get_attempt(s,web_session['user_id'],exam_id)
    if attempt and attempt.status=='submitted':return redirect(url_for('submitted',exam_id=exam_id))
    if not attempt:
        qids=list(s.scalars(select(Question.id).where(Question.exam_id==exam_id).order_by(Question.id)).all())
        if not qids:flash('This exam has no questions.','error');return redirect(url_for('student_dashboard'))
        target=min((cfg.question_count if cfg and cfg.question_count else len(qids)),len(qids))
        if cfg is None or cfg.randomize_questions:qids=random.sample(qids,target)
        else:qids=qids[:target]
        started=now_dt();end=started+timedelta(minutes=exam.duration_minutes)
        if _session and _session.scheduled_end:
            session_end=datetime.fromisoformat(_session.scheduled_end).astimezone() if datetime.fromisoformat(_session.scheduled_end).tzinfo else datetime.fromisoformat(_session.scheduled_end).replace(tzinfo=started.tzinfo)
            if session_end<end:end=session_end
        attempt=Attempt(student_id=web_session['user_id'],exam_id=exam_id,started_at=started.isoformat(timespec='seconds'),end_at=end.isoformat(timespec='seconds'),status='in_progress',question_order=','.join(map(str,qids)));s.add(attempt);s.flush()
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
    return render_template('submitted.html',exam=exam,display_title=student_exam_display_title(s,exam),attempt=attempt,violations=violations,percentage=percentage,grade=grade,grade_class=grade_class,answer_review_exam_id=exam.id if attempt.status=='submitted' else None)

@app.route('/student/submitted/<int:exam_id>/answers')
@student_required
def submitted_answers(exam_id):
    s=DB();exam=s.get(Exam,exam_id);attempt=get_attempt(s,web_session['user_id'],exam_id)
    # Answer review is deliberately available only after this student's exam has been submitted.
    if not exam or not attempt or attempt.status!='submitted':abort(404)

    aq_rows=s.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id==attempt.id).order_by(AttemptQuestion.position)).all()
    if aq_rows:
        ordered=[(row.position,row.question_id,row.option_order or 'ABCD') for row in aq_rows]
    else:
        ordered=[(pos,qid,'ABCD') for pos,qid in enumerate(attempt_question_ids(s,attempt),1)]

    qids=[qid for _pos,qid,_order in ordered]
    qrows=s.scalars(select(Question).where(Question.id.in_(qids))).all() if qids else []
    qmap={q.id:q for q in qrows}
    saved=s.scalars(select(Answer).where(Answer.attempt_id==attempt.id)).all()
    amap={a.question_id:a.selected_answer for a in saved}
    views=[]

    for position,qid,option_order in ordered:
        q=qmap.get(qid)
        if not q:continue
        text={'A':q.option_a,'B':q.option_b,'C':q.option_c,'D':q.option_d}
        order=option_order if len(option_order)==4 and set(option_order)==set('ABCD') else 'ABCD'
        display_label={key:chr(65+i) for i,key in enumerate(order)}
        student_key=amap.get(q.id)
        correct_key=q.correct_answer
        options=[]
        for i,key in enumerate(order):
            options.append(type('AnswerOptionView',(),{
                'label':chr(65+i),
                'key':key,
                'text':text[key],
                'is_student':student_key==key,
                'is_correct':correct_key==key,
            })())
        views.append(type('AnswerReviewView',(),{
            'position':position,
            'question':q.question,
            'marks':q.marks,
            'student_key':student_key,
            'student_label':display_label.get(student_key,'') if student_key else '',
            'student_text':text.get(student_key,'') if student_key else '',
            'correct_key':correct_key,
            'correct_label':display_label.get(correct_key,correct_key),
            'correct_text':text.get(correct_key,''),
            'is_correct':bool(student_key and student_key==correct_key),
            'options':options,
        })())

    return render_template('submitted_answers.html',exam=exam,display_title=student_exam_display_title(s,exam),attempt=attempt,questions=views,answer_review_exam_id=exam.id)

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
