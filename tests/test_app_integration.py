import os
import tempfile
import unittest

TEST_DATA=tempfile.mkdtemp(prefix='lwh_exam_test_')
os.environ.update({
    'APP_MODE':'offline',
    'OFFLINE_REQUIRE_SETUP':'0',
    'EXAM_DATA_DIR':TEST_DATA,
    'SECRET_KEY':'test-secret-key-abcdefghijklmnopqrstuvwxyz-123456',
    'SUPER_ADMIN_USERNAME':'testsuperadmin',
    'ADMIN_PASSWORD':'AdminTest@123',
})

import app as exam_app
from sqlalchemy import inspect, select
from werkzeug.security import generate_password_hash


class AppIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.s=exam_app.DB()

    def tearDown(self):
        self.s.rollback()
        exam_app.DB.remove()

    def make_attempt(self,question,answer,roll):
        student=exam_app.Student(roll_no=roll,name='Test Student',password_hash=generate_password_hash('Student@123'),created_at=exam_app.now_iso())
        exam=exam_app.Exam(title='Regression Exam '+roll,duration_minutes=30,is_active=True,created_at=exam_app.now_iso())
        self.s.add_all([student,exam]);self.s.flush();question.exam_id=exam.id;self.s.add(question);self.s.flush()
        attempt=exam_app.Attempt(student_id=student.id,exam_id=exam.id,started_at=exam_app.now_iso(),end_at=(exam_app.now_dt()+exam_app.timedelta(minutes=30)).isoformat(timespec='seconds'),status='in_progress',question_order=str(question.id))
        self.s.add(attempt);self.s.flush();self.s.add(exam_app.AttemptQuestion(attempt_id=attempt.id,question_id=question.id,position=1,option_order='BCAD'));self.s.flush()
        exam_app.save_answer_record(self.s,attempt.id,question.id,answer,question);self.s.commit();exam_app.finalize_attempt(self.s,attempt)
        return attempt,student,exam

    def test_schema_upgrade_columns_exist(self):
        cols={c['name'] for c in inspect(exam_app.engine).get_columns('questions')}
        self.assertTrue({'question_type','answer_key','answer_tolerance','answer_case_sensitive'}.issubset(cols))
        answer_cols={c['name'] for c in inspect(exam_app.engine).get_columns('answers')}
        self.assertTrue({'answer_value','manual_score','grader_comment','graded_by','graded_at'}.issubset(answer_cols))
        attempt_cols={c['name'] for c in inspect(exam_app.engine).get_columns('attempts')}
        self.assertIn('grading_status',attempt_cols)
        bank_cols={c['name'] for c in inspect(exam_app.engine).get_columns('bank_questions')}
        self.assertTrue({'po_mapping','pso_mapping'}.issubset(bank_cols))
        admin_cols={c['name'] for c in inspect(exam_app.engine).get_columns('admins')}
        self.assertTrue({'mfa_secret','mfa_enabled'}.issubset(admin_cols))
        audit_cols={c['name'] for c in inspect(exam_app.engine).get_columns('audit_logs')}
        self.assertTrue({'prev_hash','event_hash'}.issubset(audit_cols))
        tables=set(inspect(exam_app.engine).get_table_names())
        self.assertTrue({'edge_result_receipts','edge_result_attempts','edge_package_receipts'}.issubset(tables))

    def test_single_choice_scoring_survives_option_shuffle(self):
        question=exam_app.Question(exam_id=0,question='Correct is canonical A',option_a='Right',option_b='Wrong',option_c='Wrong',option_d='Wrong',correct_answer='A',question_type='single_choice',answer_key='A',answer_tolerance='',answer_case_sensitive=False,marks=2)
        attempt,_,_=self.make_attempt(question,'A','REG-A-001')
        self.assertEqual(attempt.score,2)
        self.assertEqual(attempt.total_marks,2)

    def test_multiple_select_scoring(self):
        question=exam_app.Question(exam_id=0,question='Select A and C',option_a='A',option_b='B',option_c='C',option_d='D',correct_answer='A',question_type='multiple_select',answer_key='A,C',answer_tolerance='',answer_case_sensitive=False,marks=3)
        attempt,_,_=self.make_attempt(question,'C,A','REG-M-001')
        self.assertEqual(attempt.score,3)

    def test_candidate_checkin_gate(self):
        student=exam_app.Student(roll_no='CHECKIN-001',name='Check In Student',password_hash=generate_password_hash('Student@123'),created_at=exam_app.now_iso());exam=exam_app.Exam(title='Check-in Exam',duration_minutes=20,is_active=True,created_at=exam_app.now_iso());self.s.add_all([student,exam]);self.s.flush()
        policy=exam_app.ExamSecurityPolicy(exam_id=exam.id,require_candidate_checkin=True,heartbeat_seconds=15,updated_at=exam_app.now_iso());self.s.add(policy);self.s.commit()
        allowed,label,_=exam_app.exam_access_for_student(self.s,student.id,exam);self.assertFalse(allowed);self.assertIn('Identity',label)
        self.s.add(exam_app.ExamCandidateCheckin(exam_id=exam.id,student_id=student.id,status='verified',verified_by='test',verified_at=exam_app.now_iso(),notes=''));self.s.commit()
        allowed,_,_=exam_app.exam_access_for_student(self.s,student.id,exam);self.assertTrue(allowed)

    def test_essay_requires_manual_grading_then_recalculates(self):
        question=exam_app.Question(exam_id=0,question='Explain elasticity.',option_a='',option_b='',option_c='',option_d='',correct_answer='A',question_type='essay',answer_key='',answer_tolerance='',answer_case_sensitive=False,marks=5)
        attempt,_,_=self.make_attempt(question,'Elasticity allows resources to scale with demand.','REG-E-001')
        self.assertEqual(attempt.grading_status,'pending')
        self.assertEqual(attempt.score,0)
        answer=self.s.scalar(select(exam_app.Answer).where(exam_app.Answer.attempt_id==attempt.id,exam_app.Answer.question_id==question.id))
        answer.manual_score=4;answer.graded_by='faculty:test';answer.graded_at=exam_app.now_iso();self.s.flush()
        exam_app.recalculate_attempt_score(self.s,attempt)
        self.assertEqual(attempt.grading_status,'complete')
        self.assertEqual(attempt.score,4)


if __name__=='__main__':
    unittest.main()
