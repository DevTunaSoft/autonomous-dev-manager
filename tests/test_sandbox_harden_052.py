import unittest
from adm import sandbox
from adm.sandbox import SandboxError


class HardenTests(unittest.TestCase):
    def test_every_shared_dir_gets_a_deny_rule_for_only_the_sandbox_account(self):
        cmds = sandbox.harden_commands()
        denied = [c[1] for c in cmds]
        for d in sandbox.HARDEN_DIRS:
            self.assertIn(d, denied)
        for c in cmds:
            self.assertEqual(c[0], 'icacls')
            self.assertEqual(c[2], '/deny')
            self.assertTrue(c[3].startswith(sandbox.USER + ':'))

    def test_project_inside_hardened_location_is_refused(self):
        for bad in (r'C:\Users\Public\proj', r'C:\ProgramData', r'c:\programdata\x\y'):
            with self.assertRaises(SandboxError):
                sandbox.refuse_hardened_location(bad)

    def test_normal_project_locations_are_allowed(self):
        for ok in (r'C:\Users\me\Documents\app', r'D:\projects\app'):
            sandbox.refuse_hardened_location(ok)


if __name__ == '__main__':
    unittest.main()
