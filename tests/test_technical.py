"""Regression tests for defects fixed in the technical pass (2026-11-14)."""
import json

import pandas as pd
import pytest


def test_run_id_changes_when_features_change():
    from mi.model.train import make_run_id
    a = make_run_id("cfg", "hgb_small", 1, "commit", ["f1", "f2"])
    assert a == make_run_id("cfg", "hgb_small", 1, "commit", ["f1", "f2"])
    assert a != make_run_id("cfg", "hgb_small", 1, "commit", ["f1", "f2", "f3"])


def test_verify_detects_tampered_or_missing_raw_files(tmp_path):
    from mi.ingest.verify import DataIntegrityError, sha256, verify
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.rds").write_bytes(b"hello")
    lock = {"commit": "abc", "files": [{"name": "a.rds", "bytes": 5, "sha256": sha256(raw / "a.rds"), "expected_rows": 1}]}
    lp = tmp_path / "lock.json"
    lp.write_text(json.dumps(lock))
    assert verify(raw, lp, check_rows=False)["ok"]
    (raw / "a.rds").write_bytes(b"hellO")                   # same size, different content
    with pytest.raises(DataIntegrityError, match="mismatch"):
        verify(raw, lp, check_rows=False)
    (raw / "a.rds").unlink()
    with pytest.raises(DataIntegrityError, match="missing"):
        verify(raw, lp, check_rows=False)


def test_parquet_cache_rebuilds_when_raw_file_changes(tmp_path, monkeypatch):
    pyreadr = pytest.importorskip("pyreadr")
    from mi.ingest import load as L
    raw, proc = tmp_path / "raw", tmp_path / "proc"
    raw.mkdir()
    proc.mkdir()
    monkeypatch.setattr(L, "RAW", raw)
    monkeypatch.setattr(L, "PROCESSED", proc)
    pyreadr.write_rdata(str(raw / "products.rda"), pd.DataFrame({"product_id": ["1"], "brand": ["X"]}), df_name="products")
    L.load.cache_clear()
    assert list(L.load("products").brand) == ["X"]
    pyreadr.write_rdata(str(raw / "products.rda"), pd.DataFrame({"product_id": ["1", "2"], "brand": ["Y", "Z"]}), df_name="products")
    L.load.cache_clear()
    assert list(L.load("products").brand) == ["Y", "Z"]          # stale cache is not reused
    L.load.cache_clear()


def _synthetic_pilot(n=4000, true_dq=0.20, seed=3):
    """SYNTHETIC fixture with a known effect (for estimator behaviour only; never evidence)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    arm = np.where(rng.random(n) < 0.5, "treatment", "control")
    stratum = np.where(rng.random(n) < 0.5, "high", "low")
    p0 = np.where(stratum == "high", 0.40, 0.20)
    base = rng.random(n) < p0
    incr = (arm == "treatment") & ~base & (rng.random(n) < true_dq / (1 - p0))
    buy = base | incr
    spend = np.where(buy, 10.0, 0.0)
    trt = arm == "treatment"
    coupon = np.where(trt & (incr | (base & (rng.random(n) < 0.35))), 0.9, 0.0)
    return pd.DataFrame({"household_id": [f"H{i}" for i in range(n)], "arm": arm, "stratum": stratum,
                         "excluded_pre_treatment": 0, "category_spend_usd": spend, "coupon_cost_usd": coupon,
                         "contact_cost_usd": np.where(trt, 0.03, 0.0), "purchased": buy.astype(int),
                         "opted_out": 0, "complaint": 0})


META = {"source": "SYNTHETIC test fixture", "randomized": True, "assignment_method": "rng", "margin_rate": 0.28,
        "margin_status": "ASSUMED", "rollout_households": 7308, "rollout_fixed_setup_usd": 1500, "stockout_flag": False,
        "preregistration": "tests"}


def test_pilot_estimator_recovers_known_effect_and_applies_hurdle():
    from mi.outcome.pilot import analyze
    r = analyze(_synthetic_pilot(true_dq=0.20), META)
    assert r["provenance"].startswith("SYNTHETIC")
    # true incremental contribution ~ 0.20*(10*0.28 - 0.9) - 0.03 - E[q0]*0.35*0.9 = 0.38 - 0.03 - 0.0945 = 0.2555
    lo, hi = r["ci95"]
    assert lo < 0.2555 < hi
    assert r["by_stratum"] and not r["srm_warning"]
    # positive effect but compared with the commercial hurdle (1500/7308 = 0.205), not with 0
    assert r["commercial_hurdle_per_household"] == round(1500 / 7308, 4)
    small = analyze(_synthetic_pilot(true_dq=0.0), META)
    assert small["decision"] in ("STOP", "INCONCLUSIVE", "CHANGE") and small["decision"] != "EXPAND"


def test_pilot_refuses_observational_or_broken_data():
    from mi.outcome.pilot import PilotDataError, analyze
    df = _synthetic_pilot(n=400)
    with pytest.raises(PilotDataError, match="randomized"):
        analyze(df, {**META, "randomized": False})
    with pytest.raises(PilotDataError, match="duplicated"):
        analyze(pd.concat([df, df.head(3)]), META)
    bad = df.copy()
    bad.loc[0, "category_spend_usd"] = None
    with pytest.raises(PilotDataError, match="ITT"):
        analyze(bad, META)


def test_decide_hurdle_zero_keeps_original_rule():
    from mi.outcome.learning import decide
    o = {"provenance": "SYNTHETIC test", "incremental_contribution_per_household": 0.1, "ci95": [0.05, 0.15],
         "guardrails": {"opt_out_rate": 0.0, "complaint_rate": 0.0, "stockout_flag": False}}
    assert decide(o)["decision"] == "EXPAND"
    assert decide(o, hurdle_usd_per_hh=0.2)["decision"] == "CHANGE"


def test_grocery_decision_code_never_reads_the_hillstrom_namespace():
    """The randomized e-mail experiment is method evidence; it must not feed grocery economics."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "mi"
    for sub in ("decision", "outcome", "model"):
        for f in (root / sub).glob("*.py"):
            text = f.read_text(encoding="utf-8")
            assert "hillstrom" not in text.lower(), f"{f.name} references the Hillstrom experiment"


