#!/usr/bin/env python3
"""Install pinned local runtimes and start one selected oneM2M topology."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["single", "secure", "multisite"], default="single", nargs="?")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    def run(script, *options):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script), *options], cwd=ROOT, check=True)
    if not args.skip_install:
        run("cse_runtime.py", "install")
        if args.profile == "secure":
            run("cse_broker.py", "install")
    if args.profile == "single":
        run("cse_runtime.py", "start")
    elif args.profile == "secure":
        run("cse_broker.py", "start")
        run("cse_runtime.py", "start", "--name", "secure", "--mqtt")
    else:
        run("cse_runtime.py", "start", "--name", "central", "--port", "8180")
        run("cse_runtime.py", "start", "--name", "food", "--port", "8181", "--registrar-port", "8180")
        run("cse_runtime.py", "start", "--name", "learning", "--port", "8182", "--registrar-port", "8180")


if __name__ == "__main__":
    main()
