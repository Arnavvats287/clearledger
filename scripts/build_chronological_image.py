"""Build a runner image from an explicit application-only context, never the workspace."""

import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "chronological_adapter.py",
    "chronological_host.py",
    "chronological_protocol.py",
    "application_eval_host.py",
    "application_eval_runtime.py",
    "application_eval_inputs.py",
    "application_eval_contract.py",
    "pilot_runtime.py",
)


def main():
    context = ROOT / "local-data" / "chronological-builds" / uuid4().hex
    context.mkdir(parents=True, exist_ok=False)
    for name in ("pyproject.toml", "uv.lock", ".python-version", "alembic.ini"):
        shutil.copyfile(ROOT / name, context / name)
    shutil.copytree(
        ROOT / "src",
        context / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )
    shutil.copytree(
        ROOT / "infra/migrations",
        context / "infra/migrations",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (context / "scripts").mkdir()
    for name in SCRIPTS:
        shutil.copyfile(ROOT / "scripts" / name, context / "scripts" / name)
    shutil.copyfile(ROOT / "infra/chronological.Dockerfile", context / "Dockerfile")
    subprocess.run(
        ["docker", "build", "--tag", "clearledger-chronological:local", str(context)], check=True
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_chronological_startup.py")], check=True
    )


if __name__ == "__main__":
    main()
