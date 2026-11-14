"""Metric engine with explicit numerator/denominator contracts (course Module 04 rules).

Rules: sum first, then divide; a zero denominator returns Undefined(reason) instead of 0 or inf;
currencies must match; amounts are rounded only for display.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Undefined:
    reason: str

    def __bool__(self):
        return False

    def __repr__(self):
        return f"Undefined({self.reason!r})"


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValueError(f"currency mismatch: {self.currency} vs {getattr(other, 'currency', other)}")
        return Money(self.amount + other.amount, self.currency)


def ratio(num: float, den: float, reason: str = "zero denominator"):
    if den is None or den == 0:
        return Undefined(reason)
    return num / den


def sum_money(items: Iterable[Money]) -> Money:
    items = list(items)
    if not items:
        raise ValueError("no amounts")
    out = items[0]
    for m in items[1:]:
        out = out + m
    return out


def ctr(clicks: Iterable[float], impressions: Iterable[float]):
    return ratio(sum(clicks), sum(impressions), "no impressions")


def cpm(spend: Iterable[float], impressions: Iterable[float]):
    r = ratio(sum(spend), sum(impressions), "no impressions")
    return r * 1000 if not isinstance(r, Undefined) else r


def cpa(spend: float, completed_orders: int):
    return ratio(spend, completed_orders, "no completed orders")


def cac(acquisition_spend: float, new_customers: int):
    return ratio(acquisition_spend, new_customers, "no new customers")


def roas(attributed_net_revenue: float, ad_spend: float):
    return ratio(attributed_net_revenue, ad_spend, "no ad spend")


def break_even_roas(contribution_margin_rate: float):
    return ratio(1.0, contribution_margin_rate, "zero margin")


def aov(net_revenue: float, completed_orders: int):
    return ratio(net_revenue, completed_orders, "no completed orders")


def roi(incremental_contribution: float, cost: float):
    return ratio(incremental_contribution - cost, cost, "zero cost")


def return_rate(returned: int, completed: int):
    return ratio(returned, completed + returned, "no completed or returned orders")
