"""Single-file Windows entrypoint: GUI normally, headless supervisor with flag.

The packaged GUI invokes itself with --adm-supervisor. This avoids a missing
python.exe/adm.daemon module when sys.frozen is true. No shell execution.
"""
from __future__ import annotations
import sys

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == '--adm-self-test':
        from adm.selftest import write_smoke_report
        return 0 if write_smoke_report(args[1])['passed'] else 1
    if len(args) >= 2 and args[0] == '--adm-module':
        # Packaged re-entry for ADM's own jobs (allowlisted modules only).
        from adm.pyruntime import ENTRY_MODULES
        if args[1] not in ENTRY_MODULES:
            raise SystemExit('Unknown ADM module: ' + args[1])
        import importlib
        sys.argv = [args[1], *args[2:]]
        entry = importlib.import_module(args[1]).main
        result = entry()
        return result if isinstance(result, int) else 0
    if args and args[0] == '--adm-supervisor':
        from adm.daemon import main as daemon_main
        return daemon_main(args[1:])
    if args:
        raise SystemExit('Unknown desktop arguments: ' + ' '.join(args))
    from adm.desktop import main as desktop_main
    return desktop_main()

if __name__ == '__main__':
    sys.exit(main())
