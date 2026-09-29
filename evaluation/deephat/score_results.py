"""Separate plain-JSON compliance from classification after extracting JSON.

Does not score correctness of explanations; those require semantic review.
"""
import json
import pathlib
import re
import statistics
import sys
from run_eval import SECURITY

folder = pathlib.Path(__file__).resolve().parent / sys.argv[1]
records = [json.loads(line) for line in (folder / "responses.jsonl").read_text(encoding="utf-8").splitlines()]
by_case = {record["case"]: record for record in records}
scores = []
for case, expected, cwe, _, _ in SECURITY:
    content = by_case[case]["response"].get("message", {}).get("content", "")
    strict = True
    try:
        parsed = json.loads(content)
    except ValueError:
        strict = False
        match = re.search(r"```json\s*(.*?)```", content, re.S)
        try:
            parsed = json.loads(match.group(1)) if match else {}
        except ValueError:
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    pred = parsed.get("vulnerable")
    valid = type(pred) is bool
    scores.append({"case": case, "expected_vulnerable": expected, "prediction": pred, "classification_correct": valid and pred == expected, "plain_json_compliant": strict and valid, "expected_cwe": cwe, "returned_cwe": parsed.get("cwe"), "explanation": parsed.get("explanation"), "truncated": by_case[case]["response"].get("done_reason") == "length"})
summary = {
    "classification_correct_after_json_extraction": sum(r["classification_correct"] for r in scores),
    "security_cases": len(scores),
    "plain_json_compliant": sum(r["plain_json_compliant"] for r in scores),
    "true_positives": sum(r["expected_vulnerable"] and r["prediction"] is True for r in scores),
    "vulnerable_cases": sum(r["expected_vulnerable"] for r in scores),
    "false_positives": sum(not r["expected_vulnerable"] and r["prediction"] is True for r in scores),
    "safe_cases": sum(not r["expected_vulnerable"] for r in scores),
    "unparseable": sum(type(r["prediction"]) is not bool for r in scores),
    "median_generation_tps": statistics.median(r["generation_tps"] for r in records if "generation_tps" in r),
    "note": "Classification scores do not imply correct reasoning. Explanations must be reviewed independently.",
    "cases": scores,
}
(folder / "classification_scores.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
