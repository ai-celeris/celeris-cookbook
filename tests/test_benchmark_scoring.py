"""Offline tests for the benchmark harness scoring and statistics."""

from conftest import load_example

benchmark = load_example("benchmark", "examples/benchmark/main.py")


def test_json_checker_accepts_plain_and_fenced_json():
    check = benchmark.json_checker(["name", "quantity"])
    assert check('{"name": "flour", "quantity": 3}')
    assert check('```json\n{"name": "flour", "quantity": 3}\n```')
    assert check('Here you go: {"name": "flour", "quantity": 3}')


def test_json_checker_rejects_bad_or_incomplete_json():
    check = benchmark.json_checker(["name", "quantity"])
    assert not check("not json")
    assert not check('{"name": "flour"}')  # missing key
    assert not check('{"name": "flour", "quantity": ')  # truncated


def test_label_checker_requires_exactly_the_expected_label():
    check = benchmark.label_checker("positive")
    assert check("The sentiment is positive.")
    assert not check("It could be positive or negative.")
    assert not check("The sentiment is negative.")
    assert not check("")


def test_answer_checker_matches_substring_case_insensitively():
    check = benchmark.answer_checker("paris")
    assert check("The capital of France is Paris.")
    assert not check("The capital of France is Lyon.")


def test_percentile_bounds():
    values = list(range(1, 101))
    assert benchmark.percentile(values, 0.5) in (50, 51)
    assert benchmark.percentile(values, 0.99) in (99, 100)
    assert benchmark.percentile([], 0.5) == 0.0


def test_summarize_reports_counts():
    samples = [
        benchmark.Sample(category="classify", ok=True, ttft_ms=100, total_ms=100, correct=True),
        benchmark.Sample(category="classify", ok=True, ttft_ms=200, total_ms=200, correct=False),
        benchmark.Sample(category="summarize", ok=True, ttft_ms=150, total_ms=150),
        benchmark.Sample(category="short-answer", ok=False, error="throttle", throttles=3),
    ]
    report = benchmark.summarize(samples, elapsed_s=1.0)
    assert "4 (3 ok, 1 failed)" in report
    assert "1/2 (50%)" in report
    assert "n/a (no objective check)" in report
