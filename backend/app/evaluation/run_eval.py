"""Reproducible retrieval + evidence-verification evaluation.

Run from backend/:   python -m app.evaluation.run_eval
Writes evaluation/results/latest.json and evaluation/results/latest.md. Every number is computed here.
"""
from __future__ import annotations

import json
import math
import platform
import random
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import EVAL_DIR
from app.models import ClaimFacts, DocType, DocumentRecord
from app.policy.versions import active_clauses, build_versions
from app.retrieval.retrievers import Retriever, reranker_available
from app.retrieval.text import normalize_item
from app.verification.verify import ItemContext, decide, verify

SEED = 42
DEV_FRACTION = 0.4
KS = (1, 3, 5)
METHODS = [("bm25", "raw"), ("bm25", "normalized"), ("semantic", "raw"), ("semantic", "normalized"),
           ("hybrid", "normalized"), ("hybrid_rerank", "normalized")]
LABELS = ["covered", "excluded", "conditional", "conflict", "insufficient"]
NON_DEFINITIVE = {"conditional", "conflict", "insufficient"}


def load_demo_docs() -> tuple[DocumentRecord, DocumentRecord]:
    from demo.generate_demo import OUT_DIR, generate
    from app.ingestion.documents import process_policy_document
    if not (OUT_DIR / "synthetic_policy_v1.pdf").exists():
        generate()
    pol = process_policy_document((OUT_DIR / "synthetic_policy_v1.pdf").read_bytes(), "synthetic_policy_v1.pdf", DocType.policy, True)
    end = process_policy_document((OUT_DIR / "synthetic_endorsement_E01.pdf").read_bytes(), "synthetic_endorsement_E01.pdf", DocType.endorsement, True)
    return pol, end


