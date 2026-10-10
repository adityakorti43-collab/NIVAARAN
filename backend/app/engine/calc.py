"""Deterministic financial rules engine.

- Decimal arithmetic only, quantised to paise with ROUND_HALF_UP.
- Stage order comes from the policy's computation-order clause. If the policy does not state one, a
  documented default is used and the result is flagged as relying on an assumed order.
- Every adjustment has a unique ID (scenario, stage, item, clause). Registering the same adjustment twice
  raises, which prevents double deductions.
- Claim-level amounts (deductible, co-payment, sum-insured cap) are computed once on the claim total and
  allocated to items with the largest-remainder method, so they are never applied independently per item.
- Shared per-hospitalisation limits are drawn down in bill-line order and never over-allocated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Optional

from app.models import Adjustment, LimitSpec, TraceStep
from app.money import ZERO, allocate, fmt, q

DEFAULT_ORDER = ["exclusion", "item_limit", "deductible", "copay", "sum_insured_cap"]
STAGE_LABEL = {"exclusion": "Exclusions and non-payable items", "item_limit": "Item limits and sub-limits",
               "deductible": "Deductible", "copay": "Co-payment", "sum_insured_cap": "Sum insured cap"}


class DuplicateAdjustment(Exception):
    pass


@dataclass
class EngineItem:
    item_id: str
    claimed: Decimal
    basis: Literal["covered", "excluded", "unresolved"]
    quantity: Decimal = Decimal("1")
    limits: list[tuple[str, LimitSpec]] = field(default_factory=list)
    exclusion_clauses: list[str] = field(default_factory=list)
    label: str = ""


@dataclass
class EngineParams:
    deductible: Optional[Decimal]
    deductible_clause: Optional[str]
    deductible_used: Decimal
    copay_percent: Optional[Decimal]
    copay_clause: Optional[str]
    sum_insured: Optional[Decimal]
    sum_insured_used: Decimal
    order: list[str]
    order_clause: Optional[str]
    hypothetical: set[str] = field(default_factory=set)  # which params are what-if overrides
    limit_overrides: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class EngineResult:
    scenario: str
    payable: dict[str, Decimal]
    after_limits: dict[str, Decimal]
    by_stage: dict[str, dict[str, Decimal]]
    adjustments: list[Adjustment]
    trace: list[TraceStep]
    notes: list[str]
    deductible_applied: Decimal
    copay_applied: Decimal
    pool_usage: dict[str, tuple[Decimal, Decimal]]  # clause -> (pool, allocated)


class Ledger:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.items: dict[str, Adjustment] = {}

    def add(self, stage: str, item_id: Optional[str], amount: Decimal, clauses: list[str], desc: str, hypothetical=False) -> str:
        key = f"{self.scenario}:{stage}:{item_id or 'claim'}:{'+'.join(clauses) or 'none'}"
        if key in self.items:
            raise DuplicateAdjustment(f"Adjustment {key} already applied; refusing to deduct twice.")
        self.items[key] = Adjustment(adjustment_id=key, stage=stage, item_id=item_id, amount=q(amount), clause_ids=clauses,
                                     description=desc, hypothetical=hypothetical)
        return key


def _limit_cap(item: EngineItem, lim: LimitSpec, override: Optional[Decimal], si: Optional[Decimal]) -> tuple[Optional[Decimal], str]:
    amount = override if override is not None else lim.amount
    if amount is None and lim.percent_of_sum_insured is not None and si is not None:
        amount = q(si * lim.percent_of_sum_insured / Decimal(100))
    if amount is None:
        return None, "limit amount could not be established"
    if lim.basis == "per_day":
        return q(amount * item.quantity), f"{fmt(amount)} per day x {item.quantity} day(s)"
    if lim.basis == "per_eye":
        return q(amount * item.quantity), f"{fmt(amount)} per eye x {item.quantity} (quantity used as eye count)"
    return q(amount), f"{fmt(amount)} {lim.basis.replace('_', ' ')}"


def run(items: list[EngineItem], p: EngineParams, scenario: Literal["low", "high"]) -> EngineResult:
    led = Ledger(scenario)
    cur = {i.item_id: q(i.claimed) for i in items}
    by_stage: dict[str, dict[str, Decimal]] = {s: {} for s in DEFAULT_ORDER + ["unresolved_hold"]}
    trace: list[TraceStep] = []
    notes: list[str] = []
    after_limits: dict[str, Decimal] = {}
    pools: dict[str, tuple[Decimal, Decimal]] = {}
    ded_applied = cop_applied = ZERO
    total = lambda: sum(cur.values(), ZERO)
    start = total()
    trace.append(TraceStep(step_no=1, stage="billed", description="Original itemised bill total (amounts exactly as billed).",
                           amount_before=start, amount_after=start))

    order = [s for s in p.order if s in DEFAULT_ORDER]
    if "exclusion" not in order:
        order = ["exclusion"] + order
        notes.append("The computation-order clause does not mention exclusions; they are removed first.")
    for s in DEFAULT_ORDER:
        if s not in order:
            order.append(s)
            notes.append(f"The computation-order clause does not mention '{STAGE_LABEL[s]}'; it is applied last.")

    for stage in order:
        before = total()
        ids: list[str] = []
        clauses: list[str] = []
        desc = STAGE_LABEL[stage]
        if stage == "exclusion":
            for it in items:
                if it.basis == "excluded" and cur[it.item_id] > 0:
                    amt = cur[it.item_id]
                    ids.append(led.add("exclusion", it.item_id, amt, it.exclusion_clauses, f"{it.label}: removed as not payable."))
                    by_stage["exclusion"][it.item_id] = amt
                    clauses += it.exclusion_clauses
                    cur[it.item_id] = ZERO
                elif it.basis == "unresolved" and scenario == "low" and cur[it.item_id] > 0:
                    amt = cur[it.item_id]
                    ids.append(led.add("unresolved_hold", it.item_id, amt, [], f"{it.label}: held out as unresolved (not assumed payable)."))
                    by_stage["unresolved_hold"][it.item_id] = amt
                    cur[it.item_id] = ZERO
            desc = "Excluded items removed" + ("; unresolved items held out (not assumed payable)" if scenario == "low"
                                               else "; unresolved items assumed resolved favourably (upper bound only)")
        elif stage == "item_limit":
            for it in items:
                for cid, lim in it.limits:
                    if cur[it.item_id] <= 0:
                        continue
                    cap, how = _limit_cap(it, lim, p.limit_overrides.get(cid), p.sum_insured)
                    hyp = cid in p.limit_overrides
                    if cap is None:
                        notes.append(f"{it.label}: {how}; limit {cid} not applied — review required.")
                        continue
                    if lim.basis in ("per_hospitalisation", "per_claim", "per_policy_year"):
                        pool, used = pools.get(cid, (cap, ZERO))
                        allowed = min(cur[it.item_id], pool - used)
                        pools[cid] = (pool, used + allowed)
                        reduction = cur[it.item_id] - allowed
                        how += f" (shared limit; {fmt(pool - used)} remaining before this item)"
                    else:
                        reduction = max(ZERO, cur[it.item_id] - cap)
                    if reduction > 0:
                        ids.append(led.add("item_limit", it.item_id, reduction, [cid],
                                           f"{it.label}: limited to {how}." + (" HYPOTHETICAL limit." if hyp else ""), hyp))
                        by_stage["item_limit"][it.item_id] = by_stage["item_limit"].get(it.item_id, ZERO) + reduction
                        cur[it.item_id] = q(cur[it.item_id] - reduction)
                        clauses.append(cid)
            after_limits = dict(cur)
        elif stage == "deductible":
            if p.deductible is None:
                notes.append("No deductible found in the applicable policy version; none applied.")
            else:
                remaining = max(ZERO, p.deductible - p.deductible_used)
                ded = min(remaining, total())
                if ded > 0:
                    keys = list(cur)
                    for k, share in zip(keys, allocate(ded, [cur[k] for k in keys])):
                        if share > 0:
                            ids.append(led.add("deductible", k, share, [p.deductible_clause] if p.deductible_clause else [],
                                               "Share of claim-level deductible (allocated proportionally).", "deductible" in p.hypothetical))
                            by_stage["deductible"][k] = share
                            cur[k] = q(cur[k] - share)
                ded_applied = ded
                clauses += [p.deductible_clause] if p.deductible_clause else []
                desc = (f"Deductible {fmt(p.deductible)} per policy year; {fmt(p.deductible_used)} already used; "
                        f"{fmt(ded)} applied to this claim" + (" (HYPOTHETICAL value)" if "deductible" in p.hypothetical else ""))
        elif stage == "copay":
            if p.copay_percent is None:
                notes.append("No co-payment found in the applicable policy version; none applied.")
            else:
                base = total()
                cop = q(base * p.copay_percent / Decimal(100))
                if cop > 0:
                    keys = list(cur)
                    for k, share in zip(keys, allocate(cop, [cur[k] for k in keys])):
                        if share > 0:
                            ids.append(led.add("copay", k, share, [p.copay_clause] if p.copay_clause else [],
                                               f"Share of {p.copay_percent}% co-payment.", "copay" in p.hypothetical))
                            by_stage["copay"][k] = share
                            cur[k] = q(cur[k] - share)
                cop_applied = cop
                clauses += [p.copay_clause] if p.copay_clause else []
                desc = f"Co-payment {p.copay_percent}% of {fmt(base)}" + (" (HYPOTHETICAL value)" if "copay" in p.hypothetical else "")
        elif stage == "sum_insured_cap":
            if p.sum_insured is None:
                notes.append("Sum insured not found; the sum-insured cap could not be checked — review required.")
                desc = "Sum insured cap (not checked: sum insured not found)"
            else:
                avail = max(ZERO, p.sum_insured - p.sum_insured_used)
                excess = max(ZERO, total() - avail)
                if excess > 0:
                    keys = list(cur)
                    for k, share in zip(keys, allocate(excess, [cur[k] for k in keys])):
                        if share > 0:
                            ids.append(led.add("sum_insured_cap", k, share, [], "Share of reduction to available sum insured."))
                            by_stage["sum_insured_cap"][k] = share
                            cur[k] = q(cur[k] - share)
                desc = f"Available sum insured {fmt(avail)}; " + ("no reduction needed" if excess == 0 else f"reduced by {fmt(excess)}")
        trace.append(TraceStep(step_no=len(trace) + 1, stage=stage, description=desc, amount_before=before, amount_after=total(),
                               clause_ids=sorted(set(clauses)), adjustments=ids))
    trace.append(TraceStep(step_no=len(trace) + 1, stage="estimated_payable",
                           description="Estimated payable amount (an estimate, not an insurer decision).",
                           amount_before=total(), amount_after=total()))
    return EngineResult(scenario=scenario, payable=cur, after_limits=after_limits or dict(cur), by_stage=by_stage,
                        adjustments=list(led.items.values()), trace=trace, notes=notes, deductible_applied=ded_applied,
                        copay_applied=cop_applied, pool_usage=pools)


def check_invariants(items: list[EngineItem], low: EngineResult, high: EngineResult, p: EngineParams) -> list[dict]:
    out = []

    def add(name: str, ok: bool, detail: str = ""):
        out.append({"name": name, "passed": bool(ok), "detail": detail})

    for r in (low, high):
        add(f"[{r.scenario}] amounts are non-negative", all(v >= 0 for v in r.payable.values()) and all(a.amount >= 0 for a in r.adjustments))
        add(f"[{r.scenario}] payable <= eligible after limits <= claimed",
            all(r.payable[i.item_id] <= r.after_limits.get(i.item_id, i.claimed) <= i.claimed for i in items))
        claimed = sum((i.claimed for i in items), ZERO)
        reductions = sum((a.amount for a in r.adjustments), ZERO)
        payable = sum(r.payable.values(), ZERO)
        add(f"[{r.scenario}] claimed = payable + all adjustments (reconciles)", claimed == payable + reductions,
            f"{fmt(claimed)} = {fmt(payable)} + {fmt(reductions)}")
        ids = [a.adjustment_id for a in r.adjustments]
        add(f"[{r.scenario}] no adjustment applied twice", len(ids) == len(set(ids)))
        add(f"[{r.scenario}] shared limits not over-allocated", all(used <= pool for pool, used in r.pool_usage.values()))
        if p.deductible is not None:
            add(f"[{r.scenario}] deductible within remaining amount", r.deductible_applied <= max(ZERO, p.deductible - p.deductible_used))
        add(f"[{r.scenario}] all values rounded to paise", all(v == q(v) for v in r.payable.values()))
        if p.sum_insured is not None:
            add(f"[{r.scenario}] payable within available sum insured", payable <= max(ZERO, p.sum_insured - p.sum_insured_used))
    add("unresolved items are never counted as payable in the definite estimate",
        all(low.payable[i.item_id] == 0 for i in items if i.basis == "unresolved"))
    add("excluded items have zero payable", all(low.payable[i.item_id] == 0 and high.payable[i.item_id] == 0 for i in items if i.basis == "excluded"))
    add("lower estimate <= upper estimate", sum(low.payable.values(), ZERO) <= sum(high.payable.values(), ZERO))
    return out
