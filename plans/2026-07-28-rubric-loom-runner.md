# Rubric Loom Runner v1.0.0

## Goal

Create a colleague-facing, one-download Rubric Loom application analogous to
Blueprint Wizard while keeping rubric semantics in
`brightspace-rubric-bundle`.

The initial runner release pairs with Rubric Bundle `v1.3.1`. The exact
annotated tag commit is recorded in the compatibility lock and each release
manifest after the bundle compatibility PR is merged.

## Architecture

```text
coursecraft_workbench -> brightspace-rubric-bundle
                                      |-> brightspace-rubric-loom-runner
                                      `-> coursecraft-workshop-space
```

The runner may validate releases, supervise processes, consume progress events,
and present producer outputs. It may not interpret rubric evidence itself.

## User package

The recommended managed ZIP contains:

```text
Rubric Loom.command
Rubric Loom.bat
START_HERE.txt
current.json
launcher/
versions/1.0.0/
  brightspace-rubric-loom-runner/
  brightspace-rubric-bundle/
  RELEASE_MANIFEST.json
user-data/
```

The portable ZIP contains the same exact runner/bundle pair in one versioned
folder with top-level launchers and `START_HERE.txt`.

## Work

1. Parameterize the runner against an explicit bundle directory and persistent
   user-data root.
2. Add macOS, Windows, and Linux launchers with private-environment setup.
3. Adapt the stable install/update/rollback model without copying rubric
   semantics.
4. Build deterministic portable and managed ZIPs from explicit refs.
5. Record exact repository commits, bundle version, runtime digests,
   capabilities, and licensing in a compact release manifest.
6. Test path containment, archive shape, checksum verification, interrupted
   activation, rollback preservation, launcher forwarding, and semantic
   boundaries.
7. Publish v1.0.0 only after local and GitHub checks pass.

## Transition

Rubric Bundle `v1.3.1` remains available for Workshop and technical consumers.
Once the runner is verified, ordinary download guidance moves to the runner.
The bundle's existing terminal entry point remains compatible during the
transition.
