"""The quality gates reject what they must (issue #4: a deliberately failing change is rejected).

Each test feeds the real configuration a violation and expects a non-zero exit. A gate that
stops rejecting fails here, so a config edit cannot silently switch it off.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = Path(sys.executable).parent


def ruff_on(source: str, filename: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            str(BIN / "ruff"),
            "check",
            "--config",
            str(ROOT / "pyproject.toml"),
            "--stdin-filename",
            filename,
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("from datetime import datetime\n\nx = datetime.now()\n", "datetime.datetime.now"),
        ("import datetime\n\nx = datetime.datetime.now()\n", "datetime.datetime.now"),
        ("from datetime import datetime\n\nx = datetime.utcnow()\n", "datetime.datetime.utcnow"),
        ("from datetime import date\n\nx = date.today()\n", "datetime.date.today"),
        ("import time\n\ntime.sleep(1)\n", "time.sleep"),
        ("from time import sleep\n\nsleep(1)\n", "time.sleep"),
        ("import random\n\nx = random.random()\n", "random"),
        ("from random import choice\n\nx = choice([1])\n", "random"),
    ],
)
def test_ruff_bans_time_and_randomness_in_app(source: str, rule: str) -> None:
    result = ruff_on(source, "app/metrics/_x.py")

    assert result.returncode != 0, result.stdout
    assert "TID251" in result.stdout
    assert rule in result.stdout


def test_ruff_allows_the_same_calls_in_tests() -> None:
    result = ruff_on("import time\n\ntime.sleep(0)\n", "tests/metrics/test_x.py")

    assert result.returncode == 0, result.stdout


def lint_imports_with(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    shutil.copytree(ROOT / "app", tmp_path / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "importlinter.ini", tmp_path / "importlinter.ini")
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return subprocess.run(  # noqa: S603
        [str(BIN / "lint-imports"), "--config", "importlinter.ini"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
        env={"PATH": str(BIN), "PYTHONPATH": str(tmp_path)},
    )


def test_import_linter_passes_on_the_real_code(tmp_path: Path) -> None:
    result = lint_imports_with(tmp_path, {})

    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    ("file", "text", "contract"),
    [
        ("app/domain/_bad.py", "from app.metrics import average_rating\n", "Dependencies go one way"),
        ("app/metrics/_bad.py", "from app.domain._clock import FakeClock\n", "Internals are private"),
        ("app/metrics/_bad2.py", "import httpx\n", "No network library in pure modules"),
        ("app/domain/_bad2.py", "import requests\n", "No network library in pure modules"),
    ],
)
def test_import_linter_rejects_a_boundary_violation(
    tmp_path: Path, file: str, text: str, contract: str
) -> None:
    result = lint_imports_with(tmp_path, {file: text})

    assert result.returncode != 0, result.stdout
    assert contract in result.stdout
