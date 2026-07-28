# Repository instructions

## Product boundary

This repository owns the colleague-facing Rubric Loom runner:

- macOS, Windows, and Linux launchers;
- guided terminal presentation and user-language flow;
- environment setup;
- persistent user data, logs, update state, and outputs;
- exact runner/bundle compatibility;
- portable and managed release ZIPs;
- update, activation, rollback, and cleanup safety.

`brightspace-rubric-bundle` remains the deterministic producer. This runner
must not parse D2L XML, normalize or score rubrics, construct package XML,
validate rubric semantics, or invent a second progress or receipt contract.
It invokes exact bundle entry points and consumes their declared outputs and
`coursecraft.progress/1` events.

## User release boundary

The ordinary user path begins at top-level launchers and `START_HERE.txt`.
Internal Workbench pins and producer provenance remain machine-verifiable
inside the paired runtime; do not place commit inventories or engineering
governance in user onboarding.

Every release must:

- be built from explicit clean runner and bundle refs;
- contain an exact compatible pair;
- preserve AGPL-3.0-or-later and the family commercial terms;
- include a compact machine-readable release manifest;
- include independent checksum sidecars;
- keep persistent user data outside replaceable version directories;
- refuse incomplete, mismatched, unsafe, or path-escaping archives;
- pass the full test suite before tagging or publication.

## Privacy

Never commit real course exports, institutional rubrics, learner records,
tenant identifiers, tokens, cookies, or generated user outputs. Fixtures must
be synthetic and clearly labeled.

## Verification

Before committing implementation changes, run:

```bash
python3 -m pytest
python3 scripts/make_portable_release.py --runner-ref HEAD --bundle-ref <exact-ref>
python3 scripts/make_managed_release.py --runner-ref HEAD --bundle-ref <exact-ref>
```

Release construction and public publication remain separate claims.
