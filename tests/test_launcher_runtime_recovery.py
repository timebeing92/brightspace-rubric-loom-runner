"""Exercise real entry points against disposable private interpreters."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import venv

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = '''import json, sys
answer = sys.stdin.readline().strip()
print("HANDOFF=" + json.dumps({"prefix": sys.prefix, "args": sys.argv[1:], "answer": answer}))
print("synthetic terminal diagnostic", file=sys.stderr)
raise SystemExit(7)
'''


@pytest.mark.parametrize("surface", ["managed", "portable"])
@pytest.mark.parametrize("shell", ["bash", "powershell", "pwsh"])
@pytest.mark.parametrize("state", ["healthy", "missing", "broken", "unsupported", "hung"])
def test_entry_point_reuses_or_recovers_private_runtime(
    tmp_path: Path, surface: str, shell: str, state: str,
) -> None:
    if (shell == "bash") != (os.name != "nt"):
        pytest.skip("native entry point for the other operating system")
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    install = tmp_path / "Loom install & review"
    shutil.copytree(ROOT / "launcher", install / "launcher")
    suffix = ".sh" if shell == "bash" else ".ps1"
    if surface == "managed":
        entry = install / ("rubric_loom_launcher" + suffix)
        shutil.copy2(ROOT / "launcher" / entry.name, entry)
        (install / "launcher/stable_launcher.py").write_text(HANDOFF)
    else:
        entry = install / ("rubric_loom" + suffix)
        shutil.copy2(ROOT / entry.name, entry)
    bundle = tmp_path / "paired bundle"
    (bundle / "scripts").mkdir(parents=True)
    (bundle / "scripts/rubric_loom_wizard.py").write_text(HANDOFF)
    environment = install / "user-data/runtime/.venv"
    private_python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pid_file = tmp_path / "probe.pid"
    if state != "missing":
        venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(environment)
        if state == "broken":
            # Unlink first: never write through a symlink to the real Python.
            private_python.unlink()
            private_python.write_bytes(b"not an executable")
        elif state in {"unsupported", "hung"}:
            site = environment / ("Lib/site-packages" if os.name == "nt" else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
            site.mkdir(parents=True, exist_ok=True)
            code = "import sys\nsys.version_info = (3, 10, 0, 'final', 0)\n"
            if state == "hung":
                code = f"import os, time\nfrom pathlib import Path\nPath({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(60)\n"
            (site / "sitecustomize.py").write_text(code)
    env = {key: value for key, value in os.environ.items() if not key.startswith("RUBRIC_LOOM_")}
    env.update(PYTHON=sys.executable, RUBRIC_LOOM_BUNDLE_DIR=str(bundle))
    args = ["--health", "file with spaces", "--label=two words"]
    command = [executable, str(entry), *args] if shell == "bash" else [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(entry), *args]
    started = time.monotonic()
    try:
        result = subprocess.run(command, env=env, input="operator response\n", capture_output=True, text=True, timeout=15, check=False)
        assert result.returncode == 7, result.stdout + result.stderr
        handoff = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("HANDOFF=")))
        expected = environment if state == "healthy" else Path(sys.prefix)
        assert Path(handoff["prefix"]).resolve() == expected.resolve()
        assert handoff["args"][-len(args):] == args
        assert handoff["answer"] == "operator response"
        assert "synthetic terminal diagnostic" in result.stderr
        assert time.monotonic() - started < 15
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGTERM)
            except OSError:
                # Windows reports an already-terminated probe as WinError 87,
                # rather than POSIX's ProcessLookupError.
                pass
