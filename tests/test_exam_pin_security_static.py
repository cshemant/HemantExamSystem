import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BUILDER=(ROOT/'templates'/'exam_builder.html').read_text(encoding='utf-8')
ACCESS=(ROOT/'templates'/'exam_student_access.html').read_text(encoding='utf-8')
VERIFY=(ROOT/'templates'/'exam_pin_verify.html').read_text(encoding='utf-8')
EXAM=(ROOT/'templates'/'exam.html').read_text(encoding='utf-8')
STYLE=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
APPJS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
LOGIN=(ROOT/'templates'/'login.html').read_text(encoding='utf-8')

class ExamPinSecurityStaticTests(unittest.TestCase):
    def test_models_and_policy_exist(self):
        self.assertIn("class ExamStudentAccess(Base):",APP)
        self.assertIn("class ExamDeviceLock(Base):",APP)
        self.assertIn("require_exam_pin:Mapped[bool]",APP)

    def test_pin_and_device_routes_exist(self):
        self.assertIn("/student/exam/<int:exam_id>/verify-pin",APP)
        self.assertIn("/admin/exam/<int:exam_id>/student-access",APP)
        self.assertIn("reset-device",APP)

    def test_secure_exam_blocks_unverified_and_other_device(self):
        self.assertIn("exam_pin_is_verified(exam_id)",APP)
        self.assertIn("ensure_exam_device_lock(s,exam_id,web_session['user_id'])",APP)
        self.assertIn("secure_exam_device_allowed(s,attempt)",APP)

    def test_rotating_pin_changes_every_minute(self):
        self.assertIn("ROTATING_EXAM_PIN_SECONDS=60",APP)
        self.assertIn("def rotating_exam_pin(",APP)
        self.assertIn("/student/exam/<int:exam_id>/current-pin",APP)

    def test_secure_exam_submission_escapes_frame_to_result(self):
        self.assertIn('target="_top"',EXAM)
        self.assertIn('data-secure-shell',EXAM)
        self.assertIn('window.top.location.href=resultUrl',APPJS)

    def test_secure_exam_starts_with_first_question_visible(self):
        self.assertIn('body.secure-exam-shell-page .exam-head{top:0}',STYLE)
        self.assertIn("frame.contentWindow.scrollTo(0,0)",VERIFY)

    def test_admin_ui_and_student_verification_exist(self):
        self.assertIn('require_exam_pin',BUILDER)
        self.assertIn('Student Access',BUILDER)
        self.assertIn('Device Locks',ACCESS)
        self.assertIn('Reset Device',ACCESS)
        self.assertIn('6-digit Exam PIN',VERIFY)
        self.assertIn('rotating-exam-pin',VERIFY)
        self.assertIn('Password',LOGIN)
        self.assertNotIn('Password / Exam PIN',LOGIN)

if __name__=='__main__':unittest.main()
