"""Cross-platform helper script to package Stock Multi-Agent Desktop via PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    spec_file = project_root / "build" / "stock_analyst.spec"
    work_dir = project_root / "build" / "work"
    dist_dir = project_root / "dist"

    work_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(work_dir),
        "--distpath",
        str(dist_dir),
        str(spec_file),
    ]
    print("Running PyInstaller:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(project_root), check=False)
    if result.returncode == 0:
        print(f"\nBuild succeeded! Output directory: {dist_dir}")
    else:
        print(f"\nBuild failed with exit code {result.returncode}.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
