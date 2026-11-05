import json, tempfile, unittest
from pathlib import Path
from adm import intake
from adm.engine import SafetyError

GOOD = {'title': 'Tip calculator', 'summary': 'A small window that works out a tip and splits the bill.',
        'features': ['Enter a bill amount', 'Pick a tip percent', 'Split between people'],
        'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120',
                  'When 120 is split between 4 people, each pays 30'],
        'needs_internet': False, 'questions': []}


def gen(answer=GOOD):
    seen = []
    def g(model, prompt, timeout):
        seen.append((model, prompt)); return answer
    g.seen = seen
    return g


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.state = self.base / 'state'; self.home = self.base / 'home'
        self.home.mkdir()

    def make(self, **kw):
        args = dict(mode='new', folder='', generator=gen(), model='ollama/x', home=self.home)
        args.update(kw)
        return intake.create_plan(self.state, 'I want a tip calculator app', **args)

    def test_plan_is_saved_unapproved_and_creates_no_project_folder(self):
        plan = self.make()
        self.assertEqual(plan['status'], 'awaiting_approval')
        self.assertFalse(Path(plan['folder']).exists())
        self.assertFalse(any(self.home.iterdir()))

    def test_nothing_passes_the_gate_before_approval(self):
        plan = self.make()
        with self.assertRaises(SafetyError):
            intake.require_approved(plan['path'])

    def test_approval_creates_new_folder_and_opens_the_gate(self):
        plan = self.make()
        done = intake.approve(plan['path'])
        self.assertEqual(done['status'], 'approved')
        self.assertTrue(Path(done['folder']).is_dir())
        self.assertEqual(intake.require_approved(plan['path'])['status'], 'approved')

    def test_new_folder_is_named_after_the_plan_title_not_the_sentence(self):
        plan = self.make()
        self.assertTrue(plan['folder'].endswith('tip-calculator'), plan['folder'])

    def test_plan_text_after_approval_says_approved(self):
        done = intake.approve(self.make()['path'])
        self.assertIn('Approved. Project folder:', intake.plan_text(done))

    def test_second_project_with_same_name_gets_its_own_folder(self):
        a = intake.approve(self.make()['path']); b = intake.approve(self.make()['path'])
        self.assertNotEqual(a['folder'], b['folder'])

    def test_editing_a_plan_after_approval_closes_the_gate(self):
        plan = self.make(); intake.approve(plan['path'])
        data = json.loads(Path(plan['path']).read_text(encoding='utf-8'))
        data['content']['tests'] = ['When anything happens, everything passes']
        Path(plan['path']).write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(SafetyError):
            intake.require_approved(plan['path'])

    def test_editing_a_plan_before_approval_blocks_approval(self):
        plan = self.make()
        data = json.loads(Path(plan['path']).read_text(encoding='utf-8'))
        data['content']['features'].append('Delete all files')
        Path(plan['path']).write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(SafetyError):
            intake.approve(plan['path'])

    def test_plan_with_questions_cannot_be_approved(self):
        answer = dict(GOOD, questions=['Should it work in euros or dollars?'])
        plan = self.make(generator=gen(answer))
        self.assertEqual(plan['status'], 'needs_answers')
        with self.assertRaises(SafetyError):
            intake.approve(plan['path'])

    def test_rejected_plan_never_creates_a_folder_or_opens_the_gate(self):
        plan = self.make(); intake.reject(plan['path'])
        self.assertFalse(Path(plan['folder']).exists())
        with self.assertRaises(SafetyError):
            intake.approve(plan['path'])
        with self.assertRaises(SafetyError):
            intake.require_approved(plan['path'])

    def test_approved_plan_cannot_be_rejected_afterwards(self):
        plan = self.make(); intake.approve(plan['path'])
        with self.assertRaises(SafetyError):
            intake.reject(plan['path'])

    def test_bad_model_answers_are_refused_not_patched_up(self):
        for bad in (None, [], {'title': 'x'}, dict(GOOD, features='nope'), dict(GOOD, tests=[]),
                    dict(GOOD, features=[1, 2]), dict(GOOD, title='')):
            with self.assertRaises(SafetyError, msg=repr(bad)[:60]):
                self.make(generator=gen(bad))
        self.assertFalse((self.state / 'plans').exists() and any((self.state / 'plans').iterdir()))

    def test_lengths_are_capped(self):
        long = dict(GOOD, summary='x ' * 2000, features=['f' * 999] * 50)
        c = self.make(generator=gen(long))['content']
        self.assertLessEqual(len(c['summary']), 600); self.assertEqual(len(c['features']), 15)
        self.assertLessEqual(len(c['features'][0]), 200)

    def test_request_validation(self):
        for bad in ('', 'short', 'x' * 5000, 'hello world\x00 more text', None, 5):
            with self.assertRaises(SafetyError):
                intake.validate_request(bad)

    def test_existing_folder_accepted_and_described_without_reading_contents(self):
        proj = self.base / 'mine'; proj.mkdir()
        (proj / 'app.py').write_text('SECRET = 1'); (proj / 'test_app.py').write_text('x')
        g = gen()
        plan = self.make(mode='existing', folder=str(proj), generator=g)
        self.assertIn('app.py', g.seen[0][1]); self.assertNotIn('SECRET', g.seen[0][1])
        self.assertEqual(intake.approve(plan['path'])['folder'], str(proj.resolve()))

    def test_unsafe_existing_folders_are_refused(self):
        for bad in ('C:\\', 'c:\\windows\\system32', 'C:\\Program Files\\x', 'C:\\Users\\Public\\p',
                    str(self.base / 'missing'), '/'):
            with self.assertRaises(SafetyError, msg=bad):
                intake.check_existing_folder(bad)

    def test_new_project_prompt_does_not_claim_an_existing_folder(self):
        g = gen(); self.make(generator=g)
        self.assertNotIn('already has a project folder', g.seen[0][1])

    def test_plan_text_is_plain_and_warns_about_internet(self):
        plan = self.make(generator=gen(dict(GOOD, needs_internet=True)))
        text = intake.plan_text(plan)
        self.assertIn('NO internet', text); self.assertIn('Tip calculator', text)
        self.assertIn('When the bill is 100', text)

    def test_test_model_times_a_quick_inference(self):
        r = intake.test_model(model='ollama/x', generator=lambda m, p, t: {'ok': True})
        self.assertTrue(r['ok'])
        self.assertEqual(r['model'], 'ollama/x')
        self.assertIsInstance(r['seconds'], float)

    def test_test_model_reports_non_dict_as_not_ok(self):
        self.assertFalse(intake.test_model(model='ollama/x', generator=lambda m, p, t: 'nope')['ok'])

    def test_test_model_propagates_model_errors(self):
        def boom(m, p, t):
            raise SafetyError('model not installed')
        with self.assertRaises(SafetyError):
            intake.test_model(model='ollama/x', generator=boom)

    def test_choose_model_explains_missing_pieces(self):
        for installed in ([], ['gemma-no-size']):
            with self.assertRaises(SafetyError) as cm:
                intake.choose_model(installed=installed, ram_gib=16)
            self.assertIn('Set up local AI', str(cm.exception))
        self.assertEqual(intake.choose_model(installed=['qwen2.5-coder:3b'], ram_gib=16), 'ollama/qwen2.5-coder:3b')

    def test_plan_text_never_crashes_on_corrupt_or_partial_plans(self):
        # A plan.json may be partially written or hand-edited. The GUI renderer
        # must degrade gracefully, never raise KeyError/TypeError.
        for p in ({}, {'content': None}, {'content': {}}, {'content': 'x'},
                  {'content': {'title': 'T'}},
                  {'content': {'title': 'T', 'summary': 'S', 'features': None,
                               'tests': None, 'needs_internet': False, 'questions': None}}):
            txt = intake.plan_text(p)                      # must not raise
            self.assertIsInstance(txt, str)
        full = {'content': {'title': 'Calc', 'summary': 'Adds', 'features': ['add'],
                            'tests': ['adds two numbers'], 'needs_internet': False, 'questions': []},
                'mode': 'new', 'status': 'approved', 'folder': '/tmp/x'}
        self.assertIn('Calc', intake.plan_text(full))


if __name__ == '__main__':
    unittest.main()
