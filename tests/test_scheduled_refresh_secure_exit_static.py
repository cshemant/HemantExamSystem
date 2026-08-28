import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
DASH=(ROOT/'templates'/'student_dashboard.html').read_text(encoding='utf-8')
VERIFY=(ROOT/'templates'/'exam_pin_verify.html').read_text(encoding='utf-8')
APPJS=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
STYLE=(ROOT/'static'/'style.css').read_text(encoding='utf-8')

class ScheduledRefreshAndSecureExitStaticTests(unittest.TestCase):
    def test_dashboard_uses_one_shot_scheduled_refresh_not_polling(self):
        self.assertIn('auto_refresh_at_epoch=min(auto_refresh_epochs)',APP)
        self.assertIn('server_now_epoch=int(dashboard_now.timestamp())',APP)
        self.assertIn('const refreshAt={{ auto_refresh_at_epoch|int }}',DASH)
        self.assertIn('window.location.reload()',DASH)
        self.assertNotIn('setInterval(',DASH)
        self.assertIn('Math.floor(Math.random()*2500)',DASH)

    def test_secure_exit_never_leaves_blank_guard(self):
        self.assertIn('Exam paused',VERIFY)
        self.assertIn('Return to Exam',VERIFY)
        self.assertIn('fullscreen-reentry-card',STYLE)
        self.assertIn('{navigateOnSubmit:false}',VERIFY)
        self.assertIn("data.type==='secure-exam-submitted'",VERIFY)
        self.assertIn('window.location.replace(url)',VERIFY)

    def test_secure_frame_can_notify_parent_after_auto_submit(self):
        self.assertIn("postMessage({type:'secure-exam-submitted'",APPJS)
        self.assertIn('options.navigateOnSubmit!==false',APPJS)
        self.assertIn('window.top.location.href=resultUrl',APPJS)

if __name__=='__main__':unittest.main()
