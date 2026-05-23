#!/usr/bin/env python3
"""
install.py — sets up the `rss` command without relying on pip entry points.

Run once:  python3 install.py
Then use:  rss fetch / rss ui / etc.
"""
import sys
import os
import stat
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # exact python that's running this script


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  ✗ Command failed (exit {result.returncode})")
        sys.exit(1)


def main():
    print("=== RSS Reader installer ===\n")

    # 1. Install dependencies using the exact python running this script
    print("1. Installing dependencies…")
    run([PYTHON, "-m", "pip", "install", "typer", "feedparser",
         "tomlkit", "textual", "--quiet",
         "--break-system-packages"])
    print("   ✓ Dependencies installed\n")

    # 2. Write the `rss` launcher that hardcodes this exact python + project path
    bin_dirs = [
        os.path.expanduser("~/.local/bin"),
        "/usr/local/bin",  # fallback if ~/.local/bin isn't on PATH
    ]
    bin_dir = None
    for d in bin_dirs:
        if d in os.environ.get("PATH", ""):
            bin_dir = d
            break
    if not bin_dir:
        bin_dir = os.path.expanduser("~/.local/bin")

    os.makedirs(bin_dir, exist_ok=True)
    launcher_path = os.path.join(bin_dir, "rss")

    launcher = f"""#!/bin/sh
exec "{PYTHON}" "{os.path.join(PROJECT_DIR, 'run.py')}" "$@"
"""
    with open(launcher_path, "w") as f:
        f.write(launcher)

    # make it executable
    st = os.stat(launcher_path)
    os.chmod(launcher_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"2. Created launcher: {launcher_path}")
    print(f"   Uses python: {PYTHON}")
    print(f"   Points to:   {PROJECT_DIR}/run.py\n")

    # 3. Check if bin_dir is on PATH
    if bin_dir not in os.environ.get("PATH", "").split(":"):
        shell_rc = "~/.bashrc"
        if "zsh" in os.environ.get("SHELL", ""):
            shell_rc = "~/.zshrc"
        print(f"⚠  {bin_dir} is not on your PATH.")
        print(f"   Add this line to {shell_rc}:")
        print(f'   export PATH="{bin_dir}:$PATH"')
        print(f"   Then run: source {shell_rc}\n")
    else:
        print("3. PATH is already set up correctly.\n")

    print("✓ Done!  Try:  rss --help")


if __name__ == "__main__":
    main()