import json

from financial_charts.web.chart_set_store import ChartSetStore


def test_load_returns_empty_when_no_file_exists(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    assert store.load() == {}


def test_save_then_load_round_trips(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    store.save("growth", ["revenue", "eps"])

    assert store.load() == {"growth": ["revenue", "eps"]}


def test_save_preserves_other_existing_entries(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    store.save("growth", ["revenue", "eps"])
    store.save("income", ["dividends", "dividend_yield"])

    assert store.load() == {
        "growth": ["revenue", "eps"],
        "income": ["dividends", "dividend_yield"],
    }


def test_save_overwrites_an_existing_name(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    store.save("growth", ["revenue"])
    store.save("growth", ["revenue", "eps"])

    assert store.load() == {"growth": ["revenue", "eps"]}


def test_load_returns_empty_for_a_corrupt_file_instead_of_crashing(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "chart_sets.json").write_text("not valid json{{{")

    assert store.load() == {}


def test_load_returns_empty_for_a_non_object_json_file(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "chart_sets.json").write_text("[1, 2, 3]")

    assert store.load() == {}


def test_save_leaves_no_temp_file_behind(tmp_path):
    store = ChartSetStore(store_dir=tmp_path)
    store.save("growth", ["revenue"])

    assert list(tmp_path.glob("*.tmp-*")) == []


def test_load_drops_a_malformed_entry_but_keeps_valid_ones_instead_of_crashing(
    tmp_path,
):
    store = ChartSetStore(store_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "chart_sets.json").write_text(
        json.dumps({"good": ["revenue"], "bad_not_a_list": 5, "bad_not_strs": [1, 2]})
    )

    assert store.load() == {"good": ["revenue"]}
