import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BUILDER=(ROOT/'templates'/'exam_builder.html').read_text(encoding='utf-8')
ACCESS=(ROOT/'templates'/'exam_student_access.html').read_text(encoding='utf-8')
SUBMITTED=(ROOT/'templates'/'submitted.html').read_text(encoding='utf-8')
APPJS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
EXAMS=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')

class PracticalAntiCheatingStaticTests(unittest.TestCase):
    def test_security_policy_fields_exist(self):
        for token in [
            'strict_start_window:Mapped[bool]',
            'start_grace_minutes:Mapped[int]',
            'auto_submit_on_integrity_limit:Mapped[bool]',
            'defer_results_until_end:Mapped[bool]',
            'block_ip_roll_switch:Mapped[bool]',
            'practical_defaults_applied:Mapped[bool]',
        ]:
            self.assertIn(token,APP)

    def test_practical_defaults_enable_required_controls(self):
        self.assertIn('def apply_practical_exam_security_defaults',APP)
        self.assertIn('cfg.randomize_questions=True',APP)
        self.assertIn('cfg.shuffle_options=True',APP)
        self.assertIn('cfg.require_fullscreen=True',APP)
        self.assertIn('cfg.tab_switch_limit=3',APP)
        self.assertIn('security.require_exam_pin=True',APP)
        self.assertIn('security.strict_start_window=True',APP)
        self.assertIn('security.auto_submit_on_integrity_limit=True',APP)
        self.assertIn('security.defer_results_until_end=True',APP)
        self.assertIn('security.block_ip_roll_switch=True',APP)

    def test_builder_exposes_secure_defaults(self):
        for field in ['require_fullscreen','require_exam_pin','strict_start_window','auto_submit_on_integrity_limit','defer_results_until_end','block_ip_roll_switch','start_grace_minutes']:
            self.assertIn(f'name="{field}"',BUILDER)
        self.assertIn('Practical Exam secure defaults',BUILDER)
        self.assertIn('Secure defaults:',EXAMS)

    def test_integrity_auto_submit_and_warnings_exist(self):
        self.assertIn('exam_auto_submitted_integrity',APP)
        self.assertIn('Final warning: one more integrity violation',APP)
        self.assertIn("finalize_attempt(s,attempt)",APP)
        self.assertIn("['warning','final_warning']",APPJS)
        self.assertIn('data.submitted',APPJS)

    def test_result_release_is_deferred(self):
        self.assertIn('def exam_result_release_at',APP)
        self.assertIn('results_released=results_released',APP)
        self.assertIn('Answer review will be available after',APP)
        self.assertIn('Result locked',SUBMITTED)

    def test_ip_roll_session_lock_exists_and_can_be_reset(self):
        self.assertIn('class ExamIPSessionLock(Base):',APP)
        self.assertIn('def ensure_exam_ip_session_lock',APP)
        self.assertIn('You have already logged in with a roll number for this session.',APP)
        self.assertIn('reset-ip-locks',APP)
        self.assertIn('Reset IP Locks',ACCESS)
        self.assertIn('Shared Wi-Fi/NAT',ACCESS)

if __name__=='__main__':
    unittest.main()
