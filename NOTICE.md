# Attribution and provenance

Rubric Loom Runner is a CourseCraft Workbench-family distribution maintained
by Erik Hanson.

CourseCraft Workbench is the upstream living library and development lab for
the CourseCraft tool family. It curates authoritative development copies of
shared schemas and producer code alongside scripts, tests, experiments,
technical writing, and documentation. Only reviewed, verified,
production-ready versions are promoted into pinned downstream products.

The runner’s release, installation, and rollback mechanics were adapted from
the Workbench-owned `brightspace-blueprint-runner`. Rubric Loom terminal art
and appropriate user documentation were adapted from the Workbench-owned
`brightspace-rubric-bundle`.

Every published Rubric Loom runner ZIP pairs this repository with one exact
`brightspace-rubric-bundle` commit. `RELEASE_MANIFEST.json` records both
repository identities and commits, critical runtime SHA-256 digests, contract
digests, capabilities, licensing records, and the persistent user-data
boundary.

The Rubric Bundle retains the deeper producer provenance, including its
Workbench adoption pin and byte-level inventory, in
`upstream/workbench_pin.json`. The runner intentionally references that record
instead of duplicating or weakening it.

The initial adaptation was authorized against the Workbench-owned source
inventory at commit `51d9077e5bb7378bbb7bcb6a75d50f0c5250bc4b`.
