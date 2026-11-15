"""One-command entry points.

  python -m mi.cli all      download (if missing) -> verify against the committed lock -> audit -> train ->
                            extended evaluation -> portfolio, sensitivity & decision inputs -> claim audit (same-plan
                            economics, cohort turnover) -> RAG eval -> GEO check/analysis -> interview intake check ->
                            FashionForward fixture -> blocked demo -> agents to the human checkpoint
  python -m mi.cli test     run the test suite
  python -m mi.cli demo     launch the Streamlit manager app

Every step's stdout/stderr goes to reports/run_logs/NN_<step>.log; a failing step prints its last lines and stops
the run (except optional steps). reports/run_manifest.json records versions, git commit, data lock, timings and
the dossier created, so a run can be reproduced and compared.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

from mi.paths import RAW, REPORTS, ROOT

# (name, module args, run-condition or None, optional?)
STEPS = [
    ("download", ["mi.ingest.download", "--with-promotions"],
     lambda: not (RAW / "transactions.rds").exists() or not (RAW / "promotions.rds").exists(), False),
    ("verify data", ["mi.ingest.verify"], None, False),
    ("audit", ["mi.ingest.audit"], None, False),
    ("accounting audit + data dictionary", ["mi.ingest.accounting"], None, False),
    ("promotions load + join audit", ["mi.ingest.promotions"], None, False),
    ("train", ["mi.model.train"], None, False),
    ("evaluate model", ["mi.model.evaluate"], None, False),
    ("model commercial diagnostic + promo ablation", ["mi.model.diagnostic"], None, False),
    ("portfolio+sensitivity", ["mi.decision.report"], None, False),
    ("decision inputs + reversal", ["mi.decision.reversal"], None, False),
    ("claim audit", ["mi.claim_audit"], None, False),
    ("funding audit (historical coupon lines)", ["mi.ingest.funding_audit"], None, False),
    ("funding contracts (same plan) + reversal grid", ["mi.decision.funding_contracts"], None, False),
    ("category trend robustness (Yogurt)", ["mi.decision.trend_check", "YOGURT"], None, False),
    ("opportunity cards", ["mi.decision.opportunities"], None, False),
    ("client inputs check (form answers)", ["mi.decision.client_inputs", "check"], None, False),
    ("extra opportunity (pre-registered criteria)", ["mi.decision.extra_opportunity"], None, False),
    ("buyer-outcome panel", ["mi.decision.buyer_outcomes"], None, False),
    ("rag eval", ["mi.evidence.rag", "eval"], None, False),
    ("geo check", ["mi.seo.geo", "check"], None, False),
    ("geo analysis", ["mi.seo.geo", "analyze"], None, False),
    ("interview intake check", ["mi.evidence.interviews", "check"], None, False),
    ("fashionforward fixture", ["mi.decision.fashionforward"], None, True),
    ("hillstrom experiment (separate track)", ["mi.experiments.hillstrom"], None, True),
    ("blocked demo", ["mi.agents.coordinator", "blocked-demo"], None, False),
    ("agents to human checkpoint", ["mi.agents.coordinator", "run"], None, False),
]
POST = [("advisor evaluation (pre-registered cases)", ["mi.agents.advisor_eval"], None, False),
        ("current claims + decision card", ["mi.claims_export"], None, False),
        ("marketing brief + slide sync list", ["mi.decision.marketing_brief"], None, False)]
PACKAGES = ["numpy", "pandas", "scikit-learn", "pyreadr", "pyarrow", "streamlit", "anthropic"]


def _versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version
    out = {"python": sys.version.split()[0], "platform": platform.platform()}
    for p in PACKAGES:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def _git() -> dict:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
        return {"commit": head, "dirty_tracked_files": [l[3:] for l in dirty.splitlines()]}
    except Exception as e:  # git missing is not fatal
        return {"commit": None, "error": str(e)}


def run_all() -> int:
    py = sys.executable
    logs = REPORTS / "run_logs"
    logs.mkdir(parents=True, exist_ok=True)
    lock = ROOT / "data" / "manifest.lock.json"
    man = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "versions": _versions(), "git": _git(),
           "data_lock_sha16": hashlib.sha256(lock.read_bytes()).hexdigest()[:16] if lock.exists() else None,
           "seed": 20261114, "steps": []}
    rc_final, t_all = 0, time.time()
    for i, (name, mod, cond, optional) in enumerate(STEPS, 1):
        if cond is not None and not cond():
            print(f"[skip] {name}")
            man["steps"].append({"step": name, "status": "skipped"})
            continue
        t = time.time()
        log = logs / f"{i:02d}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}.log"
        print(f"[run ] {name} ...", flush=True)
        with open(log, "w", encoding="utf-8") as f:
            rc = subprocess.call([py, "-m", *mod], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        dt = round(time.time() - t, 1)
        status = "ok" if rc == 0 else ("FAIL (optional)" if optional else "FAIL")
        print(f"[{status}] {name} ({dt:.0f}s) -> {log.relative_to(ROOT)}")
        man["steps"].append({"step": name, "rc": rc, "seconds": dt, "log": str(log.relative_to(ROOT)), "status": status})
        if rc != 0:
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
            print("      last lines of the log:\n      " + "\n      ".join(tail), file=sys.stderr)
            if not optional:
                rc_final = rc
                break
    trace = REPORTS / "agent_trace_latest.json"
    if trace.exists() and rc_final == 0:
        man["dossier"] = json.loads(trace.read_text()).get("opportunity_id")
        (REPORTS / "run_manifest.json").write_text(json.dumps(man, indent=2))   # claims export reads the dossier id
        for k, (name, mod, _, _) in enumerate(POST, 1):
            t = time.time()
            log = logs / f"{len(STEPS) + k:02d}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}.log"
            with open(log, "w", encoding="utf-8") as f:
                rc = subprocess.call([py, "-m", *mod], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
            print(f"[{'ok' if rc == 0 else 'FAIL'}] {name} ({time.time() - t:.0f}s) -> {log.relative_to(ROOT)}")
            man["steps"].append({"step": name, "rc": rc, "seconds": round(time.time() - t, 1), "log": str(log.relative_to(ROOT))})
            rc_final = rc_final or rc
    man.update({"finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "seconds_total": round(time.time() - t_all, 1), "ok": rc_final == 0})
    (REPORTS / "run_manifest.json").write_text(json.dumps(man, indent=2))
    print(f"{'OK' if rc_final == 0 else 'FAILED'} in {man['seconds_total']:.0f}s; manifest -> reports/run_manifest.json"
          + (f"; dossier {man.get('dossier')}" if man.get("dossier") else ""))
    return rc_final


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["all"])[0]
    py = sys.executable
    if cmd == "test":
        return subprocess.call([py, "-m", "pytest", "-q"], cwd=ROOT)
    if cmd == "demo":
        return subprocess.call([py, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py")], cwd=ROOT)
    return run_all()


if __name__ == "__main__":
    sys.exit(main())
