import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'attendance_session_detail.html').read_text(encoding='utf-8')
STUDENT=(ROOT/'templates'/'student_attendance_session.html').read_text(encoding='utf-8')
SESSIONS=(ROOT/'templates'/'attendance_sessions.html').read_text(encoding='utf-8')
DASH=(ROOT/'templates'/'student_dashboard.html').read_text(encoding='utf-8')
LIST=(ROOT/'templates'/'student_attendance.html').read_text(encoding='utf-8')

class RotatingRoomQrAttendanceTests(unittest.TestCase):
    def test_rotating_presence_constants_exist(self):
        self.assertIn("ATTENDANCE_QR_ROTATION_SECONDS",APP)
        self.assertIn("'45'",APP)
        self.assertIn("ATTENDANCE_COMPLETION_SECONDS",APP)
        self.assertIn("'120'",APP)

    def test_rotating_qr_room_code_and_claim_helpers_exist(self):
        for name in ['_attendance_qr_token','_attendance_validate_qr_token','_attendance_room_code','_attendance_validate_room_code','_attendance_claim_token','_attendance_validate_claim']:
            self.assertIn(f'def {name}',APP)

    def test_room_code_claim_route_exists(self):
        self.assertIn("'/student/attendance/<int:session_id>/room-code'",APP)
        self.assertIn("_attendance_claim_token(row,student.id)",APP)

    def test_static_access_token_is_not_exposed_to_student_links(self):
        self.assertNotIn('token=a.access_token',DASH)
        self.assertNotIn('token=r.access_token',LIST)

    def test_faculty_ui_has_rotating_room_qr_and_code(self):
        self.assertIn('Room Attendance QR',DETAIL)
        self.assertIn('Room Code',DETAIL)
        self.assertIn('changes every',DETAIL)
        self.assertNotIn('Copy Attendance Link',DETAIL)

    def test_student_completion_flow_uses_room_presence(self):
        self.assertIn('Room presence',STUDENT)
        self.assertIn('student_attendance_room_code',STUDENT)
        self.assertIn('Register once on this device. Your first successful registration will also mark this attendance.',STUDENT)
        self.assertIn('network_preverified=True',APP)

    def test_shorter_default_attendance_window(self):
        self.assertIn('<option value="3">3 minutes</option>',SESSIONS)
        self.assertIn('<option value="5" selected>5 minutes</option>',SESSIONS)

if __name__=='__main__':
    unittest.main()
