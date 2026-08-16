"""Regression smoke test for the live web client (web/app.js + web/sprites.js).

Boots the client against a stubbed DOM via Node (tests/smoke_client.js), feeds
it realistic snapshots, runs the animation loop, and asserts the rendered DOM
(HUD title, roster cards + HP/energy bar widths, narrative log rows, sprite
elements). This catches the whole class of "selector no longer matches what the
client creates" runtime TypeErrors that would otherwise freeze the deployed
diorama — e.g. the roster-bar class mismatch that broke applySnapshot on every
tick.

Skips cleanly when Node is unavailable (no client sources to test).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "smoke_client.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not available to smoke-test the web client",
)


def test_web_client_smoke() -> None:
    result = subprocess.run(
        ["node", str(HARNESS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"web client smoke test failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
