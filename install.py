#!/usr/bin/env python3
"""
Curator installer
-----------------
Run once from the project root:

    python3 install.py          # Linux / macOS
    python  install.py          # Windows

What it does:
  1. Installs Python dependencies using the exact Python that runs this script.
  2. Writes a `curator` launcher that always calls that same Python,
     so there can never be a Python-version mismatch.
  3. Tells you if your PATH needs updating.
"""
import os
import platform
import stat
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON=sys.executable 
SYSTEM=platform.system()


def run(cmd: list[str]):
    print("  $", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"\n  ✗  Command failed (exit {r.returncode})")
        sys.exit(1)


def install_deps():
    print("1. Installing dependencies…")
    pip_args = [PYTHON, "-m", "pip", "install",
                "typer", "feedparser", "textual",
                "--quiet"]
    if SYSTEM != "Windows":
        pip_args.append("--break-system-packages")
    run(pip_args)
    print("   ✓  Dependencies installed\n")


def write_launcher() -> str:
    entry = os.path.join(PROJECT_DIR, "curator", "main.py")
    if SYSTEM == "Windows":
        bin_dir     = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "curator")
        os.makedirs(bin_dir, exist_ok=True)
        launcher    = os.path.join(bin_dir, "curator.cmd")
        with open(launcher, "w") as f:
            f.write(f'@echo off\n"{PYTHON}" "{entry}" %*\n')
        print(f"2. Created launcher: {launcher}")
        print(f"   Uses python: {PYTHON}\n")
        return bin_dir

    else:
        # Linux / macOS
        bin_dir = os.path.expanduser("~/.local/bin")
        os.makedirs(bin_dir, exist_ok=True)
        launcher = os.path.join(bin_dir, "curator")
        with open(launcher, "w") as f:
            f.write(f'#!/bin/sh\nexec "{PYTHON}" "{entry}" "$@"\n')
        st = os.stat(launcher)
        os.chmod(launcher, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"2. Created launcher: {launcher}")
        print(f"   Uses python: {PYTHON}\n")
        return bin_dir


def check_path(bin_dir: str):
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if bin_dir in path_dirs:
        print("3. PATH is already set up correctly.\n")
        return
    print(f"3.{bin_dir} is not in your PATH.")
    if SYSTEM == "Windows":
        print("   Add it via: System Properties → Environment Variables → PATH")
    else:
        shell_rc = "~/.zshrc" if "zsh" in os.environ.get("SHELL", "") else "~/.bashrc"
        print(f"   Add this line to {shell_rc}:")
        print(f'   export PATH="{bin_dir}:$PATH"')
        print(f"   Then run:  source {shell_rc}")
    print()


def main():
    print()
    print("╔══════════════════════════════╗")
    print("║   Curator — installer        ║")
    print("╚══════════════════════════════╝")
    print()
    install_deps()
    bin_dir = write_launcher()
    check_path(bin_dir)
    print("Done!")
    print()
    print("Try it:curator --help")
    print("curator ui")
    print()


if __name__ == "__main__":
    main()
