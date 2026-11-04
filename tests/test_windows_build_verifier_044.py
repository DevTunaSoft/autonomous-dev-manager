"""Contract checks for Windows-only build verifier; NOT Windows runtime acceptance."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class WindowsBuildVerifierContractTests(unittest.TestCase):
    def test_batch_calls_bounded_powershell_verifier(self):
        script = (ROOT / 'BUILD-WINDOWS-DESKTOP.cmd').read_text()
        self.assertIn('VERIFY-WINDOWS-DESKTOP.ps1', script)
        self.assertIn('-TimeoutSeconds 60', script)
        self.assertIn('if errorlevel 1', script)
    def test_verifier_requires_real_exit_and_json(self):
        script = (ROOT / 'VERIFY-WINDOWS-DESKTOP.ps1').read_text()
        for required in ('WaitForExit(', 'Kill($true)', '$process.ExitCode',
                         'ConvertFrom-Json', 'ADM-packaged-smoke-v1',
                         'Get-FileHash', 'SHA256', 'exit 1', 'Remove-Item',
                         'build-verification-v1'):
            self.assertIn(required, script)
    def test_workflow_keeps_evidence_even_on_failure(self):
        script = (ROOT / '.github/workflows/windows-desktop-build.yml').read_text()
        self.assertIn('if: always()', script)
        self.assertIn('ADM-Windows-build-evidence', script)
        self.assertIn('VERIFY-WINDOWS-DESKTOP.ps1', script)
        self.assertIn('if-no-files-found: error', script)

if __name__ == '__main__': unittest.main()
