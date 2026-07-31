# Install, update, and troubleshoot Rubric Loom

This guide covers the recommended managed release, first launch, verified
updates, rollback, and the most common installation or run problems.

## Install the managed release

1. Open the
   [Rubric Loom Releases page](https://github.com/timebeing92/brightspace-rubric-loom-runner/releases).
   On the repository page, **Releases** is also available from the repository
   sidebar.
2. Open the latest release and expand **Assets** if necessary.
3. Download `rubric-loom-managed-v<VERSION>.zip`.
   Do **not** download GitHub's automatically generated **Source code** ZIP,
   and do not use the green **Code > Download ZIP** button. Those archives
   contain this runner repository but omit the paired Rubric Bundle engine.
4. Unzip the managed release before opening it.
5. Start the Loom:

   - **macOS:** double-click `Rubric Loom.command`.
   - **Windows:** double-click `Rubric Loom.bat`.
   - **Linux:** run `bash rubric_loom_launcher.sh` from the unzipped folder.

The managed ZIP is the one-download distribution. It contains the exact
Rubric Loom runner and Rubric Bundle versions tested together, plus their
release manifest and checksum-backed runtime and contract records.

## Authorize the first launch on macOS

The current release is unsigned and not notarized, so macOS may block the
first launch even when the ZIP came from the official Releases page.

1. Unzip the release and try to open `Rubric Loom.command` once.
2. Dismiss the warning.
3. Choose **Apple menu > System Settings > Privacy & Security**. You may need
   to scroll down.
4. Under **Security**, click **Open**, then **Open Anyway**.
5. Enter your Mac login password and confirm the launch.

Apple normally leaves **Open Anyway** available for about an hour after the
blocked attempt. See Apple's
[current unknown-developer instructions](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac).

Use this per-app exception only after confirming that the ZIP came from the
official Rubric Loom Releases page. Do not disable Gatekeeper or weaken
system-wide security settings. Institution-managed Macs may require help from
local IT.

## What happens on first run

- The launcher looks for an existing supported Python 3.11-3.13 installation
  and reuses it. It does not reinstall Python when a supported copy is present.
- If Python is missing, the launcher explains what it found and asks before
  offering an installation.
- Before asking you to choose Unravel or Weave, the Loom checks its required
  support packages. If necessary, it offers to create a private environment
  under `user-data/runtime/.venv`; packages are not installed into the system
  Python.
- Rubric Loom runs locally. It does not send course material to an AI service
  or import anything into Brightspace.

## What the managed release can do

The managed launcher keeps complete releases under `versions/` and keeps
inputs, outputs, remembered settings, and the private Python environment under
`user-data/`. Program versions can therefore be installed, activated, rolled
back, or removed without deleting user work.

When you approve an update, the launcher verifies the GitHub asset digest,
the published `.sha256` sidecar, repository identities, exact runner and
bundle commits, critical runtime files, and contract hashes before activation.
An update is installed beside the current version; the previous complete
version remains available for rollback. Update checks do not silently replace
the running version.

The smaller `rubric-loom-v<VERSION>.zip` is the portable distribution. It
contains the same tested runner/bundle pair but does not provide the managed
installation's side-by-side activation and rollback workflow.

## Managed-install checks and recovery

Run these commands from the top level of the unzipped managed installation.

macOS or Linux:

```bash
bash rubric_loom_launcher.sh --health
bash rubric_loom_launcher.sh --list-versions
bash rubric_loom_launcher.sh --update
bash rubric_loom_launcher.sh --rollback
```

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\rubric_loom_launcher.ps1 --health
powershell -NoProfile -ExecutionPolicy Bypass -File .\rubric_loom_launcher.ps1 --list-versions
powershell -NoProfile -ExecutionPolicy Bypass -File .\rubric_loom_launcher.ps1 --update
powershell -NoProfile -ExecutionPolicy Bypass -File .\rubric_loom_launcher.ps1 --rollback
```

`--health` verifies the active release manifest and the receipted runner and
bundle files. `--rollback` changes the active pointer to the retained previous
version; it does not remove the current version or user data.

To inspect the Loom's Python and package setup without beginning a run:

```bash
bash rubric_loom_launcher.sh --doctor
```

## Common problems

### The download does not contain the Loom or Bundle

You probably downloaded the green **Code > Download ZIP** archive or a
GitHub-generated **Source code** ZIP. Return to Releases and download
`rubric-loom-managed-v<VERSION>.zip`.

### macOS says the developer cannot be verified

Confirm the ZIP came from the official Releases page, try to open the command
once, then follow the **Privacy & Security** workflow above.

### Windows shows a trust or policy warning

Confirm the ZIP came from the official Releases page. Follow your
organization's software policy; institution-managed devices may require IT
approval. Do not disable SmartScreen, antivirus, or organization-wide policy.

### Python is already installed, but the launcher cannot find it

Open a new Terminal or PowerShell window after installing Python and rerun the
launcher. The macOS/Linux launcher checks `python3.13`, `python3.12`,
`python3.11`, and `python3`, and also accepts an explicit `PYTHON` path:

```bash
PYTHON=/full/path/to/python3.12 bash rubric_loom_launcher.sh
```

Rubric Loom currently supports Python 3.11 through 3.13. Python 3.14 is not
selected by the launcher.

### Dependency setup fails

Keep the installation folder writable, confirm the computer can reach the
Python package index, and retry. Proxies, SSL inspection, antivirus, and
institutional network policy can block package downloads. The Loom asks before
installing and keeps its packages under `user-data/runtime/.venv`.

### An update fails or the active release appears damaged

Run `--health` first. A failed download, checksum, archive, manifest, runtime,
or contract check leaves the current version selected. Use `--rollback` only
when a previous complete version is listed. Do not manually combine runner and
bundle folders from different releases.

### Unravel fails or stops partway through

The result card identifies the output folder and run log. Each course output
folder contains `unravel_wizard.log`; a bulk run keeps a separate output folder
and log for each course. The folder may also contain valid artifacts from
steps that completed before the failure.

### Weave fails or stops partway through

Review the failure card and the referenced log. In a managed installation,
Weave logs are written under `user-data/output/logs/` and end in
`weave_wizard.log`. A failed or interrupted Weave run does not claim a package
that was not fully built and validated.

### The package imports but is not attached to an activity

Rubric Loom builds a rubric-only Brightspace import package; it does not import
the package or attach the rubric to an assignment, discussion, or quiz. Import
and activity attachment remain manual Brightspace steps.

## Report a problem

[Open a Rubric Loom issue](https://github.com/timebeing92/brightspace-rubric-loom-runner/issues)
and include:

- operating system and version;
- Rubric Loom version;
- managed or portable setup;
- Unravel or Weave;
- the step that failed;
- the complete error message; and
- a short description of what you expected to happen.

Do not attach course exports, institutional rubrics, learner data, credentials,
or other sensitive material. Redact local usernames and private paths from
logs before posting excerpts.
