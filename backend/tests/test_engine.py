"""Financial engine tests. Expected values are computed by hand from the synthetic policy rules:
v1: room 5,000/day, ICU 10,000/day, ambulance 2,000/hospitalisation, deductible 10,000, co-pay 10%.
v2 (E-01): room 7,500/day, co-pay 5%, consumables (gloves/masks/syringes) payable up to 5,000/hospitalisation."""
from decimal import Decimal as D

import pytest

from app.adjudication.adjudicate import adjudicate
from app.engine.calc import DuplicateAdjustment, EngineItem, EngineParams, Ledger, check_invariants, run
from app.models import ClaimFacts, Hypotheticals, LimitSpec
from app.money import allocate, money


def params(**kw):
    base = dict(deductible=D("10000.00"), deductible_clause="P:5.1", deductible_used=D("0.00"), copay_percent=D("10"),
                copay_clause="P:5.2", sum_insured=D("500000.00"), sum_insured_used=D("0.00"),
                order=["exclusion", "item_limit", "deductible", "copay", "sum_insured_cap"], order_clause="P:5.3")
    base.update(kw)
    return EngineParams(**base)


def test_per_day_limit():
    it = EngineItem("A", D("18000.00"), "covered", D("2"), [("P:2.2", LimitSpec(amount=D("5000"), basis="per_day"))])
    r = run([it], params(deductible=None, copay_percent=None), "low")
    assert r.payable["A"] == D("10000.00")


def test_shared_limit_not_over_allocated():
    lim = LimitSpec(amount=D("5000"), basis="per_hospitalisation")
    items = [EngineItem("A", D("3500.00"), "covered", limits=[("E:1.3", lim)]),
             EngineItem("B", D("2500.00"), "covered", limits=[("E:1.3", lim)])]
    r = run(items, params(deductible=None, copay_percent=None), "low")
    assert r.payable == {"A": D("3500.00"), "B": D("1500.00")}
    assert r.pool_usage["E:1.3"] == (D("5000.00"), D("5000.00"))


def test_deductible_applied_once_per_claim_not_per_item():
    items = [EngineItem(str(i), D("10000.00"), "covered") for i in range(3)]
    r = run(items, params(copay_percent=None), "low")
    assert sum(r.payable.values()) == D("20000.00")
    assert r.deductible_applied == D("10000.00")


def test_deductible_respects_amount_already_used():
    r = run([EngineItem("A", D("50000.00"), "covered")], params(copay_percent=None, deductible_used=D("7000.00")), "low")
    assert r.payable["A"] == D("47000.00")


def test_copay_after_deductible():
    r = run([EngineItem("A", D("50000.00"), "covered")], params(), "low")
    assert r.payable["A"] == D("36000.00")  # (50,000 - 10,000) x 90%


def test_rule_order_from_policy_changes_result():
    it = [EngineItem("A", D("18000.00"), "covered", D("2"), [("P:2.2", LimitSpec(amount=D("5000"), basis="per_day"))])]
    limits_first = run(it, params(copay_percent=None), "low").payable["A"]
    deductible_first = run(it, params(copay_percent=None, order=["exclusion", "deductible", "item_limit", "copay", "sum_insured_cap"]), "low").payable["A"]
    assert limits_first == D("0.00") and deductible_first == D("8000.00")


def test_excluded_item_gets_no_further_adjustments():
    items = [EngineItem("X", D("1000.00"), "excluded", exclusion_clauses=["P:4.3"]), EngineItem("A", D("20000.00"), "covered")]
    r = run(items, params(), "low")
    assert r.payable["X"] == 0
    assert [a.stage for a in r.adjustments if a.item_id == "X"] == ["exclusion"]


def test_duplicate_adjustment_refused():
    led = Ledger("low")
    led.add("exclusion", "A", D("10"), ["P:4.1"], "x")
    with pytest.raises(DuplicateAdjustment):
        led.add("exclusion", "A", D("10"), ["P:4.1"], "x")


def test_unresolved_items_never_silently_payable():
    items = [EngineItem("U", D("900.00"), "unresolved"), EngineItem("A", D("20000.00"), "covered")]
    low, high = run(items, params(), "low"), run(items, params(), "high")
    assert low.payable["U"] == 0 and high.payable["U"] > 0
    assert all(i["passed"] for i in check_invariants(items, low, high, params()))


