import unittest
from types import SimpleNamespace

from enterprise_core import canonical_question_type, normalize_answer, is_answer_correct, validate_question_definition


def q(**kwargs):
    base=dict(question_type='single_choice',answer_key='A',correct_answer='A',answer_tolerance='',answer_case_sensitive=False)
    base.update(kwargs)
    return SimpleNamespace(**base)


class EnterpriseScoringTests(unittest.TestCase):
    def test_legacy_mcq_maps_to_single_choice(self):
        self.assertEqual(canonical_question_type('MCQ'),'single_choice')

    def test_shuffled_display_does_not_change_canonical_correct_key(self):
        question=q(answer_key='A')
        # A may be displayed as C after shuffling, but the stored browser value remains canonical A.
        self.assertTrue(is_answer_correct(question,'A'))
        self.assertFalse(is_answer_correct(question,'B'))

    def test_multiple_select_is_order_independent(self):
        question=q(question_type='multiple_select',answer_key='A,C')
        self.assertEqual(normalize_answer(question,'C,A'),'A,C')
        self.assertTrue(is_answer_correct(question,'C,A'))
        self.assertFalse(is_answer_correct(question,'A'))

    def test_true_false(self):
        question=q(question_type='true_false',answer_key='true')
        self.assertTrue(is_answer_correct(question,'TRUE'))
        self.assertFalse(is_answer_correct(question,'false'))

    def test_numerical_tolerance(self):
        question=q(question_type='numerical',answer_key='9.81',answer_tolerance='0.02')
        self.assertTrue(is_answer_correct(question,'9.80'))
        self.assertFalse(is_answer_correct(question,'9.70'))

    def test_short_text_alternatives_case_insensitive(self):
        question=q(question_type='short_text',answer_key='ART|Android Runtime')
        self.assertTrue(is_answer_correct(question,'android   runtime'))
        self.assertTrue(is_answer_correct(question,'art'))

    def test_validation_rejects_invalid_numerical_key(self):
        error=validate_question_definition('numerical','Value of g?',{},'not-a-number','0.1')
        self.assertIsNotNone(error)

    def test_essay_is_preserved_for_manual_grading(self):
        q=SimpleNamespace(question_type='essay',answer_key='',answer_tolerance='',answer_case_sensitive=False)
        self.assertEqual(normalize_answer(q,'  First paragraph.\n\nSecond paragraph.  '),'First paragraph.\n\nSecond paragraph.')
        self.assertFalse(is_answer_correct(q,'Any descriptive response'))

    def test_essay_definition_requires_no_answer_key(self):
        self.assertIsNone(validate_question_definition('essay','Explain cloud elasticity.',{'A':'','B':'','C':'','D':''},''))


if __name__=='__main__':
    unittest.main()
