"""The shared grocery bundle: reference metrics are distinct households (not lines), reconcile with the saved opportunity cards, and the
manifest matches the files. Builds nothing into the repo (the bundle lives in the git-ignored handoff/ folder)."""
import json

import pandas as pd
import pytest

from mi.decision import demo_bundle as B
from mi.paths import REPORTS

from tests.conftest import needs_artifacts


def _fixture():
    rows = []
    # h1 buys yogurt twice in H1 (2 lines, 1 buyer), nothing in H2 but keeps shopping (stopped category, still a customer)
    rows += [("h1", "b1", 5, "YOGURT"), ("h1", "b2", 6, "YOGURT"), ("h1", "b3", 30, "SOUP")]
    # h2 buys yogurt in H1 and then never again (left the retailer)
    rows += [("h2", "b4", 7, "YOGURT")]
    # h3 buys yogurt in H2 only
    rows += [("h3", "b5", 40, "YOGURT")]
    # h4: yogurt in weeks 38-49 and none in 50-53 (simple lapsing); h5: yogurt in 38-49 and again in 51 (not lapsing)
    rows += [("h4", "b6", 40, "YOGURT"), ("h5", "b7", 41, "YOGURT"), ("h5", "b8", 51, "YOGURT")]
    t = pd.DataFrame(rows, columns=["household_id", "basket_id", "week", "product_category"])
    t["sales_value"] = 2.0
    return t


def _m(metrics):
    return {x["metric_id"]: x["value"] for x in metrics}


def test_buyers_are_distinct_households_not_lines():
    m = _m(B.reference_metrics(_fixture(), ["YOGURT", "SOUP"]))
    assert m["lines_h1__YOGURT"] == 3 and m["distinct_buyers_h1__YOGURT"] == 2        # 3 lines, 2 households
    assert m["distinct_buyers_h2__YOGURT"] == 3 and m["households_total"] == 5 and m["lines_total"] == 8
    assert m["buyer_change__YOGURT"] == pytest.approx(0.5)


def test_category_only_lapse_versus_left_the_retailer():
    m = _m(B.reference_metrics(_fixture(), ["YOGURT"]))
    assert m["yogurt_stopped_category"] == 2                  # h1 and h2 bought in H1, not in H2
    assert m["yogurt_stopped_but_still_shopping"] == 1       # h1 also bought soup in H2
    assert m["yogurt_left_retailer"] == 1                    # h2 has no line in H2 at all
    assert m["yogurt_stopped_but_still_shopping"] + m["yogurt_left_retailer"] == m["yogurt_stopped_category"]


def test_simple_lapsing_rule():
    m = _m(B.reference_metrics(_fixture(), ["YOGURT"]))
    assert m["lapsing_simple__YOGURT"] == 2                   # h3 and h4 (weeks 38-49, none in 50-53); h5 came back in week 51


def test_every_metric_carries_a_formula_and_a_unit():
    for x in B.reference_metrics(_fixture(), ["YOGURT"]):
        assert x["formula"] and x["unit"] and x["metric_id"] and x["period"]


@needs_artifacts
def test_reference_metrics_reconcile_with_the_saved_opportunity_cards():
    """The bundle's reference metrics must equal the facts already published in reports/opportunities.json (same data, same windows)."""
    from mi.config import load_config
    from mi.ingest.load import load
    cats = list(load_config()["categories"])
    t = load("transactions").merge(load("products")[["product_id", "product_category"]], on="product_id", how="left")
    m = _m(B.reference_metrics(t, cats))
    saved = {f["category"]: f for f in json.loads((REPORTS / "opportunities.json").read_text(encoding="utf-8"))["category_facts"]}
    for c in cats:
        assert m[f"distinct_buyers_h1__{B.slug(c)}"] == saved[c]["buyers_H1"], c
        assert m[f"distinct_buyers_h2__{B.slug(c)}"] == saved[c]["buyers_H2"], c
        assert m[f"buyer_change__{B.slug(c)}"] == pytest.approx(saved[c]["buyer_change_H2_vs_H1"], abs=1e-4), c
    assert m["households_total"] == 2469 and m["lines_total"] == 1_469_307


def test_a_built_bundle_matches_its_manifest():
    mp = B.OUT / "bundle_manifest.json"
    if not mp.exists():
        pytest.skip("bundle not built (python -m mi.decision.demo_bundle)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    assert man["case_id"] == B.CASE_ID and man["complete_dataset"] is True
    for name, meta in man["files"].items():
        assert B.sha256_file(B.OUT / name) == meta["sha256"], name
        assert (B.OUT / name).stat().st_size == meta["bytes"]
    assert (B.OUT / "bundle_manifest.sha256").read_text().split()[0] == B.sha256_file(mp)
    assert any("model" in s for s in man["cannot_reproduce"]) and any("coupon" in s for s in man["cannot_reproduce"])
    ids = [x["metric_id"] for x in man["reference_metrics"]]
    assert len(ids) == len(set(ids))
