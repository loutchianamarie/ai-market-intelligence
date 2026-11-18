"""The master report is generated from computed artifacts; it must agree with them and stay free of placeholders."""
import re

import pytest

from mi.consumer.adapter import EXPORT_PATH, load_case
from mi.paths import REPORTS

pytestmark = pytest.mark.skipif(not (EXPORT_PATH.exists() and (REPORTS / "campaign_lab" / "extras.json").exists()), reason="export or lab results absent")


@pytest.fixture(scope="module")
def text():
    from mi.report.master_report import build
    return build()


def test_report_numbers_match_the_export(text):
    c = load_case().doc
    m, ctl = [a for a in c["observed_arm_metrics"] if a["arm"] == "Mens E-Mail"][0], [a for a in c["observed_arm_metrics"] if a["role"] == "control"][0]
    assert f"{m['buyers']} of {m['n_customers']:,}" in text and f"{ctl['buyers']} of {ctl['n_customers']:,}" in text
    assert f"{c['buyer_impact_per_1000']['value']:.1f} additional buyers per 1,000" in text
    assert c["model_vs_baselines"]["verdict"] in text and EXPORT_PATH.read_bytes() and load_case().sha256 in text


def test_report_has_every_section_and_no_placeholders(text):
    for h in ("## Abstract", "## 1. Business problem", "## 2. Related work", "## 3. Data", "## 4. Methods", "## 5. Results", "## 6. System design",
              "## 7. Threats to validity", "## 8. Ethics", "## 9. Reproducibility", "## 10. Conclusion", "## References", "## Appendix A", "## Appendix B"):
        assert h in text, h
    assert not re.search(r"\bnan\b|\bNone\b|\{[a-z_]+\}", text), re.findall(r"\bnan\b|\bNone\b|\{[a-z_]+\}", text)[:5]


def test_report_states_the_honest_limits(text):
    low = text.lower()
    from mi.seo.geo import geo_state
    geo_phrase = "geo audit is complete (20 of 20" if geo_state()["complete"] else "0 of 20 geo"      # the report follows the real GEO log
    for phrase in ("repeated evaluation", "not shown to beat random", "scenario", geo_phrase, "deterministic_specialists", "references were checked against", "radcliffe (2007) journal issue could not be found"):
        assert phrase in low, phrase
    body = low.split("## appendix a")[0]                                   # the claim ledger legitimately lists an UNKNOWN "measured profit"
    assert "the model wins" not in body and "profit of" not in body


def test_report_figures_exist():
    for f in re.findall(r"\(\.\./(reports/campaign_lab/fig\d[^)]+)\)", __import__("mi.report.master_report", fromlist=["x"]).build()):
        assert (REPORTS.parent / f).exists(), f
