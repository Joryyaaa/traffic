#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
try:
    import madina
except Exception as e:
    raise SystemExit(f"REAL MADINA NOT AVAILABLE: {e}")
cmd=[sys.executable,str(ROOT/"scripts/run_abha_event_hotspot_madina.py"),"--scenario","B0"]
raise SystemExit(subprocess.call(cmd,cwd=ROOT))
