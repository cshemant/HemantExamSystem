import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
ADMIN=(ROOT/'templates'/'attendance_sessions.html').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'attendance_session_detail.html').read_text(encoding='utf-8')
STUDENT=(ROOT/'templates'/'student_attendance_session.html').read_text(encoding='utf-8')
JS=(ROOT/'static'/'attendance.js').read_text(encoding='utf-8')

class AttendanceV107StaticTests(unittest.TestCase):
    def test_models_exist(self):
        for name in ['class AttendanceSession','class AttendanceRecord','class StudentPasskey']:
            self.assertIn(name,APP)
    def test_staff_routes_exist(self):
        for route in ["'/admin/attendance'","'/admin/attendance/<int:session_id>'","'/admin/attendance/<int:session_id>/export.csv'","'/admin/attendance/devices'"]:
            self.assertIn(route,APP)
    def test_student_routes_exist(self):
        for route in ["'/student/attendance'","'/student/passkeys/register/options'","'/student/attendance/<int:session_id>/auth/options'","'/student/attendance/<int:session_id>/mark'"]:
            self.assertIn(route,APP)
    def test_network_and_time_guards_exist(self):
        self.assertIn('def _attendance_network_check',APP)
        self.assertIn("attendance_state(row)!='active'",APP)
        self.assertIn('def _attendance_validate_claim',APP)
        self.assertIn('def _attendance_validate_qr_token',APP)
    def test_passkey_verification_is_server_side(self):
        self.assertIn('key.verify(signature,signed',APP)
        self.assertIn("userVerification':'required'",APP)
        self.assertIn('public_key_pem',APP)
        self.assertNotIn('fingerprint_template',APP)
    def test_ui_navigation_exists(self):
        self.assertIn("url_for('attendance_sessions')",BASE)
        self.assertIn("url_for('student_attendance')",BASE)
        self.assertIn('Approved CIDRs',ADMIN)
        self.assertIn('Room Attendance QR',DETAIL)
        self.assertIn('Verify fingerprint / passkey',STUDENT)
    def test_client_webauthn_calls_exist(self):
        self.assertIn('navigator.credentials.create',JS)
        self.assertIn('navigator.credentials.get',JS)
        self.assertIn('X-CSRF-Token',JS)

if __name__=='__main__':unittest.main()
