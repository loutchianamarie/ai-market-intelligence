"""Conditional scenario arithmetic for a targeted coupon pilot. Deterministic; the LLM never computes money.

Per contacted household h in plan j (category c, segment s, channel k):
    q0_h   = calibrated historical purchase probability (MODEL ESTIMATE; not a response estimate)
    dq_s   = ASSUMED incremental purchase probability from the coupon, CONSTANT within a segment
    g_c    = OBSERVED mean 4-week category spend among buyers x ASSUMED margin rate
    F_c    = coupon face value the RETAILER pays = OBSERVED mean manufacturer coupon x ASSUMED retailer share (coupon_funding)
    r      = ASSUMED share of baseline buyers who redeem (coupon cost on purchases not caused by the coupon)
    c_k    = ASSUMED contact cost of channel k
KEY ASSUMPTION A1: the no-contact (baseline) purchase probability is approximated by q0_h, the propensity under
historical conditions. This is NOT measured: historical data cannot show who would buy without a coupon or whom a
coupon would persuade. Under A1 + constant dq_s, households with lower q0 have higher expected value, which is why a
"MODEL_FILTERED" variant can win. Treat that as a STRATIFICATION HYPOTHESIS for a randomized pilot, not measured targeting.
  expected net value  v_h = dq_s * (g_c - F_c) - c_k - q0_h * r * F_c
  (incremental buyers are assumed to redeem; non-incremental buyers redeem at rate r)
Plan net = scale * sum_h w_k * v_h - fixed_setup, where w_k is the reachable share of channel k.
Break-even uplift for a cohort with mean q0:  dq* = (c_k + q0 * r * F_c) / (g_c - F_c)   (requires g_c > F_c)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from mi.decision.metrics import Undefined

CASES = ("low", "base", "high")


@dataclass
class Assumptions:
    """A named, versioned assumption set. Every number carries a status."""
    margin_rate: float
    redemption_share: float
    contact_cost: dict            # channel -> USD
    reach_share: dict             # channel -> share of segment reachable/consented
    fixed_setup: float
    uplift: dict                  # segment -> dq
    uplift_multiplier: float = 1.0
    scale: float = 1.0
    status: dict = field(default_factory=dict)
    coupon_retailer_share: object = 1.0   # float, or {category: share}; who pays the coupon face value (ASSUMED)

    def dq(self, segment: str) -> float:
        return self.uplift[segment] * self.uplift_multiplier

    def face_share(self, category: str) -> float:
        s = self.coupon_retailer_share
        return float(s.get(category, 1.0)) if isinstance(s, dict) else float(s)


def assumptions_from_config(cfg: dict, case: str = "base", overrides: dict | None = None) -> Assumptions:
    s = cfg["scenario"]
    i = CASES.index(case)

    def pick(entry, favourable_high=True):
        lo, hi = entry.get("range", [entry["value"], entry["value"]])
        if case == "base":
            return entry["value"]
        good = hi if favourable_high else lo
        bad = lo if favourable_high else hi
        return good if case == "high" else bad

    channels = s["channels"] if "channels" in s else {
        "mail_coupon": {"contact_cost": s["contact_cost_per_household"], "reach_share": {"value": 1.0}}}
    contact = {k: pick(v["contact_cost"], favourable_high=False) for k, v in channels.items()}
    reach = {k: pick(v["reach_share"], favourable_high=True) for k, v in channels.items()}
    up = {k: v[i] for k, v in s["incremental_purchase_rate"].items() if isinstance(v, list)}
    a = Assumptions(
        margin_rate=pick(s["contribution_margin_rate"], True),
        redemption_share=pick(s["redemption_share_of_buyers"], False),
        contact_cost=contact, reach_share=reach,
        fixed_setup=pick(s["fixed_setup_per_plan"], False),
        uplift=up, scale=s.get("deployment_scale", {"value": 1.0})["value"] if case == "base"
        else pick(s.get("deployment_scale", {"value": 1.0}), True),
        coupon_retailer_share=s.get("coupon_funding", {}).get("retailer_share", {"value": 1.0})["value"],
        status={"coupon_funding": "ASSUMED", "margin_rate": "ASSUMED", "redemption_share": "ASSUMED", "contact_cost": "ASSUMED",
                "reach_share": "ASSUMED", "fixed_setup": "ASSUMED", "uplift": "ASSUMED", "scale": "ASSUMED",
                "q0": "MODEL ESTIMATE", "category_spend": "OBSERVED", "coupon_face_value": "OBSERVED"})
    for k, v in (overrides or {}).items():
        if k in ("contact_cost", "reach_share") and isinstance(v, dict):
            getattr(a, k).update(v)
        else:
            setattr(a, k, v)
    return a


def household_value(q0, dq, g, face, contact, redemption):
    """Vectorised expected net value per contacted household (USD)."""
    q0 = np.asarray(q0, dtype=float)
    if np.any((q0 < 0) | (q0 > 1)):
        raise ValueError("q0 must be a probability")
    return dq * (g - face) - contact - q0 * redemption * face


def coupon_cost(q0, dq, face, redemption):
    return (np.asarray(q0, dtype=float) * redemption + dq) * face


def break_even_uplift(mean_q0: float, g: float, face: float, contact: float, redemption: float):
    if g is None or face is None:
        return Undefined("missing margin or face value")
    if g <= face:
        return Undefined("contribution per incremental buyer does not exceed coupon value")
    return (contact + mean_q0 * redemption * face) / (g - face)
