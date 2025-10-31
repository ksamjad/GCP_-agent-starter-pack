#!/usr/bin/env python3
"""
Build the winsights_agent package into a wheel.
"""

import subprocess
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

def clean():
    for folder in ["build", "dist", "winsights_agent.egg-info"]:
        p = ROOT / folder
        if p.exists():
            shutil.rmtree(p)
            print(f"Removed {p}")

def build():
    print("Building wheel using current python:", sys.executable)
    result = subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation"], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit("Build failed")
    wheels = sorted(DIST.glob("winsights_agent-*.whl"))
    if not wheels:
        raise SystemExit("No wheel found in dist/")
    print("Built wheel:", wheels[-1])
    return wheels[-1]

if __name__ == "__main__":
    clean()
    build()
