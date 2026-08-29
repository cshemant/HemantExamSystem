import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
ADMIN=(ROOT/'templates'/'attendance_sessions.html').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'attendance_session_detail.html').read_text(encoding='utf-8')

class WifiAttendanceTests(unittest.TestCase):
    def test_wifi_and_lan_are_separate_modes(self):
        self.assertIn('Same Wi-Fi', ADMIN)
        self.assertIn('Same LAN (offline server)', ADMIN)
        self.assertNotIn('Same classroom LAN / Wi-Fi', ADMIN)
        self.assertIn("{'wifi','lan','cidr','any'}", APP)

    def test_online_defaults_to_wifi(self):
        self.assertIn("'lan' if APP_MODE=='offline' else 'wifi'", APP)

    def test_wifi_anchor_and_check_exist(self):
        self.assertIn('def _attendance_wifi_anchor', APP)
        self.assertIn("if mode=='wifi':", APP)
        self.assertIn('Same Wi-Fi verified', APP)
        self.assertIn('same Wi-Fi used by the faculty member', APP)

    def test_detail_labels_wifi_separately(self):
        self.assertIn("session.network_mode=='wifi'", DETAIL)
        self.assertIn("'Same Wi-Fi'", DETAIL)

if __name__=='__main__':
    unittest.main()
