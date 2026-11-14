"""One-command entry points.

  python -m mi.cli all      download (if missing) -> audit -> train/evaluate -> portfolio & sensitivity ->
                            RAG eval -> GEO analysis -> FashionForward fixture -> blocked demo -> agents to checkpoint
  python -m mi.cli test     run the test suite
  python -m mi.cli demo     launch the Streamlit manager app
"""
from __future__ import annotations

import subprocess
import sys
import time

from mi.paths import RAW, ROOT

STEPS = [
    ("download", ["mi.ingest.download"], lambda: not (RAW / "transactions.rds").exists()),
    ("audit", ["mi.ingest.audit"], None),
    ("train", ["mi.model.train"], None),
    ("portfolio+sensitivity", ["mi.decision.report"], None),
    ("rag eval", ["mi.evidence.rag", "eval"], None),
    ("geo analysis", ["mi.seo.geo", "analyze"], None),
    ("fashionforward fixture", ["mi.decision.fashionforward"], None),
    ("blocked demo", ["mi.agents.coordinator", "blocked-demo"], None),
    ("agents to human checkpoint", ["mi.agents.coordinator", "run"], None),
]


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["all"])[0]
    py = sys.executable
    if cmd == "test":
        return subprocess.call([py, "-m", "pytest", "-q"], cwd=ROOT)
    if cmd == "demo":
        return subprocess.call([py, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py")], cwd=ROOT)
    for name, mod, cond in STEPS:
        if cond is not None and not cond():
            print(f"[skip] {name}")
            continue
        t = time.time()
        print(f"[run ] {name} ...", flush=True)
        rc = subprocess.call([py, "-m", *mod], cwd=ROOT, stdout=subprocess.DEVNULL if name != "agents to human checkpoint" else None)
        print(f"[{'ok' if rc == 0 else 'FAIL'}] {name} ({time.time() - t:.0f}s)")
        if rc != 0 and name != "fashionforward fixture":
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
