#!/usr/bin/env python3
"""
build.py — Cross-platform build script for HA-Minder.
Produces a standalone executable via PyInstaller.

Usage:
    python build.py

Output:
    dist/HA-Minder        (macOS / Linux)
    dist/HA-Minder.exe    (Windows)
"""

import os
import sys
import shutil
import subprocess
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR   = os.path.join(SCRIPT_DIR, '.venv')
SYSTEM     = platform.system()  # 'Darwin', 'Windows', 'Linux'


def _python() -> str:
    """Return path to the venv Python interpreter."""
    if SYSTEM == 'Windows':
        return os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    return os.path.join(VENV_DIR, 'bin', 'python')


def _pip() -> str:
    if SYSTEM == 'Windows':
        return os.path.join(VENV_DIR, 'Scripts', 'pip.exe')
    return os.path.join(VENV_DIR, 'bin', 'pip')


def run(*args, **kwargs):
    """Run a subprocess and raise on failure."""
    print(f"==> {' '.join(str(a) for a in args)}")
    subprocess.run(list(args), check=True, **kwargs)


def ensure_pyinstaller():
    try:
        subprocess.run(
            [_python(), '-c', 'import PyInstaller'],
            check=True, capture_output=True
        )
    except subprocess.CalledProcessError:
        print('==> Installing PyInstaller into .venv...')
        run(_pip(), 'install', 'pyinstaller')


def clean():
    for d in ('build', 'dist'):
        path = os.path.join(SCRIPT_DIR, d)
        if os.path.exists(path):
            print(f'==> Removing {d}/')
            shutil.rmtree(path)
    spec = os.path.join(SCRIPT_DIR, 'HA-Minder.spec')
    if os.path.exists(spec):
        os.remove(spec)


def build():
    icon_arg = []
    if SYSTEM == 'Darwin' and os.path.exists(os.path.join(SCRIPT_DIR, 'icon.icns')):
        icon_arg = ['--icon', 'icon.icns']
    elif SYSTEM == 'Windows' and os.path.exists(os.path.join(SCRIPT_DIR, 'icon.ico')):
        icon_arg = ['--icon', 'icon.ico']

    run(
        _python(), '-m', 'PyInstaller',
        '--onefile',
        '--windowed',          # no console window on Windows / macOS
        '--name', 'HA-Minder',
        *icon_arg,
        'haminder.py',
        cwd=SCRIPT_DIR,
    )


def report():
    exe = 'HA-Minder.exe' if SYSTEM == 'Windows' else 'HA-Minder'
    path = os.path.join(SCRIPT_DIR, 'dist', exe)
    print()
    if os.path.exists(path):
        print(f'✅  Done!  Executable: dist/{exe}')
    else:
        print('❌  Build may have failed — check output above.')
        sys.exit(1)


if __name__ == '__main__':
    print(f'==> Platform: {SYSTEM}')
    print(f'==> Using Python: {_python()}')
    ensure_pyinstaller()
    clean()
    build()
    report()
