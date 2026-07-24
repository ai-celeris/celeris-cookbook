"""Offline tests for the extraction and search example logic."""

from conftest import load_example

extraction = load_example("extraction", "examples/extraction-at-scale/main.py")
instant_search = load_example("instant_search", "examples/instant-search/main.py")


def test_corpus_is_deterministic_with_ground_truth():
    a = extraction.build_corpus(10)
    b = extraction.build_corpus(10)
    assert [doc["truth"] for doc in a] == [doc["truth"] for doc in b]
    assert all(doc["truth"]["invoice_number"] in doc["text"] for doc in a)


def test_parse_extraction_accepts_fenced_and_prose():
    ok = '{"vendor": "Acme Supply Co", "invoice_number": "INV-1", "total_usd": 12.5, "due_date": "2026-01-02"}'
    assert extraction.parse_extraction(ok)["vendor"] == "Acme Supply Co"
    assert extraction.parse_extraction(f"```json\n{ok}\n```") is not None
    assert extraction.parse_extraction("nope") is None
    assert extraction.parse_extraction('{"vendor": "x"}') is None  # missing keys


def test_fields_correct_tolerates_formatting_noise():
    truth = {"vendor": "Acme Supply Co", "invoice_number": "INV-12345", "total_usd": 1234.5, "due_date": "2026-03-04"}
    extracted = {"vendor": "acme supply co", "invoice_number": "inv-12345", "total_usd": "$1,234.50", "due_date": "2026-03-04"}
    assert extraction.fields_correct(extracted, truth) == 4
    assert extraction.fields_correct({"vendor": "Wrong"}, truth) == 0


def test_search_scores_by_term_overlap():
    results = instant_search.search(["refund", "credits"])
    assert results[0] == "Refund policy"
    assert instant_search.search(["zzzz"]) == []


def test_parse_keywords_shapes():
    assert instant_search.parse_keywords('{"keywords": ["a", "b"]}') == ["a", "b"]
    assert instant_search.parse_keywords('```json\n{"keywords": ["x"]}\n```') == ["x"]
    assert instant_search.parse_keywords('{"keywords": []}') is None
    assert instant_search.parse_keywords("not json") is None
