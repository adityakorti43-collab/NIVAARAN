"""Print a compact summary of evaluation/results/latest.json."""
import json
from pathlib import Path

o = json.loads((Path(__file__).resolve().parent.parent / "evaluation" / "results" / "latest.json").read_text(encoding="utf-8"))
r = o["results"]
for split in ("eval", "dev", "all"):
    print(split.upper())
    for m, v in r[split]["retrieval"].items():
        print(f"  {m:26s} R@1 {v['recall@1']:.3f}  R@3 {v['recall@3']:.3f}  MRR {v['mrr']:.3f}  nDCG@5 {v['ndcg@5']:.3f}")
    vv = r[split]["verification"]
    print(f"  verification acc {vv['accuracy']:.3f}  macroF1 {vv['macro_f1']:.3f}  unsupported {vv['unsupported_answer_rate']}  items {vv['items']}")
print("split", o["split"]["dev_queries"], "/", o["split"]["eval_queries"], "errors", len(o["error_examples"]))
