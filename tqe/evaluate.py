"""Run the checks on every candidate, compare systems, and score the checks against the planted errors.

Run: python -m tqe.evaluate   (writes reports/results.json, exits 1 if the checker misses its gates)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from tqe.checks import DATA, LANGUAGES, check
from tqe.inject import SYSTEMS

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "reports" / "results.json"

# Which check findings count as catching each planted error.
CAUGHT_BY = {
    "drop_negation": {"negation_dropped"},
    "change_number": {"number_mismatch"},
    "swap_unit": {"unit_mismatch"},
    "false_friend": {"forbidden_term"},
    "untranslated": {"untranslated"},
    "omission": {"length_ratio", "number_mismatch", "missing_term", "negation_dropped"},
    "addition": {"length_ratio", "number_mismatch"},
}
CRITICAL_ERRORS = {"drop_negation", "change_number", "swap_unit", "false_friend"}

GATES = {
    "critical_recall_min": 1.0,
    "false_alarm_rate_max": 0.05,
}


def load_candidates() -> list[dict]:
    return json.loads((DATA / "candidates.json").read_text(encoding="utf-8"))


def run(candidates: list[dict]) -> dict:
    rows = []
    for c in candidates:
        result = check(c["source"], c["target"], c["lang"]).to_dict()
        found = {i["check"] for i in result["issues"]}
        planted = c["planted_error"]
        rows.append({
            **c,
            "score": result["score"],
            "verdict": result["verdict"],
            "issues": result["issues"],
            "caught": bool(planted and found & CAUGHT_BY[planted]),
            "false_alarm": planted is None and result["verdict"] != "PASS",
        })

    systems = {}
    for system in SYSTEMS:
        for lang in (None, *LANGUAGES):
            subset = [r for r in rows if r["system"] == system and (lang is None or r["lang"] == lang)]
            key = system if lang is None else f"{system}|{lang}"
            systems[key] = {
                "segments": len(subset),
                "avg_score": round(sum(r["score"] for r in subset) / len(subset), 1),
                "pass": sum(r["verdict"] == "PASS" for r in subset),
                "review": sum(r["verdict"] == "REVIEW" for r in subset),
                "fail": sum(r["verdict"] == "FAIL" for r in subset),
            }

    per_error = defaultdict(lambda: {"planted": 0, "caught": 0})
    for r in rows:
        if r["planted_error"]:
            per_error[r["planted_error"]]["planted"] += 1
            per_error[r["planted_error"]]["caught"] += r["caught"]
    for stats in per_error.values():
        stats["recall"] = round(stats["caught"] / stats["planted"], 3)

    critical = [r for r in rows if r["planted_error"] in CRITICAL_ERRORS]
    clean = [r for r in rows if r["planted_error"] is None]
    planted = [r for r in rows if r["planted_error"]]
    checker = {
        "planted_errors": len(planted),
        "overall_recall": round(sum(r["caught"] for r in planted) / len(planted), 3),
        "critical_recall": round(sum(r["caught"] for r in critical) / len(critical), 3),
        "clean_segments": len(clean),
        "false_alarm_rate": round(sum(r["false_alarm"] for r in clean) / len(clean), 3),
        "per_error": dict(sorted(per_error.items())),
    }
    return {"systems": systems, "checker": checker, "gates": GATES, "rows": rows}


def gate_failures(checker: dict) -> list[str]:
    problems = []
    if checker["critical_recall"] < GATES["critical_recall_min"]:
        problems.append(f"critical_recall {checker['critical_recall']} < {GATES['critical_recall_min']}")
    if checker["false_alarm_rate"] > GATES["false_alarm_rate_max"]:
        problems.append(f"false_alarm_rate {checker['false_alarm_rate']} > {GATES['false_alarm_rate_max']}")
    return problems


def main() -> int:
    report = run(load_candidates())
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{'System':10} {'Avg score':>9} {'Pass':>5} {'Review':>7} {'Fail':>5}")
    for system in SYSTEMS:
        s = report["systems"][system]
        print(f"{system:10} {s['avg_score']:>9} {s['pass']:>5} {s['review']:>7} {s['fail']:>5}")

    c = report["checker"]
    print(f"\nChecker: {c['planted_errors']} planted errors, overall recall {c['overall_recall']}, "
          f"critical recall {c['critical_recall']}, false alarms {c['false_alarm_rate']} "
          f"on {c['clean_segments']} clean segments")
    for error, stats in c["per_error"].items():
        print(f"  {error:14} caught {stats['caught']}/{stats['planted']}")

    problems = gate_failures(c)
    if problems:
        print("\nGate failed: " + "; ".join(problems))
        return 1
    print("\nGates met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
