"""Static fallback for the five-minute demo: the grocery decision and work queue as ONE self-contained HTML page.

Built from the same saved artifacts the app reads (model report, portfolio, the latest grocery dossier and its work
queue, the GEO log). No figure is typed here, no JavaScript and no network are needed, and nothing is sent.

  python -m mi.decision.demo_backup          -> reports/demo_fallback/grocery_demo_backup.html
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date

from mi.paths import REPORTS
from mi.seo.geo import geo_state
from mi.workflow.store import DossierStore, WorkQueue

OUT = REPORTS / "demo_fallback" / "grocery_demo_backup.html"
E = html.escape


def latest_dossier_id(store: DossierStore) -> str | None:
    with store._conn() as c:
        r = c.execute("SELECT opportunity_id FROM dossier_versions WHERE note='pilot drafted' ORDER BY created_at DESC LIMIT 1").fetchone()
    return r[0] if r else None


def render(store: DossierStore, oid: str, model: dict, port: dict, geo: dict) -> str:
    d = store.get(oid)
    rec = d.get("advisor_recommendation") or {}
    sel = "model_" + model["selected_model"]
    ap, rule, pop = model["test"][sel]["AP"], model["test"]["rule_repeat"]["AP"], model["test"]["rule_popularity"]["AP"]
    pm = port["heuristic"]["base"]["net"]
    items = WorkQueue(store).list(oid)
    rows = "".join(f"<tr><td>{E(w['item_id'])}</td><td><b>{E(w['status'])}</b></td><td>{E(w['payload']['kind'])}</td><td>{E(w['payload']['title'])}</td>"
                   f"<td>{E(str(w['payload']['owner']))}</td><td>${w['payload']['budget_usd']:,.0f}</td><td>{E(str(w['payload']['due_date']))}</td></tr>" for w in items)
    li, m, r = geo["by_intent"]["Learn"], geo["mention_rate"], geo["recommendation_rate"]
    geo_line = (f"{geo['answers_logged']}/{geo['answers_target']} answers from {' and '.join(geo['assistants'])} (not ChatGPT or Gemini), one dated run, region not set; "
                f"{geo['brand']} is a public analogue, not the dataset retailer. Mentioned {m['num']}/{m['den']}, recommended {r['num']}/{r['den']}; Learn: mentioned "
                f"{li['mentioned']}/{li['n']}, recommended {li['recommended']}/{li['n']} (not zero visibility, not lost sales). Content actions are hypotheses; publication needs approval."
                if geo["complete"] else f"{geo['answers_logged']}/{geo['answers_target']} GEO answers logged: collection incomplete.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Grocery decision: static backup</title>
<style>body{{font:15px/1.45 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d1d1b}}
table{{border-collapse:collapse;width:100%;margin:8px 0 18px}}td,th{{border:1px solid #cfcfca;padding:5px 8px;text-align:left;vertical-align:top}}th{{background:#f2f2ee}}
.k{{display:inline-block;border:1.5px solid #8a5a00;color:#8a5a00;border-radius:4px;padding:0 6px;font-size:12px;font-weight:600}}.big{{font-size:28px;font-weight:700}}
.box{{background:#fdf6e3;border:1px solid #e6d9a8;padding:10px 14px;margin:12px 0}}</style></head><body>
<h1>Where should the next CRM budget go?</h1>
<p>Static backup of the grocery decision screen (app tab 9). Anonymous US grocery retailer, 84.51&deg; Complete Journey panel (2,469 households, 2017). Generated {date.today().isoformat()} from the saved artifacts; <b>nothing is sent, spent or published</b>.</p>
<table><tr><th>Model AP (locked test)</th><th>Base-case recommendation</th><th>Popularity-led mailing (base)</th><th>Dossier</th></tr>
<tr><td class="big">{ap:.3f}</td><td class="big">{E(port['recommended_base'].split(':')[0])}</td><td class="big">&minus;${abs(pm):,.0f}</td><td class="big">{E(oid)}<br><span style="font-size:15px">state {E(d['state'])} (v{d['version']})</span></td></tr>
<tr><td>+{ap - rule:.3f} vs repeat rule ({rule:.3f}); popularity {pop:.3f}. <span class="k">HISTORICAL OBSERVATION</span> purchase propensity, not coupon response</td>
<td><span class="k">ASSUMPTION</span> every plan loses per contacted household</td><td><span class="k">ASSUMPTION</span> <span class="k">COMPANY SCALE ASSUMED</span> infeasible comparator (over budget)</td><td><span class="k">SIMULATED WORKFLOW</span> sandbox CRM only</td></tr></table>
<div class="box"><b>Advisor status: {E(rec.get('decision', 'n/a'))}.</b> {E(rec.get('reason', ''))}<br><i>{E(rec.get('status', ''))}</i></div>
<h2>Advisor work queue (simulated CRM)</h2>
<table><tr><th>Item</th><th>Status</th><th>Kind</th><th>Title</th><th>Owner</th><th>Budget</th><th>Due</th></tr>{rows}</table>
<p>READY items cost $0. The paid coupon test (design only) and the public content draft stay <b>BLOCKED_PENDING_APPROVAL</b>: a named human must verify consent and stock first, and approval is bound to the plan hash.</p>
<h2>Discovery audit (separate public analogue)</h2><p>{E(geo_line)}</p>
<p><small>Separate case: the randomized apparel e-mail experiment is a different retailer and dataset; its effect is never applied to this grocery decision.</small></p>
</body></html>
"""


def main() -> int:
    store = DossierStore()
    oid = latest_dossier_id(store)
    if not oid:
        print("no grocery dossier: run python -m mi.agents.coordinator run", file=sys.stderr)
        return 2
    model = json.loads((REPORTS / "model_report.json").read_text(encoding="utf-8"))
    port = json.loads((REPORTS / "portfolio.json").read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(store, oid, model, port, geo_state()), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPORTS.parent)} from dossier {oid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