def split(queries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group-level split so paraphrases of the same concept never straddle dev and eval (no leakage)."""
    groups = sorted({q["group"] for q in queries})
    rng = random.Random(SEED)
    rng.shuffle(groups)
    n_dev = round(len(groups) * DEV_FRACTION)
    dev_groups = set(groups[:n_dev])
    return [q for q in queries if q["group"] in dev_groups], [q for q in queries if q["group"] not in dev_groups]


def ndcg(ranked: list[str], rel: dict[str, int], k: int) -> float:
    dcg = sum((2 ** rel.get(c, 0) - 1) / math.log2(i + 2) for i, c in enumerate(ranked[:k]))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def retrieval_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}
    out = {"queries": n}
    for k in KS:
        out[f"recall@{k}"] = sum(len(set(r["ranked"][:k]) & set(r["rel"])) / len(r["rel"]) for r in rows) / n
        out[f"hit@{k}"] = sum(1 for r in rows if set(r["ranked"][:k]) & set(r["rel"])) / n
    out["precision@3"] = sum(len(set(r["ranked"][:3]) & set(r["rel"])) / 3 for r in rows) / n
    out["mrr"] = sum(next((1 / (i + 1) for i, c in enumerate(r["ranked"]) if c in r["rel"]), 0.0) for r in rows) / n
    out["ndcg@5"] = sum(ndcg(r["ranked"], r["rel"], 5) for r in rows) / n
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "support": tp + fn}


def verification_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}
    acc = sum(r["gold"] == r["pred"] for r in rows) / n
    per = {}
    for lab in LABELS:
        tp = sum(r["gold"] == lab and r["pred"] == lab for r in rows)
        fp = sum(r["gold"] != lab and r["pred"] == lab for r in rows)
        fn = sum(r["gold"] == lab and r["pred"] != lab for r in rows)
        per[lab] = prf(tp, fp, fn)
    present = [l for l in LABELS if per[l]["support"]]
    nd_gold = [r for r in rows if r["gold"] in NON_DEFINITIVE]
    amb_tp = sum(r["gold"] in NON_DEFINITIVE and r["pred"] in NON_DEFINITIVE for r in rows)
    amb_fp = sum(r["gold"] not in NON_DEFINITIVE and r["pred"] in NON_DEFINITIVE for r in rows)
    amb_fn = sum(r["gold"] in NON_DEFINITIVE and r["pred"] not in NON_DEFINITIVE for r in rows)
    conf = Counter((r["gold"], r["pred"]) for r in rows)
    return {
        "items": n, "accuracy": round(acc, 4),
        "macro_f1": round(sum(per[l]["f1"] for l in present) / len(present), 4) if present else 0.0,
        "per_label": per,
        "exclusion_identification": per["excluded"], "conflict_detection": per["conflict"],
        "ambiguity_detection": prf(amb_tp, amb_fp, amb_fn),
        "unsupported_answer_rate": round(sum(r["pred"] not in NON_DEFINITIVE for r in nd_gold) / len(nd_gold), 4) if nd_gold else None,
        "unsupported_answer_rate_definition": "Share of items whose correct answer is non-definitive (conditional, conflict or "
                                              "insufficient evidence) for which the system nevertheless returned covered/excluded.",
        "confusion": [{"gold": g, "pred": p, "count": c} for (g, p), c in sorted(conf.items())],
    }


def run() -> dict:
    t0 = time.time()
    spec = json.loads((EVAL_DIR / "labeled_queries.json").read_text(encoding="utf-8"))
    queries = spec["queries"]
    pol, end = load_demo_docs()
    docs = {pol.document_id: pol, end.document_id: end}
    versions, _ = build_versions(pol, [end])
    vmap = {"v1": versions[0], "v2": versions[1]}
    sec2id = {f"POL:{c.section}": c.clause_id for c in pol.clauses} | {f"E01:{c.section}": c.clause_id for c in end.clauses}
    retrievers = {k: Retriever(active_clauses(v, docs)) for k, v in vmap.items()}
    clause_count = {k: len(r.clauses) for k, r in retrievers.items()}
    dev, ev = split(queries)
    admission, discharge = date(2025, 11, 12), date(2025, 11, 15)
    facts = ClaimFacts()

    per_query = []
    for qd in queries:
        retr = retrievers[qd["version"]]
        clauses = retr.clauses
        rel = {sec2id[k]: g for k, g in qd["relevant"].items()}
        norm = normalize_item(qd["query"])
        runs = {}
        for method, form in METHODS:
            text = qd["query"] if form == "raw" else norm.query
            runs[f"{method}:{form}"] = [h.clause_id for h in retr.search(text, method, k=10)]
        rec = {"id": qd["id"], "group": qd["group"], "query": qd["query"], "version": qd["version"],
               "split": "dev" if qd in dev else "eval", "relevant": qd["relevant"], "rel_ids": rel, "runs": runs,
               "gold": qd["label"], "tags": qd["tags"]}
        if qd["label"] is not None:
            # Same candidate generation + verification path as production adjudication.
            off = qd.get("service_offset_days")
            sdate = discharge + timedelta(days=off) if off is not None else admission + timedelta(days=1)
            ctx = ItemContext(service_date=sdate, admission_date=admission, discharge_date=discharge)
            bm = runs["bm25:normalized"][:8]
            se = runs["semantic:normalized"][:8]
            fused = [h.clause_id for h in retr.search(norm.query, "hybrid", 16)]
            cands = [c for c in fused if c in set(bm) | set(se)]
            evidence = [verify(clauses[c], norm, ctx) for c in cands]
            prec = next((c for c in clauses.values() if c.interpretation.category.value == "precedence"), None)
            dec = decide(evidence, clauses, facts, prec)
            rec["pred"] = dec.status
            rec["decisive"] = [c.split(":")[1] for c in [e.clause_id for e in dec.decisive]]
            rec["explanation"] = " ".join(dec.explanation)
        per_query.append(rec)

    def subset(split_name):
        return [r for r in per_query if split_name == "all" or r["split"] == split_name]

    results = {}
    for split_name in ("eval", "dev", "all"):
        rs = subset(split_name)
        retr_rows = [r for r in rs if r["rel_ids"]]
        results[split_name] = {
            "retrieval": {f"{m}:{f}": retrieval_metrics([{"ranked": r["runs"][f"{m}:{f}"], "rel": r["rel_ids"]} for r in retr_rows])
                          for m, f in METHODS},
            "verification": verification_metrics([{"gold": r["gold"], "pred": r["pred"]} for r in rs if r["gold"] is not None]),
        }

    errors = []
    for r in subset("eval"):
        if r["gold"] is not None and r["gold"] != r["pred"]:
            errors.append({"id": r["id"], "query": r["query"], "type": "verification", "gold": r["gold"], "pred": r["pred"],
                           "decisive": r["decisive"], "explanation": r["explanation"]})
        if r["rel_ids"]:
            for key in ("bm25:raw", "semantic:raw", "hybrid:normalized"):
                top = r["runs"][key][:3]
                if not set(top) & set(r["rel_ids"]):
                    errors.append({"id": r["id"], "query": r["query"], "type": f"retrieval_miss@3 ({key})",
                                   "expected": list(r["relevant"]), "top3": [c.split(":")[1] for c in top]})

    sem = retrievers["v2"].semantic
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": "cd backend && python -m app.evaluation.run_eval",
        "runtime_seconds": round(time.time() - t0, 2),
        "dataset": {"file": "backend/evaluation/labeled_queries.json", "synthetic": True, "query_count": len(queries),
                    "labeled_items": sum(q["label"] is not None for q in queries),
                    "retrieval_queries": sum(bool(q["relevant"]) for q in queries),
                    "clause_count": clause_count, "documents": ["synthetic_policy_v1.pdf", "synthetic_endorsement_E01.pdf"],
                    "label_distribution": dict(Counter(q["label"] or "retrieval_only" for q in queries)),
                    "tag_distribution": dict(Counter(t for q in queries for t in q["tags"]))},
        "split": {"method": "Group-level random split: all paraphrases of a concept share a group and stay on the same side.",
                  "seed": SEED, "dev_fraction": DEV_FRACTION, "dev_queries": len(dev), "eval_queries": len(ev),
                  "dev_groups": sorted({q["group"] for q in dev}), "eval_groups": sorted({q["group"] for q in ev})},
        "configuration": {"keyword": "Okapi BM25 (k1=1.5, b=0.75), own implementation", "semantic_backend": sem.backend,
                          "semantic_model": sem.model_name, "fusion": "Reciprocal rank fusion (c=60) of BM25 and semantic top-15",
                          "reranker": retrievers["v2"].config()["reranker"], "reranker_available": reranker_available(),
                          "query_forms": {"raw": "bill description exactly as written",
                                          "normalized": "abbreviation expansion + category label from the Nivaaran lexicon"},
                          "metadata_filter": "Each query searches only clauses active in its policy version (superseded clauses removed).",
                          "verification": "Production path: union of BM25 and semantic top-8 candidates -> clause-term verification -> decision rules.",
                          "python": platform.python_version()},
        "metric_definitions": {
            "recall@k": "Mean over queries of |relevant ∩ top-k| / |relevant|.",
            "hit@k": "Share of queries with at least one relevant clause in the top k.",
            "precision@3": "Mean of |relevant ∩ top-3| / 3 (bounded above when a query has fewer than 3 relevant clauses).",
            "mrr": "Mean reciprocal rank of the first relevant clause (0 if none in the top 10).",
            "ndcg@5": "Graded nDCG with gains 2^rel - 1 (rel 2 = decisive, 1 = related).",
            "accuracy": "Share of labeled bill items whose predicted evidence label equals the gold label.",
        },
        "results": results,
        "error_examples": errors,
        "per_query": [{k: v for k, v in r.items() if k != "rel_ids"} | {"top3": {m: [c.split(':')[1] for c in r["runs"][m][:3]] for m in r["runs"]}}
                      for r in per_query],
        "limitations": [
            "Small synthetic dataset (one demo policy, one endorsement); results do not generalise to real policy wordings.",
            "Queries, labels and the normalisation lexicon were written by the same team, so the 'normalized' query form may be "
            "optimistic even on the held-out split; the 'raw' rows show performance without the lexicon.",
            "The dev split was used for inspection while building the pipeline; no parameters were tuned on the eval split. "
            "One dev-split error was fixed during development: 'Blood bank processing charges' was wrongly verified as covered "
            "under 2.5 because the bare word 'blood' mapped to the laboratory category; the keyword was narrowed.",
            "Verification metrics depend on deterministic, pattern-based clause interpretation tuned to clearly drafted wordings.",
        ],
    }
    for r in out["per_query"]:
        r.pop("runs", None)
    res_dir = EVAL_DIR / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "latest.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    (res_dir / "latest.md").write_text(to_markdown(out), encoding="utf-8")
    return out


def to_markdown(o: dict) -> str:
    lines = [f"# Nivaaran retrieval & verification evaluation", "", f"Generated {o['generated_at']} — `{o['command']}`", "",
             f"Dataset: {o['dataset']['query_count']} synthetic queries ({o['dataset']['retrieval_queries']} with relevant clauses, "
             f"{o['dataset']['labeled_items']} labeled bill items). Split: seed {o['split']['seed']}, "
             f"{o['split']['dev_queries']} dev / {o['split']['eval_queries']} eval queries.",
             f"Semantic model: `{o['configuration']['semantic_model']}`; reranker: `{o['configuration']['reranker']}`.", "",
             "## Retrieval (eval split)", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---|---|---|---|---|"]
    for m, v in o["results"]["eval"]["retrieval"].items():
        if v:
            lines.append(f"| {m} | {v['recall@1']:.3f} | {v['recall@3']:.3f} | {v['recall@5']:.3f} | {v['mrr']:.3f} | {v['ndcg@5']:.3f} |")
    vm = o["results"]["eval"]["verification"]
    lines += ["", "## Evidence verification (eval split)", "", f"Accuracy {vm['accuracy']:.3f}, macro-F1 {vm['macro_f1']:.3f}, "
              f"unsupported-answer rate {vm['unsupported_answer_rate']}", "", "## Limitations", ""] + [f"- {l}" for l in o["limitations"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    res = run()
    print(json.dumps({"eval": res["results"]["eval"]["retrieval"], "verification": res["results"]["eval"]["verification"]["accuracy"],
                      "errors": len(res["error_examples"])}, indent=2))
