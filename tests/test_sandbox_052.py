import unittest
from adm import sandbox
from adm.sandbox import SandboxError


class SandboxPureTests(unittest.TestCase):
    def test_password_fits_windows_limit_and_is_random(self):
        a, b = sandbox.new_password(), sandbox.new_password()
        self.assertLessEqual(len(a), 14)
        self.assertNotEqual(a, b)

    def test_setup_commands_target_only_the_sandbox_account(self):
        create, reset = sandbox.setup_commands('Pw1!x')
        self.assertEqual(create[:3], ['net', 'user', sandbox.USER])
        self.assertEqual(reset, ['net', 'user', sandbox.USER, 'Pw1!x'])

    def test_acl_grant_is_modify_not_full_control(self):
        cmd = sandbox.acl_grant_command(r'C:\p')
        self.assertTrue(cmd[-1].endswith('(OI)(CI)M'))

    def test_cmdline_rejects_quotes_and_empty(self):
        for bad in ([], ['a"b'], ['x\x00']):
            with self.assertRaises(SandboxError):
                sandbox.cmdline_for(bad, r'C:\o.txt')

    def test_cmdline_redirects_output(self):
        line = sandbox.cmdline_for(['python.exe', '-c', 'print(1)'], r'C:\o\out.txt')
        self.assertIn('> "C:\\o\\out.txt" 2>&1', line)

    @unittest.skipIf(sandbox.available(), 'non-Windows behavior')
    def test_refuses_to_run_off_windows(self):
        with self.assertRaises(SandboxError):
            sandbox.provision()
        with self.assertRaises(SandboxError):
            sandbox.run_confined(['x'], '.', 'pw')


if __name__ == '__main__':
    unittest.main()
