from datetime import date

import pytest

from app.models import ClaimFacts
from app.policy.versions import active_clauses, build_versions
from app.retrieval.retrievers import BM25, Retriever
from app.retrieval.text import normalize_item, term_match
from app.verification.verify import ItemContext, decide, verify

ADM, DIS = date(2025, 11, 12), date(2025, 11, 15)


@pytest.fixture(scope="module")
def setup(policy, endorsement):
    versions, _ = build_versions(policy, [endorsement])
    docs = {policy.document_id: policy, endorsement.document_id: endorsement}
    out = {}
    for key, v in (("v1", versions[0]), ("v2", versions[1])):
        cl = active_clauses(v, docs)
        out[key] = (Retriever(cl), {c.clause_id: c for c in cl})
    return out


def sec(cid):
    return cid.split(":")[1]


def classify(setup, text, version="v2", service=date(2025, 11, 13), facts=None):
    retr, by_id = setup[version]
    norm = normalize_item(text)
    ids = list(dict.fromkeys([h.clause_id for h in retr.search(norm.query, "bm25", 8)] +
                             [h.clause_id for h in retr.search(norm.query, "semantic", 8)]))
    ev = [verify(by_id[i], norm, ItemContext(service, ADM, DIS)) for i in ids]
    prec = next(c for c in by_id.values() if c.interpretation.category.value == "precedence")
    return decide(ev, by_id, facts or ClaimFacts(), prec)


def test_exact_keyword_match_bm25_top1(setup):
    retr, _ = setup["v2"]
    assert sec(retr.search("ICU charges", "bm25", 3)[0].clause_id) == "2.3"


def test_paraphrase_found_by_semantic(setup):
    retr, _ = setup["v2"]
    top = [sec(h.clause_id) for h in retr.search("intensive care unit stay", "semantic", 3)]
    assert "2.3" in top


def test_abbreviation_normalisation():
    n = normalize_item("USG Abdomen")
    assert "ultrasonography" in n.normalized.lower() and n.category == "imaging"
    assert normalize_item("Inj. Ceftriaxone 1g").category == "medicine"
    assert normalize_item("OT Charges").category == "operation_theatre"


def test_term_match_direct_general_none():
    gloves = normalize_item("Disposable gloves, masks & syringes")
    assert term_match("disposable gloves", gloves) == "direct"
    assert term_match("consumables", gloves) == "general"
    assert term_match("nebulizer kits", normalize_item("Admission kit")) is None  # shared word 'kit' is not enough


def test_synonym_room_matches_limit_clause(setup):
    d = classify(setup, "Private ward accommodation")
    assert d.status == "covered"
    assert any(sec(cid) == "E1.1" for cid, _ in d.limits)


def test_relevant_exclusion(setup):
    d = classify(setup, "TV & telephone charges")
    assert d.status == "excluded" and [sec(e.clause_id) for e in d.decisive] == ["4.3"]


def test_irrelevant_clause_rejected_despite_similarity(setup):
    retr, by_id = setup["v2"]
    norm = normalize_item("Dental scaling")
    hits = retr.search(norm.query, "semantic", 5)
    evs = [verify(by_id[h.clause_id], norm, ItemContext(date(2025, 11, 13), ADM, DIS)) for h in hits]
    assert all(e.relation in ("irrelevant", "inapplicable") for e in evs)


def test_missing_evidence_not_assumed(setup):
    d = classify(setup, "Dietitian consultation")
    assert d.status == "insufficient" and d.missing


def test_conflicting_evidence_detected(setup):
    d = classify(setup, "Nebulizer kit")
    assert d.status == "conflict"
    assert {sec(e.clause_id) for e in d.decisive} >= {"2.10", "A1.4"}


def test_conditional_exclusion_depends_on_fact(setup):
    assert classify(setup, "MVI Infusion").status == "conditional"
    assert classify(setup, "MVI Infusion", facts=ClaimFacts(vitamin_prescription="yes")).status == "covered"
    assert classify(setup, "MVI Infusion", facts=ClaimFacts(vitamin_prescription="no")).status == "excluded"


def test_amendment_override_changes_interpretation(setup):
    assert classify(setup, "Disposable gloves", "v1").status == "excluded"
    d = classify(setup, "Disposable gloves", "v2")
    assert d.status == "covered" and any("Notwithstanding" in x for x in d.explanation)


def test_similar_but_inapplicable_time_window(setup):
    assert classify(setup, "Follow-up consultation", service=date(2025, 11, 25)).status == "covered"
    assert classify(setup, "Follow-up consultation", service=date(2026, 2, 20)).status == "insufficient"


def test_bm25_scores_are_relevance_not_probability(setup):
    retr, _ = setup["v2"]
    hits = retr.bm25.search("room rent", 5)
    assert hits and hits[0].score > 1  # unbounded BM25 relevance, clearly not a probability


def test_bm25_empty_query_returns_nothing(policy):
    assert BM25(policy.clauses).search("zzzz qqqq", 5) == []