def test_sum_insured_cap():
    r = run([EngineItem("A", D("700000.00"), "covered")], params(deductible=None, copay_percent=None), "low")
    assert r.payable["A"] == D("500000.00")


def test_missing_cost_sharing_is_noted_not_invented():
    r = run([EngineItem("A", D("100.00"), "covered")], params(deductible=None, copay_percent=None, sum_insured=None), "low")
    assert r.payable["A"] == D("100.00")
    assert any("No deductible" in n for n in r.notes) and any("Sum insured not found" in n for n in r.notes)


def test_rounding_allocation_reconciles():
    parts = allocate(D("100.00"), [D("1"), D("1"), D("1")])
    assert sum(parts) == D("100.00") and sorted(parts) == [D("33.33"), D("33.33"), D("33.34")]
    assert money("1,25,900.00") == D("125900.00")
    with pytest.raises(TypeError):
        money(0.1)


def test_demo_claim_base_version(make_claim):
    claim, docs = make_claim(with_endorsement=False)
    a = adjudicate(claim, docs)
    s = a.summary
    # eligible: 10,000 room + 10,000 ICU + 45,000 + 12,000 + 18,000 + 3,200 + 2,500 + 2,400 + 2,000 amb + 1,000 follow-up = 106,100
    assert s.eligible_definite == D("106100.00")
    assert s.payable_low == D("86490.00")      # (106,100 - 10,000) x 90%
    assert s.payable_high == D("89640.00")     # (106,100 + 1,800 + 900 + 800 - 10,000) x 90%
    assert s.patient_high == D("39410.00") and s.total_billed == D("125900.00")
    assert all(i["passed"] for i in a.invariants)


def test_demo_claim_with_endorsement(make_claim):
    claim, docs = make_claim()
    a = adjudicate(claim, docs)
    s = a.summary
    assert s.eligible_definite == D("114600.00")  # room 15,000 and consumables 3,500 now eligible
    assert s.payable_low == D("99370.00")         # (114,600 - 10,000) x 95%
    assert s.payable_high == D("102695.00")       # (118,100 - 10,000) x 95%
    rows = {r.original_description: r for r in a.rows}
    assert rows["Deluxe Room Charges"].status == "partially_payable" and rows["Deluxe Room Charges"].eligible_amount == D("15000.00")
    assert rows["Disposable gloves, masks & syringes"].status == "potentially_covered"
    assert rows["Nebulizer kit"].status == "conflicting_evidence" and rows["Nebulizer kit"].manual_review
    assert rows["MVI Infusion"].status == "conditional"
    assert rows["Dietitian consultation"].status == "insufficient_evidence"
    assert rows["TV & telephone charges"].status == "potentially_excluded"
    assert rows["Ambulance pickup"].eligible_amount == D("2000.00")
    assert sum(r.payable_low for r in a.rows) == s.payable_low


def test_fact_change_resolves_conditional(make_claim):
    claim, docs = make_claim(facts=ClaimFacts(vitamin_prescription="yes"))
    a = adjudicate(claim, docs)
    assert a.summary.payable_low == D("101080.00")  # (114,600 + 1,800 - 10,000) x 95%


def test_waiting_period_not_satisfied_excludes_claim(make_claim, policy):
    claim, docs = make_claim(diagnosis="Hernia repair", title="Hernia repair")
    p2 = policy.model_copy(update={"metadata": {**policy.metadata, "continuous_coverage_since": "2025-04-01"}})
    docs = {**docs, policy.document_id: p2}
    a = adjudicate(claim, docs)
    assert any(c.status == "not_satisfied" for c in a.claim_checks)
    assert a.summary.payable_high == D("0.00")
    assert all(r.status == "potentially_excluded" for r in a.rows)


def test_what_if_uses_same_engine(make_claim):
    claim, docs = make_claim()
    a = adjudicate(claim, docs, Hypotheticals(copay_percent=D("0")))
    assert a.summary.payable_low == D("104600.00") and a.hypothetical
    b = adjudicate(claim, docs, Hypotheticals(removed_items=["L01"]))
    assert b.summary.payable_low == D("85120.00")  # (114,600 - 15,000 - 10,000) x 95%


def test_hypothetical_treatment_date_switches_version(make_claim):
    from datetime import date
    claim, docs = make_claim()
    a = adjudicate(claim, docs, Hypotheticals(treatment_date=date(2025, 9, 20)))
    assert a.version.selected.label == "Base policy wording" and a.summary.payable_low == D("86490.00")
