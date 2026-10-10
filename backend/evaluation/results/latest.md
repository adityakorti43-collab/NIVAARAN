# Nivaaran retrieval & verification evaluation

Generated 2026-10-10T13:49:15+00:00 — `cd backend && python -m app.evaluation.run_eval`

Dataset: 60 synthetic queries (54 with relevant clauses, 53 labeled bill items). Split: seed 42, 23 dev / 37 eval queries.
Semantic model: `sentence-transformers/all-MiniLM-L6-v2`; reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`.

## Retrieval (eval split)

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |
|---|---|---|---|---|---|
| bm25:raw | 0.657 | 0.838 | 0.864 | 0.826 | 0.822 |
| bm25:normalized | 0.798 | 0.980 | 0.990 | 0.970 | 0.970 |
| semantic:raw | 0.763 | 0.889 | 0.939 | 0.934 | 0.901 |
| semantic:normalized | 0.808 | 0.950 | 1.000 | 0.985 | 0.965 |
| hybrid:normalized | 0.838 | 0.975 | 1.000 | 1.000 | 0.990 |
| hybrid_rerank:normalized | 0.838 | 1.000 | 1.000 | 1.000 | 1.000 |

## Evidence verification (eval split)

Accuracy 1.000, macro-F1 1.000, unsupported-answer rate 0.0

## Limitations

- Small synthetic dataset (one demo policy, one endorsement); results do not generalise to real policy wordings.
- Queries, labels and the normalisation lexicon were written by the same team, so the 'normalized' query form may be optimistic even on the held-out split; the 'raw' rows show performance without the lexicon.
- The dev split was used for inspection while building the pipeline; no parameters were tuned on the eval split. One dev-split error was fixed during development: 'Blood bank processing charges' was wrongly verified as covered under 2.5 because the bare word 'blood' mapped to the laboratory category; the keyword was narrowed.
- Verification metrics depend on deterministic, pattern-based clause interpretation tuned to clearly drafted wordings.
