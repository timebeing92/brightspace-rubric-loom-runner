# Rubric Loom adoption map

| Concern | Authority | Runner treatment |
| --- | --- | --- |
| Rubric schemas and normalization | `coursecraft_workbench` | Never reimplemented |
| Brightspace rubric extraction | `coursecraft_workbench`, promoted through `brightspace-rubric-bundle` | Invoked through the bundle’s Unravel orchestrator |
| Scoring policy, rubric XML, and package validation | `coursecraft_workbench`, promoted through `brightspace-rubric-bundle` | Invoked through the bundle’s Weave orchestrator |
| Guided Unravel/Weave terminal journey | `brightspace-rubric-bundle` | Launched as the pinned engine |
| Release pairing and provenance manifest | `brightspace-rubric-loom-runner` | Owned here |
| Environment discovery and private dependency setup | Runner launcher plus bundle bootstrap | Composed here; dependencies remain bundle-pinned |
| Update download, verification, activation, and rollback | `brightspace-rubric-loom-runner` | Owned here |
| Inputs, outputs, state, logs, and private environment | User-controlled `user-data/` | Preserved across activation and rollback |
| Hosted Workshop presentation | `coursecraft-workshop-space` | Separate consumer of the same bundle family |

## Permitted adaptation

Runner code may validate releases, supervise the bundle’s terminal entry
point, consume its exit status, and present its producer-reported results.
Runner code may not parse D2L rubric XML, infer scoring, normalize authoring
sources, construct packages, or redefine the bundle’s contracts.

## Release trace

Each release must contain:

1. the exact runner and bundle commits;
2. the bundle version;
3. SHA-256 receipts for critical runner and bundle runtime files;
4. the four rubric-family contract receipts;
5. explicit Unravel and Weave capability records;
6. the AGPL and commercial-terms references; and
7. this adoption map and `NOTICE.md`.
