"""No-input Docker startup preflight using the exact trusted-operator invocation.

No operator files, databases, credentials, datasets or external networks are needed.
The second probe explicitly checks the required transitive modules and isolation flags.
"""

import json
import subprocess

IMAGE = "clearledger-chronological:local"
OPERATOR_ARGV = [
    "/app/.venv/bin/python",
    "-X",
    "utf8",
    "-I",
    "-B",
    "/app/scripts/chronological_adapter.py",
]
MODULES = (
    "chronological_adapter",
    "chronological_protocol",
    "chronological_diagnostics",
    "chronological_host",
    "application_eval_contract",
    "application_eval_host",
    "application_eval_inputs",
    "application_eval_runtime",
    "pilot_runtime",
)
TRANSITIVE = (
    "clearledger.main",
    "clearledger.case_outbox",
    "clearledger.imports",
    "clearledger.document_contract",
    "clearledger.finance_models",
    "alembic.command",
    "sqlalchemy",
    "httpx",
)


def container_command(arguments):
    return [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--network",
        "none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=1g",
        "--cpus=2",
        "--pids-limit=128",
        "--workdir",
        "/tmp",
        "--env",
        "PYTHONPATH=/tmp",
        "--entrypoint",
        arguments[0],
        IMAGE,
        *arguments[1:],
    ]


def run(arguments):
    result = subprocess.run(
        container_command(arguments),
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )
    if result.returncode:
        raise RuntimeError("ISOLATED_STARTUP_PREFLIGHT_FAILED\n" + result.stderr)
    return result


def verify():
    # EXACT invocation, no preflight flags/arguments appended, closed input and no DB.
    result = run(OPERATOR_ARGV)
    if result.stdout:
        raise RuntimeError("UNEXPECTED_PROTOCOL_STDOUT_AT_EOF")
    probe = (
        "import importlib,json,os,sys,sysconfig; from pathlib import Path; "
        "assert sys.flags.isolated == 1 and sys.flags.ignore_environment == 1; "
        "assert sys.flags.no_user_site == 1 and sys.flags.dont_write_bytecode == 1; "
        "assert sys.flags.utf8_mode == 1; assert '' not in sys.path and '/tmp' not in sys.path; "
        "assert os.geteuid() == 10001; directory=Path('/app/scripts'); "
        "assert directory.stat().st_uid == 0 and directory.stat().st_mode & 0o022 == 0; "
        "pth=Path(sysconfig.get_path('purelib'), 'clearledger_harness.pth'); "
        "assert pth.read_text() == '/app/scripts\\n'; "
        "assert pth.stat().st_uid == 0 and pth.stat().st_mode & 0o022 == 0; "
        f"names={MODULES!r}; dependencies={TRANSITIVE!r}; "
        "loaded={name:importlib.import_module(name) for name in names+dependencies}; "
        "assert all(Path(loaded[name].__file__).resolve() == "
        "Path('/app/scripts', name+'.py') for name in names); "
        "assert loaded['pilot_runtime'].ROOT == Path('/app'); "
        "print(json.dumps({'isolated':True,'module_origins':"
        "{name:module.__file__ for name,module in loaded.items()}}))"
    )
    checked = json.loads(run(OPERATOR_ARGV[:-1] + ["-c", probe]).stdout)
    return {"exact_operator_argv": OPERATOR_ARGV, "eof_startup": "PASS", **checked}


def main():
    print(json.dumps(verify(), indent=2))


if __name__ == "__main__":
    main()
