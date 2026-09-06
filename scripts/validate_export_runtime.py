"""Validate an Aqlio application export in a clean, standalone environment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import venv
import zipfile
from pathlib import Path


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="aqlio-export-validation-") as raw_directory:
        root = Path(raw_directory)
        with zipfile.ZipFile(args.archive) as archive:
            names = archive.namelist()
            if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                raise ValueError("Unsafe archive path")
            archive.extractall(root)
        combined = b"\n".join(path.read_bytes() for path in root.rglob("*") if path.is_file())
        forbidden = [
            b"app.application",
            b"app.adapters",
            b"app.infrastructure",
            b"OperationsService",
            b"AQLIO_AI_MODE",
        ]
        if any(item in combined for item in forbidden):
            raise ValueError("Aqlio platform dependency found")
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        if "OPENAI_API_KEY=\n" not in env_example:
            raise ValueError("Environment template is not placeholder-only")
        environment = root / ".validation-venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = environment / "bin/python"
        pip_result = run(
            [str(python), "-m", "pip", "install", "-r", "requirements-test.txt"],
            cwd=root,
            env=os.environ.copy(),
        )
        isolated_env = {
            **os.environ,
            "APPLICATION_AI_MODE": "fake",
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
        }
        test_result = run([str(python), "-m", "pytest", "-q"], cwd=root, env=isolated_env)
        process = subprocess.Popen(
            [
                str(python),
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.headless=true",
                "--server.address=127.0.0.1",
                "--server.port=8765",
            ],
            cwd=root,
            env=isolated_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        healthy = False
        try:
            for _ in range(40):
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:8765/_stcore/health", timeout=1
                    ) as response:
                        healthy = response.status == 200 and response.read().strip() == b"ok"
                    if healthy:
                        break
                except OSError:
                    time.sleep(0.25)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if not healthy:
            raise RuntimeError("Standalone Streamlit health check failed")
        config = json.loads((root / "application_config.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "AQLIO_EXPORT_MANIFEST.json").read_text(encoding="utf-8"))
        railpack = json.loads((root / "railpack.json").read_text(encoding="utf-8"))
        railway_guide = (root / "deployment/RAILWAY.md").read_text(encoding="utf-8")
        start_command = railpack["deploy"]["startCommand"]
        if (root / ".python-version").read_text(encoding="utf-8").strip() != "3.12":
            raise ValueError("Railway runtime is not pinned to Python 3.12")
        if start_command != ("streamlit run app.py --server.address 0.0.0.0 --server.port $PORT"):
            raise ValueError("Railway start command is invalid")
        readiness_terms = (
            "APPLICATION_AI_MODE=fake",
            "`/_stcore/health`",
            "do not survive a restart",
            "Never use Aqlio provider credentials",
        )
        if any(term not in railway_guide for term in readiness_terms):
            raise ValueError("Railway deployment guidance is incomplete")
        results = {
            "clean_environment": "passed",
            "dependency_install": "passed",
            "dependency_install_output": pip_result.stdout.splitlines()[-1],
            "package_tests": test_result.stdout.strip(),
            "startup_health": "passed",
            "ai_mode": "fake",
            "aqlio_import_scan": "passed",
            "placeholder_env": "passed",
            "approved_version": manifest["Approved Version"],
            "project_version": manifest["Project Version"],
            "export_version": manifest["Export Version"],
            "ui_config": config["ui"],
            "behavior_config": config["behavior"],
            "railway_readiness": "passed",
            "railway_runtime": "Python 3.12",
            "railway_start_command": start_command,
            "railway_health_path": "/_stcore/health",
            "railway_storage_assumption": "session-memory only; no persistence",
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
