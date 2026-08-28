import ast
import difflib
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
DETAIL=(ROOT/'templates'/'practical_register_detail.html').read_text(encoding='utf-8')
CODE=(ROOT/'templates'/'practical_code.html').read_text(encoding='utf-8')


def test_reference_code_storage_and_upgrade_exist():
    assert "reference_code:Mapped[str]=mapped_column(Text,nullable=False,default='')" in APP
    assert "('practical_experiments','reference_code',\"TEXT NOT NULL DEFAULT ''\")" in APP
    assert 'class PracticalCodeSubmission(Base):' in APP


def test_student_link_is_conditional():
    assert 'practical_code_available' in BASE
    assert "url_for('student_practical_code')" in BASE
    assert BASE.count('Practical Marks') >= 2


def test_exact_experiment_and_roll_mapping_is_used():
    assert 'def resolve_practical_target_for_student' in APP
    assert 'PracticalExperiment.experiment_no==target_experiment' in APP
    assert 'practical_roll_key!=registration_key' in APP
    assert 'practical_target_not_unique' in APP


def test_performance_mark_is_written_not_viva():
    assert 'mark.performance_marks=performance_value' in APP
    assert "updated_by='Practical Code'" in APP
    assert 'practical_code_auto_evaluated' in APP


def test_student_code_is_compared_but_never_executed():
    assert 'def evaluate_practical_code' in APP
    assert 'difflib.SequenceMatcher' in APP
    assert 'exec(source' not in APP
    assert 'eval(source' not in APP


def test_reference_code_admin_action_exists():
    assert "url_for('practical_reference_code'" in DETAIL
    assert 'Add Code' in DETAIL and 'Edit Code' in DETAIL


def test_student_template_has_paste_and_submit_flow():
    assert 'name="source_code"' in CODE
    assert 'Evaluate &amp; Save Performance' in CODE
    assert 'reference_code' in CODE


def test_similarity_exact_match_is_full_score_and_short_snippet_is_penalized():
    tree=ast.parse(APP)
    wanted={'_strip_code_comments','_code_tokens','_code_semantic_tokens','_code_behavior_tokens','evaluate_practical_code'}
    body=[]
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='PRACTICAL_CODE_LANGUAGE_KEYWORDS' for t in n.targets): body.append(n)
        if isinstance(n,ast.FunctionDef) and n.name in wanted: body.append(n)
    mod=ast.Module(body=body,type_ignores=[]);ast.fix_missing_locations(mod)
    ns={'re':re,'difflib':difflib}
    exec(compile(mod,'<similarity>','exec'),ns)
    ref='public class Main { public static void main(String[] args) { System.out.println("Hello"); } }'
    assert ns['evaluate_practical_code'](ref,ref) > .999
    assert ns['evaluate_practical_code'](ref,'System.out.println("Hi");') < .35


def test_similarity_ignores_variable_and_android_resource_id_names_but_keeps_api_behavior():
    tree=ast.parse(APP)
    wanted={'_strip_code_comments','_code_tokens','_code_semantic_tokens','_code_behavior_tokens','evaluate_practical_code'}
    body=[]
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='PRACTICAL_CODE_LANGUAGE_KEYWORDS' for t in n.targets): body.append(n)
        if isinstance(n,ast.FunctionDef) and n.name in wanted: body.append(n)
    mod=ast.Module(body=body,type_ignores=[]);ast.fix_missing_locations(mod)
    ns={'re':re,'difflib':difflib}
    exec(compile(mod,'<identifier-tolerant-similarity>','exec'),ns)
    evaluate=ns['evaluate_practical_code']
    reference='toggleButton = findViewById(R.id.toggleButton);'
    renamed='myButton = findViewById(R.id.my_toggle);'
    wrong_api='myButton = setText(R.id.my_toggle);'
    assert evaluate(reference,renamed) > .999
    assert evaluate(reference,wrong_api) < .80


def test_student_penalty_detail_is_private():
    assert '(exact-match deduction:' not in APP
    assert 'penalty=' in APP  # remains in staff audit detail


def test_student_practical_marks_label_and_score_are_visible():
    assert '<h1>Practical Marks</h1>' in CODE
    assert 'Performance Marks: <strong>' in CODE
