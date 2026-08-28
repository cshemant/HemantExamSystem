import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')


class PracticalFeatureStaticTests(unittest.TestCase):
    def test_practical_models_exist(self):
        for model in ['PracticalRegister','PracticalStudent','PracticalExperiment','PracticalMark']:
            self.assertIn(f'class {model}(Base):',APP)

    def test_practical_routes_exist(self):
        required={
            '/admin/practicals',
            '/admin/practicals/<int:register_id>',
            '/admin/practicals/<int:register_id>/delete',
            '/admin/practicals/<int:register_id>/students/import',
            '/admin/practicals/<int:register_id>/experiments/import',
            '/admin/practicals/<int:register_id>/mark-entry',
            '/admin/practicals/<int:register_id>/marks/save',
            '/admin/practicals/<int:register_id>/marks/bulk',
            '/admin/practicals/<int:register_id>/marks-settings',
            '/admin/practicals/<int:register_id>/export/<fmt>',
        }
        tree=ast.parse(APP);routes=set()
        for node in ast.walk(tree):
            if not isinstance(node,ast.FunctionDef):continue
            for dec in node.decorator_list:
                if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr=='route' and dec.args and isinstance(dec.args[0],ast.Constant):
                    routes.add(dec.args[0].value)
        self.assertTrue(required.issubset(routes),required-routes)

    def test_owner_scope_is_enforced(self):
        self.assertIn("if current_staff_role(s)=='super_admin'",APP)
        self.assertIn('row.owner_type!=owner_type or row.owner_id!=owner_id',APP)
        self.assertIn("PRACTICAL_ROLES={'super_admin','hod','faculty'}",APP)

    def test_live_entry_assets_exist(self):
        for name in ['practical_registers.html','practical_register_detail.html','practical_mark_entry.html']:
            self.assertTrue((ROOT/'templates'/name).exists(),name)
        js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
        self.assertIn('initPracticalMarks',js)
        self.assertIn('data-practical-entry', (ROOT/'templates'/'practical_mark_entry.html').read_text(encoding='utf-8'))

    def test_component_marking_fields_exist(self):
        for field in ['attendance_max_marks','record_max_marks','performance_max_marks','viva_max_marks','attendance_marks','record_marks','performance_marks','viva_marks']:
            self.assertIn(field,APP)
        template=(ROOT/'templates'/'practical_mark_entry.html').read_text(encoding='utf-8')
        for label in ['Attendance / {{ component_maxima.attendance }}','Record / {{ component_maxima.record }}','Performance / {{ component_maxima.performance }}','Viva / {{ component_maxima.viva }}','Total / {{ total_max }}']:
            self.assertIn(label,template)
        self.assertNotIn('<h1>Live Practical Marks</h1>',template)
        self.assertIn('<h1>{{ register.subject }}</h1>',template)

    def test_global_marks_settings_exist(self):
        template=(ROOT/'templates'/'practical_register_detail.html').read_text(encoding='utf-8')
        self.assertIn('Marks Distribution',template)
        self.assertIn("url_for('practical_marks_settings'",template)
        self.assertIn('Attendance Max',template)
        self.assertIn('Record Max',template)
        self.assertIn('Performance Max',template)
        self.assertIn('Viva Max',template)


    def test_practical_register_delete_requires_confirmation(self):
        template=(ROOT/'templates'/'practical_registers.html').read_text(encoding='utf-8')
        self.assertIn("url_for('delete_practical_register'",template)
        self.assertIn('Delete this entire practical section?',template)
        self.assertIn('class="practical-delete-icon"',template)


    def test_attendance_marks_follow_status(self):
        self.assertIn("if attendance=='P':",APP)
        self.assertIn("component_values['attendance']=float(maxima['attendance'])",APP)
        self.assertIn("if attendance=='A':total=0.0",APP)
        js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
        self.assertIn("attendance.value==='A'",js)
        self.assertIn("attendance.value==='P'",js)
        self.assertIn("attendanceInput.value='0'",js)
        self.assertIn("attendanceInput.value=String(attendanceMax)",js)

    def test_practical_detail_circled_helpers_removed(self):
        template=(ROOT/'templates'/'practical_register_detail.html').read_text(encoding='utf-8')
        self.assertNotIn('One global setting for every experiment in this register.',template)
        self.assertNotIn('Upload your university Excel sheet directly.',template)



if __name__=='__main__':unittest.main()
