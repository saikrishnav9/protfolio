from __future__ import annotations

import shutil
from pathlib import Path

from pulse.config import ROOT


def assemble_site() -> Path:
    """Copy the Pulse dashboard under site/pulse so Pages can serve both."""
    src = ROOT / "dashboard"
    dest = ROOT / "site" / "pulse"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return ROOT / "site"
