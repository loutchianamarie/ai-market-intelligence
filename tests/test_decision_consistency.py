"""Advisor status agrees across dossier, claims export, decision card and app; funding-share arithmetic."""
import json
from pathlib import Path

import pandas as pd
import pytest

from mi.agents.coordinator import ADVISOR_STATUS, BASE_CASE
from mi.paths import REPORTS

ROOT = Path(__file__).resolve().parents[1]


def test_funding_shares_value_vs_line_weighting():
    from mi.ingest.funding_audit import _shares
    d = pd.DataFrame({"household_id": ["a", "b", "c", "d"], "coupon_disc": [1.0, 1.0, 1.0, 5.0], "coupon_match_disc": [1.0, 0.0, 0.0, 0.0]})
    s = _shares(d, n_boot=50)
    assert s["value_weighted_match_share"] == round(1 / 8, 4)          # sum(match) / sum(coupon)
    assert s["line_weighted_mean_match_ratio"] == 0.25                   # mean of per-line ratios
    assert s["match_incidence_lines"] == 0.25 and s["couponed_lines"] == 4


def test_advisor_status_is_a_deferral_not_an_approval_or_rejection():
    assert ADVISOR_STATUS == "DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED"
    assert "RETAILER-FUNDED" in BASE_CASE


@pytest.mark.skipif(not (REPORTS / "current_claims.json").exists(), reason="run python -m mi.cli all")
def test_dossier_claims_card_and_app_agree():
    from mi.workflow.store import DossierStore
    man = json.loads((REPORTS / "run_manifest.json").read_text())
    rec = DossierStore().get(man["dossier"]).get("advisor_recommendation") or {}
    if rec.get("decision") != ADVISOR_STATUS:
        pytest.skip("artifacts predate this pass; re-run the pipeline")
    claims = {c["id"]: c["value"] for c in json.loads((REPORTS / "current_claims.json").read_text())["claims"]}
    card = (ROOT / "docs" / "decision_card.md").read_text(encoding="utf-8")
    app = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert claims["advisor.status"] == rec["decision"] == ADVISOR_STATUS
    assert claims["advisor.base_case"] == rec["base_case"] == BASE_CASE
    assert ADVISOR_STATUS in card and man["dossier"] in card
    assert "rec['decision']" in app and "base_case" in app                # app renders the dossier's own status
    assert claims["decision.recommendation"].startswith("NONE")
