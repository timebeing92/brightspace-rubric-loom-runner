# Bounded launcher recovery and exact pairing

The ecosystem review reproduced a hang in both shell entry points before the
stable launcher's five-second Python probe could run. The owner authorized
fixes and a validated Rubric/Loom release pair; quiz products and hosted spaces
are explicitly excluded.

Share one bounded probe within each native shell family. Keep the existing
private-runtime preference and fallback order. POSIX recovery must not require
GNU timeout or another working Python. Windows must work in both PowerShell
5.1 and PowerShell 7, preserve paths and arguments, and drain probe output.
Include both helper files in the release's critical-runtime receipts.

Exercise actual managed and portable entry points with real healthy, missing,
broken, unsupported, and hung private interpreters. Test paths containing
spaces and ampersands and forward user arguments without interpretation.
Keep Windows cases native in CI rather than claiming them from source review.

Prepared CI selects the exact bundle commit before its release tag exists.
Released compatibility continues to select the tag and check the exact commit.
After the corrected bundle release is verified, update the runner's pairing
to its final immutable commit and complete reproducible archive/health checks.
Do not change parser, rubric semantic, or progress-envelope ownership.
