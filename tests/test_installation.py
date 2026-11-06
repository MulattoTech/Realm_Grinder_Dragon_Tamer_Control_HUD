"""Offline regressions for the PowerShell install and release entry points."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
import sys

import pytest


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if not executable:
        pytest.skip("PowerShell is required for installer script tests")
    return executable


def _run_powershell(script: Path, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_powershell(), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _stub_path(tmp_path: Path, env: dict[str, str]) -> Path:
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    env["PATH"] = str(stub_dir) + os.pathsep + env.get("PATH", "")
    return stub_dir


def _install_project(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    shutil.copy2(source / "Install.ps1", tmp_path / "Install.ps1")
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "bootstrap.py").write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    return tmp_path / "Install.ps1"


def test_install_rejects_python_discovery_commands_that_exit_nonzero(tmp_path: Path) -> None:
    """A version string is not proof that the native discovery command succeeded."""
    install_script = _install_project(tmp_path)

    env = os.environ.copy()
    log = tmp_path / "commands.txt"
    env["INSTALL_STUB_LOG"] = str(log)
    stubs = _stub_path(tmp_path, env)
    (stubs / "py.cmd").write_text(
        '@echo off\r\necho py %*>>"%INSTALL_STUB_LOG%"\r\necho Python 3.12.9\r\nexit /b 9\r\n',
        encoding="ascii",
    )
    (stubs / "python.cmd").write_text(
        '@echo off\r\necho python %*>>"%INSTALL_STUB_LOG%"\r\necho 3.12\r\nexit /b 7\r\n',
        encoding="ascii",
    )

    result = _run_powershell(install_script, tmp_path, env)

    assert result.returncode != 0
    assert "Python 3.12" in result.stdout + result.stderr
    calls = log.read_text(encoding="utf-8")
    assert "py -3.12 --version" in calls
    assert "-m venv" not in calls
    assert "python -c" in calls
    assert "pip install" not in calls
    assert "bootstrap.py" not in calls


def test_install_reports_virtual_environment_creation_failure(tmp_path: Path) -> None:
    install_script = _install_project(tmp_path)
    env = os.environ.copy()
    stubs = _stub_path(tmp_path, env)
    (stubs / "py.cmd").write_text(
        '@echo off\r\nif "%2"=="--version" (echo Python 3.12.9& exit /b 0)\r\nexit /b 23\r\n',
        encoding="ascii",
    )

    result = _run_powershell(install_script, tmp_path, env)

    assert result.returncode != 0
    assert "Virtual environment creation failed with exit code 23" in result.stdout + result.stderr


def test_install_stops_when_pip_upgrade_fails(tmp_path: Path) -> None:
    if sys.version_info[:2] != (3, 12):
        pytest.skip("offline virtual environment fixture requires Python 3.12")

    install_script = _install_project(tmp_path)
    env = os.environ.copy()
    env["INSTALL_REAL_PYTHON"] = sys.executable
    pip_config = tmp_path / "invalid-pip.ini"
    pip_config.write_text("not a valid ini section\n", encoding="ascii")
    env["PIP_CONFIG_FILE"] = str(pip_config)
    stubs = _stub_path(tmp_path, env)
    (stubs / "py.cmd").write_text(
        '@echo off\r\n'
        'if "%2"=="--version" goto version\r\n'
        'if "%2"=="-m" if "%3"=="venv" goto venv\r\n'
        'exit /b 23\r\n'
        ':version\r\n'
        'echo Python 3.12.9\r\n'
        'exit /b 0\r\n'
        ':venv\r\n'
        'call "%INSTALL_REAL_PYTHON%" -m venv "%4"\r\n'
        'exit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )

    result = _run_powershell(install_script, tmp_path, env)

    assert result.returncode != 0
    assert "pip upgrade failed with exit code" in result.stdout + result.stderr
    assert "Installation complete." not in result.stdout


def test_release_archive_failure_preserves_existing_archive(tmp_path: Path) -> None:
    """A failed archive attempt must not remove the last successfully built ZIP."""
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(source / "scripts" / "Build-Release.ps1", root / "scripts" / "Build-Release.ps1")
    (root / "VERSION").write_text("1.2.3\n", encoding="ascii")
    env = os.environ.copy()
    build_script = root / "scripts" / "Build-Release.ps1"
    harness = root / "run-build.ps1"
    harness.write_text(
        "function git {\n"
        "  $global:LASTEXITCODE = 0\n"
        "  switch ($args -join ' ') {\n"
        "    'status --porcelain' { return }\n"
        "    'ls-files state backups logs screenshots scratch scraped_wiki assets/templates' { return }\n"
        "    'rev-parse HEAD' { return '0123456789abcdef0123456789abcdef01234567' }\n"
        "    'rev-parse --short=12 HEAD' { return '0123456789ab' }\n"
        "    'archive --format=zip --prefix=Realm_Grinder_Dragon_Tamer_Control_HUD-1.2.3/ -o' { $global:LASTEXITCODE = 17; return }\n"
        "    default { $global:LASTEXITCODE = 17; return }\n"
        "  }\n"
        "}\n"
        f". '{build_script.as_posix()}' -Version '1.2.3'\n",
        encoding="utf-8",
    )
    artifact = root / "dist" / "Realm-Grinder-Dragon-Tamer-Control-HUD-v1.2.3-0123456789ab.zip"
    artifact.parent.mkdir()
    artifact.write_bytes(b"previous-valid-archive")

    result = _run_powershell(harness, root, env)

    assert result.returncode != 0
    assert artifact.read_bytes() == b"previous-valid-archive"
    assert list(artifact.parent.glob("*.tmp")) == []


def test_release_archive_promotes_a_completed_temporary_archive(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    build_script = root / "scripts" / "Build-Release.ps1"
    shutil.copy2(source / "scripts" / "Build-Release.ps1", build_script)
    (root / "VERSION").write_text("1.2.3\n", encoding="ascii")
    harness = root / "run-build.ps1"
    harness.write_text(
        "function git {\n"
        "  $global:LASTEXITCODE = 0\n"
        "  switch ($args[0]) {\n"
        "    'status' { return }\n"
        "    'ls-files' { return }\n"
        "    'rev-parse' { if ($args[1] -eq 'HEAD') { return '0123456789abcdef0123456789abcdef01234567' }; return '0123456789ab' }\n"
        "    'archive' { $outputIndex = [Array]::IndexOf($args, '-o'); [IO.File]::WriteAllBytes($args[$outputIndex + 1], [Text.Encoding]::UTF8.GetBytes('complete-zip')); return }\n"
        "  }\n"
        "}\n"
        f". '{build_script.as_posix()}' -Version '1.2.3'\n",
        encoding="utf-8",
    )
    artifact = root / "dist" / "Realm-Grinder-Dragon-Tamer-Control-HUD-v1.2.3-0123456789ab.zip"
    artifact.parent.mkdir()
    artifact.write_bytes(b"previous-valid-archive")

    result = _run_powershell(harness, root, os.environ.copy())

    assert result.returncode == 0, result.stdout + result.stderr
    assert artifact.read_bytes() == b"complete-zip"
    assert list(artifact.parent.glob("*.tmp")) == []
    assert (artifact.parent / "release-manifest-1.2.3.json").exists()


def test_repository_verifier_pins_python_launcher_to_312(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    verifier = scripts / "Verify-Repository.ps1"
    shutil.copy2(source / "scripts" / "Verify-Repository.ps1", verifier)
    harness = root / "run-verify.ps1"
    log = root / "python-calls.txt"
    harness.write_text(
        "function py {\n"
        "  Add-Content -LiteralPath $env:VERIFY_STUB_LOG -Value ($args -join ' ')\n"
        "  $global:LASTEXITCODE = 0\n"
        "  if ($args -contains '--version') { Write-Output 'Python 3.12.9' }\n"
        "}\n"
        f". '{verifier.as_posix()}' -AllowDirty\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["VERIFY_STUB_LOG"] = str(log)
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=15)

    result = _run_powershell(harness, root, env)

    assert result.returncode == 0, result.stdout + result.stderr
    python_calls = log.read_text(encoding="utf-8").splitlines()
    assert len(python_calls) == 4
    assert all(call.startswith("-3.12 ") for call in python_calls[1:])
    assert "-3.12 -m compileall" in python_calls[1]
    assert "-3.12 -m pytest" in python_calls[2]
    assert "-3.12 tools\\verify_checkout.py" in python_calls[3]
