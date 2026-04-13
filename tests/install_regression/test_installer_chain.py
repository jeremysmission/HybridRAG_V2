"""
Regression tests for the dated workstation installer surfaces.

These tests exist because a recent installer QA pass focused too much on
filename/path consistency and not enough on real launcher behavior. The suite
locks down:

1. The dated launcher chain:
   INSTALL_WORKSTATION.bat -> tools/setup_workstation_2026-04-12.bat
   -> tools/setup_workstation_2026-04-12.ps1
2. The legacy 2026-04-06 wrapper remains a compatibility shim only.
3. The pip + pip-system-certs stage streams live output instead of buffering
   into variables that make the installer look frozen.
4. All three launcher surfaces complete a -DryRun -NoPause smoke run.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


V2_ROOT = Path(__file__).resolve().parents[2]
INSTALL_BAT = V2_ROOT / "INSTALL_WORKSTATION.bat"
ACTIVE_BAT = V2_ROOT / "tools" / "setup_workstation_2026-04-12.bat"
LEGACY_BAT = V2_ROOT / "tools" / "setup_workstation_2026-04-06.bat"
ACTIVE_PS1 = V2_ROOT / "tools" / "setup_workstation_2026-04-12.ps1"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_minimal_installer_tree(root: Path) -> None:
    """Create the smallest project tree needed for installer dry-run smoke."""
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "src" / "config").mkdir(parents=True, exist_ok=True)

    shutil.copy2(INSTALL_BAT, root / "INSTALL_WORKSTATION.bat")
    shutil.copy2(ACTIVE_BAT, root / "tools" / "setup_workstation_2026-04-12.bat")
    shutil.copy2(LEGACY_BAT, root / "tools" / "setup_workstation_2026-04-06.bat")
    shutil.copy2(ACTIVE_PS1, root / "tools" / "setup_workstation_2026-04-12.ps1")
    (root / "src" / "config" / "schema.py").write_text(
        "# minimal schema marker for installer dry-run smoke\n",
        encoding="utf-8",
    )


def _have_py312() -> bool:
    try:
        result = subprocess.run(
            ["py", "-3.12", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def test_install_workstation_points_to_current_dated_wrapper():
    text = _read_text(INSTALL_BAT)
    assert r'tools\setup_workstation_2026-04-12.bat' in text
    assert r'tools\setup_workstation_2026-04-06.bat' not in text


def test_active_wrapper_points_to_current_dated_ps1():
    text = _read_text(ACTIVE_BAT)
    assert 'setup_workstation_2026-04-12.ps1' in text


def test_legacy_wrapper_is_compatibility_shim_to_current_ps1():
    text = _read_text(LEGACY_BAT)
    assert 'setup_workstation_2026-04-12.bat' in text
    assert 'compatibility' in text.lower()


def test_active_ps1_keeps_gliner_on_the_install_path():
    text = _read_text(ACTIVE_PS1)
    assert "pip-system-certs" in text
    assert '"gliner"' in text
    assert "verify_install.py" in text
    assert "pip install -r requirements.txt" in text


def test_pip_stage_streams_live_output_instead_of_buffering():
    text = _read_text(ACTIVE_PS1)
    assert "& $VenvPython -m pip install --upgrade pip @TrustedHosts" in text
    assert "& $VenvPip install pip-system-certs @TrustedHosts" in text
    assert "$pipUpgradeOutput =" not in text
    assert "$pipSystemCertsOutput =" not in text
    assert "Streaming pip output live" in text


def test_existing_healthy_venv_skips_pip_repair():
    text = _read_text(ACTIVE_PS1)
    assert 'pip already present in existing venv -- skipping upgrade' in text
    assert 'pip-system-certs already installed -- skipping' in text


def test_existing_healthy_torch_skips_reinstall():
    text = _read_text(ACTIVE_PS1)
    assert '$torchHealthyForLane' in text
    assert 'torch CUDA already healthy' in text
    assert '--force-reinstall --no-deps' in text


@pytest.mark.skipif(
    shutil.which("cmd") is None or not _have_py312(),
    reason="Windows cmd.exe and py -3.12 are required for installer smoke runs",
)
@pytest.mark.parametrize(
    ("launcher", "expected_line"),
    [
        ("INSTALL_WORKSTATION.bat", "[OK] HybridRAG V2 workstation install finished."),
        (r"tools\setup_workstation_2026-04-12.bat", "[OK] Setup completed."),
        (r"tools\setup_workstation_2026-04-06.bat", "[OK] Setup completed."),
    ],
)
def test_launcher_dryrun_smoke(launcher: str, expected_line: str):
    result = subprocess.run(
        ["cmd", "/c", launcher, "-DryRun", "-NoPause"],
        cwd=V2_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    output = result.stdout + "\n" + result.stderr
    assert result.returncode == 0, output
    assert "Pre-flight inventory (detect-first)" in output
    assert "-DryRun mode: inventory reported above, no install actions performed." in output
    assert expected_line in output


@pytest.mark.skipif(
    shutil.which("cmd") is None or not _have_py312(),
    reason="Windows cmd.exe and py -3.12 are required for installer smoke runs",
)
def test_fresh_checkout_dryrun_does_not_create_venv():
    with tempfile.TemporaryDirectory(prefix="v2_install_dryrun_") as tmpdir:
        root = Path(tmpdir)
        _build_minimal_installer_tree(root)

        result = subprocess.run(
            ["cmd", "/c", "INSTALL_WORKSTATION.bat", "-DryRun", "-NoPause"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        output = result.stdout + "\n" + result.stderr

        assert result.returncode == 0, output
        assert "-DryRun mode: inventory reported above, no install actions performed." in output
        assert not (root / ".venv").exists(), output
