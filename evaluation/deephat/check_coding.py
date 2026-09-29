"""Tests for the three generated functions; run only after reviewing their source.

Usage: python evaluation/deephat/check_coding.py deephat
This is a test runner, not a sandbox. It executes reviewed generated functions.
"""
import ast
import json
import pathlib
import random
import sys

folder = pathlib.Path(__file__).resolve().parent / sys.argv[1]
rng = random.Random(42)
results = {}

def load(name):
    source = (folder / (name + ".py")).read_text(encoding="utf-8")
    lines = source.splitlines()
    original_count = len(lines)
    syntax_error = None
    while lines:
        try:
            tree = ast.parse("\n".join(lines))
            break
        except SyntaxError as error:
            if syntax_error is None:
                syntax_error = str(error)
            lines.pop()
    else:
        raise ValueError("No parsable source")
    # Remove prose/truncated examples, not function logic. Execute only the
    # reviewed function definitions, retaining the raw syntax failure in scores.
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    module = ast.Module(body=definitions, type_ignores=[])
    namespace = {}
    exec(compile(module, str(folder / (name + ".py")), "exec"), namespace)
    results[name] = {"raw_python_parses": syntax_error is None, "raw_syntax_error": syntax_error, "trailing_lines_removed_for_function_tests": original_count - len(lines)}
    return namespace

def run(name, tests):
    failures = []
    for label, check in tests:
        try:
            check()
        except Exception as error:
            failures.append({"test": label, "error": repr(error)})
    results[name].update({"passed": len(tests) - len(failures), "total": len(tests), "failures": failures})

def equal(got, expected):
    assert got == expected, (got, expected)

merge = load("merge_intervals")["merge_intervals"]
merge_tests = []
def check_merge(intervals):
    before = list(intervals)
    covered = sorted({x for a, b in intervals for x in range(a, b + 1)})
    expected = []
    for x in covered:
        if expected and x == expected[-1][1] + 1:
            expected[-1] = (expected[-1][0], x)
        else:
            expected.append((x, x))
    equal(merge(intervals), expected)
    equal(intervals, before)
for i, intervals in enumerate([[], [(1, 2), (3, 4)], [(5, 7), (-2, 1), (0, 6)], [(2, 2), (2, 2)], [(1, 2), (4, 5)]]):
    merge_tests.append((f"edge_{i}", lambda intervals=intervals: check_merge(intervals)))
for i in range(100):
    intervals = [tuple(sorted((rng.randint(-20, 20), rng.randint(-20, 20)))) for _ in range(rng.randrange(15))]
    merge_tests.append((f"random_{i}", lambda intervals=intervals: check_merge(intervals)))
run("merge_intervals", merge_tests)

count = load("count_statuses")["count_statuses"]
status_tests = []
status_cases = [([], {}), (["t GET / 200 12", "t POST / 404 0", "t GET / 200 3"], {200: 2, 404: 1}), (["t GET / 99 1", "t GET / 600 1", "t GET / 0200 1", "t GET / +200 1", "t GET / 200 1 extra", "t GET / 200"], {}), (["t GET / ٢٠٠ 1", "t GET / ２００ 1", "t GET / ²00 1"], {}), ([" t\tGET / 100 1 ", "t GET / 599 1"], {100: 1, 599: 1}), (["", "   ", "bad", "t GET / 2e2 1", "t GET / abc 1"], {})]
for i, (lines, expected) in enumerate(status_cases):
    status_tests.append((f"edge_{i}", lambda lines=lines, expected=expected: equal(count(iter(lines)), expected)))
for i in range(100):
    codes = [rng.randrange(50, 650) for _ in range(rng.randrange(20))]
    expected = {c: codes.count(c) for c in codes if 100 <= c <= 599}
    lines = [f"t GET / {c} 0" for c in codes]
    status_tests.append((f"random_{i}", lambda lines=lines, expected=expected: equal(count(iter(lines)), expected)))
run("count_statuses", status_tests)

burst = load("failure_window")["has_failure_burst"]
burst_tests = []
def check_burst(times, n, window):
    before = list(times)
    if n <= 0 or window < 0:
        try:
            burst(times, n, window)
        except ValueError:
            equal(times, before)
            return
        raise AssertionError("Expected ValueError")
    expected = any(sum(start <= value <= start + window for value in times) >= n for start in times)
    answer = burst(times, n, window)
    assert type(answer) is bool
    equal(answer, expected)
    equal(times, before)
cases = [([], 1, 0), ([], 0, 1), ([], 1, -1), ([2, 2, 2], 3, 0), ([10, 0, 5], 3, 10), ([10, 0, 5], 3, 9), ([1], 2, 0), ([-1, -5, -3], 3, 4)]
for i, case in enumerate(cases):
    burst_tests.append((f"edge_{i}", lambda case=case: check_burst(*case)))
for i in range(100):
    case = ([rng.randint(-20, 20) for _ in range(rng.randrange(20))], rng.randrange(1, 10), rng.randrange(0, 15))
    burst_tests.append((f"random_{i}", lambda case=case: check_burst(*case)))
run("failure_window", burst_tests)

(folder / "coding_scores.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps({name: {k: v for k, v in score.items() if k != "failures"} for name, score in results.items()}, indent=2))
