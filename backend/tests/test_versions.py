from datetime import date

from demo import content as C
from app.ingestion.documents import process_policy_document
from app.models import DocType
from app.policy.versions import active_clauses, build_versions, select_version
from tests.conftest import endorsement_pdf, make_pdf


def _end(tmp_path, **kw):
    return process_policy_document(endorsement_pdf(tmp_path, f"{kw.get('number', 'E-09')}.pdf", **kw), "e.pdf", DocType.endorsement)


def test_base_policy_only(policy):
    versions, conflicts = build_versions(policy, [])
    assert len(versions) == 1 and not conflicts
    assert versions[0].effective_from == date(2025, 4, 1) and versions[0].effective_to == date(2026, 3, 31)


def test_treatment_before_and_after_amendment(policy, endorsement):
    versions, conflicts = build_versions(policy, [endorsement])
    assert [v.label for v in versions] == ["Base policy wording", "Policy + E-01"]
    assert versions[0].effective_to == date(2025, 9, 30)
    before = select_version(date(2025, 9, 20), versions, conflicts)
    after = select_version(date(2025, 11, 12), versions, conflicts)
    assert before.selected.label == "Base policy wording"
    assert after.selected.label == "Policy + E-01"
    assert any("do not apply because they start after" in r for r in before.reasons)


def test_amendment_not_retrospective_and_upload_order_irrelevant(policy, endorsement):
    v1, _ = build_versions(policy, [endorsement])
    sel = select_version(date(2025, 9, 30), v1, [])
    assert sel.selected.label == "Base policy wording"  # day before effective date


def test_superseded_clauses_removed_from_active_set(policy, endorsement):
    versions, _ = build_versions(policy, [endorsement])
    docs = {policy.document_id: policy, endorsement.document_id: endorsement}
    active = {c.section for c in active_clauses(versions[1], docs)}
    assert "2.2" not in active and "5.2" not in active and "E1.1" in active and "E1.2" in active
    assert "2.2" in {c.section for c in active_clauses(versions[0], docs)}


def test_missing_effective_date_is_conflict(policy, tmp_path):
    e = _end(tmp_path, effective=None, applies=None)
    versions, conflicts = build_versions(policy, [e])
    assert len(versions) == 1
    assert any("no effective date" in c for c in conflicts)
    assert select_version(date(2025, 12, 5), versions, conflicts).review_required


def test_policy_number_mismatch(policy, tmp_path):
    e = _end(tmp_path, policy_no="OTHER-999")
    versions, conflicts = build_versions(policy, [e])
    assert len(versions) == 1 and any("refers to policy OTHER-999" in c for c in conflicts)


def test_effective_date_outside_policy_period(policy, tmp_path):
    e = _end(tmp_path, effective="01-May-2026", applies="Hospitalisations commencing on or after 01-May-2026")
    _, conflicts = build_versions(policy, [e])
    assert any("outside the policy period" in c for c in conflicts)


def test_overlapping_replacements_same_date_conflict(policy, tmp_path):
    a = _end(tmp_path, number="E-08")
    b = _end(tmp_path, number="E-09")
    _, conflicts = build_versions(policy, [a, b])
    assert any("both replace clause 5.2" in c for c in conflicts)


def test_unclear_retrospectivity_without_applicability_clause(tmp_path):
    pages = [[("Section 5 Cost Sharing", None), ("5.2 Co-payment", "A co-payment of 10% applies to the admissible claim amount after the deductible.")]]
    header = ["Mini Policy", "Policy Number: SYN-HP-2025-000123", "Policy Period: 01-Apr-2025 to 31-Mar-2026", "Sum Insured: INR 1,00,000"]
    pol = process_policy_document(make_pdf(tmp_path, "mini.pdf", header, pages), "mini.pdf", DocType.policy)
    e = _end(tmp_path, applies="All claims")
    _, conflicts = build_versions(pol, [e])
    assert any("does not state whether it applies retrospectively" in c for c in conflicts)


def test_treatment_date_outside_all_versions(policy, endorsement):
    versions, conflicts = build_versions(policy, [endorsement])
    sel = select_version(date(2026, 6, 1), versions, conflicts)
    assert sel.selected is None and sel.review_required


def test_chained_endorsements_replace_same_section(policy, endorsement, tmp_path):
    e2 = _end(tmp_path, number="E-02", effective="01-Jan-2026", applies="Hospitalisations commencing on or after 01-Jan-2026",
              clauses=[("X2.1 Room Rent", "This endorsement replaces clause 2.2. Room rent, boarding and nursing charges are payable up to INR 9,000 per day.")])
    versions, conflicts = build_versions(policy, [e2, endorsement])  # upload order deliberately reversed
    assert [v.label for v in versions] == ["Base policy wording", "Policy + E-01", "Policy + E-01 + E-02"]
    docs = {policy.document_id: policy, endorsement.document_id: endorsement, e2.document_id: e2}
    active = {c.section for c in active_clauses(versions[2], docs)}
    assert "X2.1" in active and "E1.1" not in active and "2.2" not in active


def test_manual_override_is_labelled_hypothetical(policy, endorsement):
    versions, conflicts = build_versions(policy, [endorsement])
    sel = select_version(date(2025, 11, 12), versions, conflicts, override_id=versions[0].version_id)
    assert sel.overridden and "HYPOTHETICAL" in sel.reasons[0]
