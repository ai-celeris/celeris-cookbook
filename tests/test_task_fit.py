"""Offline tests for the task-fit harness checkers and verdicts."""

from conftest import load_example

task_fit = load_example("task_fit", "examples/task-fit/main.py")


def test_build_checker_shapes():
    exact = task_fit.build_checker({"checker": "exact", "expected": "42"})
    assert exact(" 42 ") and not exact("forty-two")

    contains = task_fit.build_checker({"checker": "contains", "expected": "tokyo"})
    assert contains("The capital is Tokyo.") and not contains("Kyoto")

    json_keys = task_fit.build_checker({"checker": "json_keys", "expected_keys": ["a"]})
    assert json_keys('{"a": 1}') and not json_keys('{"b": 1}')

    labels = task_fit.build_checker(
        {"checker": "label_set", "labels": ["billing", "technical"], "expected": "billing"}
    )
    assert labels("This is a billing question.")
    assert not labels("Could be billing or technical.")

    assert task_fit.build_checker({"checker": "none"}) is None


def test_unknown_checker_raises():
    try:
        task_fit.build_checker({"checker": "vibes", "id": "x"})
    except ValueError as error:
        assert "vibes" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_verdicts():
    assert task_fit.verdict_for(1.0, 0.0, 0)[0] == "strong fit"
    assert task_fit.verdict_for(0.7, 0.0, 0)[0] == "partial fit"
    assert task_fit.verdict_for(0.3, 0.0, 0)[0] == "poor fit"
    assert task_fit.verdict_for(None, 0.0, 0)[0] == "unchecked"
    verdict, reasons = task_fit.verdict_for(1.0, 0.4, 0)
    assert verdict == "partial fit" or "empty" in " ".join(reasons)


def test_shipped_task_files_load():
    good = task_fit.load_tasks(task_fit.HERE / "tasks" / "good-fit-classification.jsonl")
    hard = task_fit.load_tasks(task_fit.HERE / "tasks" / "hard-reasoning.jsonl")
    assert len(good) == 8 and len(hard) == 6
    assert all(entry["task"].max_tokens % 256 == 0 for entry in good + hard)