def test_hillstrom_loader_refuses_wrong_checksum(tmp_path):
    from mi.experiments.hillstrom import HillstromUnavailable, load
    p = tmp_path / "h.csv"
    p.write_text("recency,segment\n1,No E-Mail\n")
    with pytest.raises(HillstromUnavailable, match="checksum"):
        load(p, {"source": {"sha256": "0" * 64, "file": "x"}, "arms": []})


def test_mock_llm_invalid_tool_args_become_tool_errors_and_loop_continues(tmp_path):
    """MOCKED client (not a live LLM): a malformed tool call is returned to the model as an error result."""
    from types import SimpleNamespace as NS
    from mi.agents.llm import LLMClient
    from mi.agents.tools import Toolbox
    from mi.workflow.store import DossierStore

    class Fake:
        def __init__(self, script):
            self.script, self.calls = list(script), []

        def create(self, **kw):
            self.calls.append(kw)
            return self.script.pop(0)
    bad = NS(stop_reason="tool_use", model="mock", content=[NS(type="tool_use", id="t1", name="get_dossier", input={"wrong_arg": 1})])
    final = NS(stop_reason="end_turn", model="mock", content=[NS(type="text", text="done")])
    c = LLMClient.__new__(LLMClient)
    c.model, c.effort, c.available = "mock", "medium", True
    fake = Fake([bad, final])
    c._client = NS(beta=NS(messages=fake))
    tb = Toolbox(DossierStore(tmp_path / "m.sqlite"))
    out = c.run_role("sys", "user", [], lambda n, i: tb.dispatch("research", n, i, None))
    assert out["status"] == "ok" and out["calls"][0]["status"] == "error"
    tool_result = fake.calls[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True and "TypeError" in tool_result["content"]


def test_llm_grounded_path_drops_fabricated_citations(monkeypatch):
    from mi.evidence import rag
    docs = [{"chunk_id": "d#0", "source_id": "dataset_doc", "type": "dataset_documentation", "url": "u", "retrieved_at": "2026-11-14",
             "instruction_like": False, "text": "The study covers 2,469 households who shop at one retailer."}]
    monkeypatch.setattr(rag, "_INDEX", rag.BM25(docs))

    class FakeLLM:  # stands in for LLMClient.grounded_claims; returns one real and one invented span
        def grounded_claims(self, q, chunks):
            return [{"claim": "real", "chunk_id": "d#0", "span": "2,469 households"},
                    {"claim": "invented", "chunk_id": "d#0", "span": "5,000 households in 2019"}]
    r = rag.answer("How many households does the study cover?", min_score=0.1, llm=FakeLLM())
    assert r["method"] == "bm25+llm"
    assert [c["span"] for c in r["supported_claims"]] == ["2,469 households"]
    assert r["rejected_claims"][0]["reason"].startswith("span not found")
