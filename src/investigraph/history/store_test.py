"""Tests ported from legacy/eps_evaluation/src/history/index.test.ts (persistence,
malformed-entry filtering, evaluator-scoped storage, get_all_latest_valuations) and
resolveHistoryFilePath's own tests at the bottom of that same file.

The evaluator-scoped tests exercise the real `PROJECT_ROOT`-relative paths (the
evaluator branch of `resolve_history_file_path` is only reachable when no explicit
`file_path` is passed), but instead of the original's approach of writing into the
real project root and manually backing up/restoring history.json, they monkeypatch
`store.PROJECT_ROOT` to a pytest `tmp_path` -- same code path, no risk of ever
touching a real user's saved valuations.
"""

import json
from pathlib import Path

import pytest

import investigraph.history.store as store
from investigraph.history.models import (
    InvalidHistoryInput,
    SavedValuation,
    ScenarioValuation,
    ValuationNotFound,
)
from investigraph.history.store import (
    delete_valuation,
    get_all_latest_valuations,
    get_history,
    resolve_history_file_path,
    save_valuation,
)


def _valuation(**overrides) -> SavedValuation:
    fields = dict(
        ticker="AAPL",
        current_price=220.5,
        currency="USD",
        eps_ttm=6.5,
        growth_rate_percent=12,
        exit_pe_multiple=25,
        required_return_percent=15,
        years=5,
        rule_one_fair_value=180.2,
    )
    fields.update(overrides)
    return SavedValuation(**fields)


# ---------------------------------------------------------------------------
# save / get / delete
# ---------------------------------------------------------------------------


def test_get_history_returns_empty_list_when_file_does_not_exist(tmp_path):
    history_file = tmp_path / "history-test.json"
    assert get_history(None, history_file) == []


def test_saves_a_valuation_and_reads_it_back(tmp_path):
    history_file = tmp_path / "history-test.json"

    saved = save_valuation(_valuation(), history_file)
    assert saved.ticker == "AAPL"
    assert saved.id is not None
    assert saved.evaluated_at is not None

    history = get_history(None, history_file)
    assert len(history) == 1
    assert history[0].ticker == "AAPL"
    assert history[0].current_price == 220.5


def test_filters_history_by_ticker_case_insensitively_and_sorts_newest_first(tmp_path):
    history_file = tmp_path / "history-test.json"

    save_valuation(
        _valuation(
            ticker="AAPL",
            evaluated_at="2026-08-01T10:00:00.000Z",
            current_price=210,
        ),
        history_file,
    )
    save_valuation(
        _valuation(
            ticker="MSFT",
            evaluated_at="2026-08-05T10:00:00.000Z",
            current_price=420,
            eps_ttm=11.5,
        ),
        history_file,
    )
    save_valuation(
        _valuation(
            ticker="AAPL",
            evaluated_at="2026-08-10T10:00:00.000Z",
            current_price=225,
        ),
        history_file,
    )

    everything = get_history(None, history_file)
    assert len(everything) == 3
    assert everything[0].ticker == "AAPL"
    assert everything[0].current_price == 225  # Newest overall.

    aapl_only = get_history("aapl", history_file)
    assert len(aapl_only) == 2
    assert aapl_only[0].current_price == 225
    assert aapl_only[1].current_price == 210


def test_deletes_a_valuation_by_id(tmp_path):
    history_file = tmp_path / "history-test.json"

    save_valuation(_valuation(id="test-id-1", ticker="GOOGL"), history_file)

    deleted = delete_valuation("test-id-1", history_file)
    assert deleted.ticker == "GOOGL"

    assert get_history(None, history_file) == []

    with pytest.raises(ValuationNotFound):
        delete_valuation("test-id-1", history_file)


def test_rejects_a_blank_ticker_on_save(tmp_path):
    history_file = tmp_path / "history-test.json"

    with pytest.raises(InvalidHistoryInput):
        save_valuation(_valuation(ticker="   "), history_file)


def test_rejects_a_blank_id_on_delete(tmp_path):
    history_file = tmp_path / "history-test.json"

    with pytest.raises(InvalidHistoryInput):
        delete_valuation("   ", history_file)


def test_saving_an_existing_id_replaces_it_in_place_and_stays_newest_first(tmp_path):
    history_file = tmp_path / "history-test.json"

    save_valuation(_valuation(id="dup", current_price=100), history_file)
    save_valuation(
        _valuation(id="other", ticker="MSFT", current_price=50, eps_ttm=11.5),
        history_file,
    )
    save_valuation(_valuation(id="dup", current_price=150), history_file)

    history = get_history(None, history_file)
    assert len(history) == 2
    assert [r.id for r in history].count("dup") == 1
    dup = next(r for r in history if r.id == "dup")
    assert dup.current_price == 150


def test_saves_and_reads_back_a_three_scenario_record_distinct_from_legacy_flat_shape(
    tmp_path,
):
    # Regression coverage: the web UI's 3-scenario save writes base/bear/bull
    # ScenarioValuation objects instead of the legacy flat fields. Confirms the
    # shape actually round-trips through save/read/filter.
    history_file = tmp_path / "history-test.json"

    saved = save_valuation(
        SavedValuation(
            ticker="NVDA",
            current_price=300,
            currency="USD",
            eps_ttm=12.5,
            years=10,
            base=ScenarioValuation(
                growth_rate_percent=20,
                exit_pe_multiple=15,
                required_return_percent=15,
                mos_percent=25,
                rule_one_fair_value=270,
            ),
            bear=ScenarioValuation(
                growth_rate_percent=15,
                exit_pe_multiple=10,
                required_return_percent=15,
                mos_percent=50,
                rule_one_fair_value=140,
            ),
            bull=ScenarioValuation(
                growth_rate_percent=25,
                exit_pe_multiple=20,
                required_return_percent=12,
                mos_percent=10,
                rule_one_fair_value=400,
            ),
            notes="scenario round-trip test",
        ),
        history_file,
    )

    assert saved.ticker == "NVDA"
    # The legacy flat fields must NOT be silently populated -- this record is
    # scenario-shaped only.
    assert saved.rule_one_fair_value is None

    history = get_history("NVDA", history_file)
    assert len(history) == 1

    record = history[0]
    assert record.base == ScenarioValuation(
        growth_rate_percent=20,
        exit_pe_multiple=15,
        required_return_percent=15,
        mos_percent=25,
        rule_one_fair_value=270,
    )
    assert record.bear.rule_one_fair_value == 140
    assert record.bull.rule_one_fair_value == 400


# ---------------------------------------------------------------------------
# read_history_file resilience to a hand-edited file
# ---------------------------------------------------------------------------


def test_skips_malformed_entries_instead_of_throwing_on_the_whole_history(
    tmp_path, caplog
):
    history_file = tmp_path / "history.json"
    history_file.write_text(
        json.dumps(
            [
                None,
                "not-a-record",
                42,
                {
                    "id": "good-1",
                    "ticker": "AAPL",
                    "evaluated_at": "2026-08-01T00:00:00.000Z",
                    "years": 10,
                },
            ]
        ),
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        everything = get_history(None, history_file)
    assert len(everything) == 1
    assert everything[0].id == "good-1"
    # Dropping a malformed row must be logged, not silent -- a dropped row here
    # would otherwise be written back out (permanently) on the next unrelated save.
    assert "dropped 3 malformed entries" in caplog.text

    filtered = get_history("AAPL", history_file)
    assert len(filtered) == 1


def test_read_history_file_returns_empty_list_for_non_array_json(tmp_path):
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps({"not": "an array"}), encoding="utf-8")

    assert get_history(None, history_file) == []


# ---------------------------------------------------------------------------
# Atomic writes -- reusing investigraph.cache.store.TemplateCache's pattern.
# ---------------------------------------------------------------------------


def test_write_leaves_no_temp_file_behind(tmp_path):
    history_file = tmp_path / "history-test.json"
    save_valuation(_valuation(), history_file)

    assert list(tmp_path.glob("*.tmp-*")) == []
    assert history_file.exists()


def test_save_and_delete_round_trip_through_atomic_writes_repeatedly(tmp_path):
    history_file = tmp_path / "history-test.json"

    for i in range(5):
        save_valuation(_valuation(id=f"id-{i}", ticker=f"T{i}"), history_file)

    assert len(get_history(None, history_file)) == 5
    delete_valuation("id-2", history_file)
    assert len(get_history(None, history_file)) == 4
    assert list(tmp_path.glob("*.tmp-*")) == []


# ---------------------------------------------------------------------------
# Evaluator-scoped storage (data/evaluators/<name>.json)
#
# These exercise the real on-disk paths (rather than an injected file_path)
# because the evaluator branch of resolve_history_file_path is only reachable
# when no explicit path is passed -- monkeypatching PROJECT_ROOT to a tmp_path
# keeps this isolated from any real project data.
# ---------------------------------------------------------------------------


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    return tmp_path


EVALUATOR_A = "VitestEvalA"
EVALUATOR_B = "VitestEvalB"
TICKER = "ZZVITEST"


def _evaluator_record(**overrides) -> SavedValuation:
    fields = dict(
        ticker=TICKER,
        current_price=100,
        currency="USD",
        eps_ttm=5,
        years=10,
        base=ScenarioValuation(
            growth_rate_percent=10,
            exit_pe_multiple=15,
            required_return_percent=15,
            mos_percent=0,
            rule_one_fair_value=60,
        ),
    )
    fields.update(overrides)
    return SavedValuation(**fields)


def test_routes_a_save_with_an_evaluator_to_data_evaluators_sanitized_name_json(
    project_root,
):
    save_valuation(_evaluator_record(evaluator=EVALUATOR_A))

    eval_file = project_root / "data" / "evaluators" / "vitestevala.json"
    on_disk = json.loads(eval_file.read_text())
    assert len(on_disk) == 1
    assert on_disk[0]["ticker"] == TICKER
    assert on_disk[0]["evaluator"] == EVALUATOR_A


def test_strips_illegal_filename_characters_from_the_evaluator_name(project_root):
    save_valuation(_evaluator_record(evaluator="Vitest Eval A!"))

    eval_file = project_root / "data" / "evaluators" / "vitestevala.json"
    on_disk = json.loads(eval_file.read_text())
    assert on_disk[0]["evaluator"] == "Vitest Eval A!"


def test_reads_back_only_that_evaluators_own_records(project_root):
    save_valuation(_evaluator_record(id="a-1", evaluator=EVALUATOR_A))
    save_valuation(_evaluator_record(id="b-1", evaluator=EVALUATOR_B))

    result = get_history(TICKER, None, EVALUATOR_A)
    assert [r.id for r in result] == ["a-1"]


def test_merges_legacy_history_records_with_no_evaluator_into_an_evaluators_history(
    project_root,
):
    legacy_file = project_root / "history.json"
    legacy_file.write_text(
        json.dumps(
            [
                {
                    "id": "legacy-1",
                    "ticker": TICKER,
                    "evaluated_at": "2026-01-01T00:00:00.000Z",
                    "current_price": 90,
                    "currency": "USD",
                    "eps_ttm": 5,
                    "years": 10,
                    "rule_one_fair_value": 55,
                }
            ]
        ),
        encoding="utf-8",
    )

    save_valuation(_evaluator_record(id="a-1", evaluator=EVALUATOR_A))

    result = get_history(TICKER, None, EVALUATOR_A)
    # Both the evaluator's own record and the un-owned legacy one are visible --
    # that is the whole point of the merge (old records aren't orphaned).
    assert sorted(r.id for r in result) == ["a-1", "legacy-1"]


def test_does_not_merge_a_legacy_record_belonging_to_a_different_evaluator(
    project_root,
):
    legacy_file = project_root / "history.json"
    legacy_file.write_text(
        json.dumps(
            [
                {
                    "id": "legacy-owned",
                    "ticker": TICKER,
                    "evaluated_at": "2026-01-01T00:00:00.000Z",
                    "current_price": 90,
                    "currency": "USD",
                    "eps_ttm": 5,
                    "years": 10,
                    "evaluator": EVALUATOR_B,
                }
            ]
        ),
        encoding="utf-8",
    )

    save_valuation(_evaluator_record(id="a-1", evaluator=EVALUATOR_A))

    result = get_history(TICKER, None, EVALUATOR_A)
    assert [r.id for r in result] == ["a-1"]


def test_delete_checks_the_legacy_file_for_a_stranded_copy(project_root):
    legacy_file = project_root / "history.json"
    legacy_file.write_text(
        json.dumps(
            [
                {
                    "id": "stranded",
                    "ticker": TICKER,
                    "evaluated_at": "2026-01-01T00:00:00.000Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    deleted = delete_valuation("stranded", None, EVALUATOR_A)
    assert deleted.id == "stranded"
    assert json.loads(legacy_file.read_text()) == []


def test_get_all_latest_valuations_keeps_one_row_per_ticker_evaluator_pair(
    project_root,
):
    save_valuation(
        _evaluator_record(
            id="a-1", evaluated_at="2026-02-01T00:00:00.000Z", evaluator=EVALUATOR_A
        )
    )
    save_valuation(
        _evaluator_record(
            id="b-1", evaluated_at="2026-03-01T00:00:00.000Z", evaluator=EVALUATOR_B
        )
    )

    result = get_all_latest_valuations()
    mine = [r for r in result if r.ticker == TICKER]
    # Keyed on ticker alone (the previous behavior) this would return only 'b-1',
    # silently hiding evaluator A's opinion.
    assert sorted(r.id for r in mine) == ["a-1", "b-1"]


def test_get_all_latest_valuations_keeps_only_the_most_recent_within_a_pair(
    project_root,
):
    save_valuation(
        _evaluator_record(
            id="a-old", evaluated_at="2026-01-01T00:00:00.000Z", evaluator=EVALUATOR_A
        )
    )
    save_valuation(
        _evaluator_record(
            id="a-new", evaluated_at="2026-06-01T00:00:00.000Z", evaluator=EVALUATOR_A
        )
    )

    result = get_all_latest_valuations()
    mine = [r for r in result if r.ticker == TICKER]
    assert [r.id for r in mine] == ["a-new"]


# ---------------------------------------------------------------------------
# resolve_history_file_path's own branches.
# ---------------------------------------------------------------------------


def test_prefers_an_explicit_path_over_everything_else(monkeypatch):
    monkeypatch.setenv("HISTORY_FILE_PATH", "/tmp/from-env.json")
    assert resolve_history_file_path("/tmp/explicit.json", "Someone") == Path(
        "/tmp/explicit.json"
    )


def test_uses_history_file_path_env_var_resolved_to_an_absolute_path(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    monkeypatch.setenv("HISTORY_FILE_PATH", "./relative-history.json")
    assert resolve_history_file_path() == tmp_path / "relative-history.json"


def test_history_file_path_env_var_takes_precedence_over_the_evaluator(monkeypatch):
    monkeypatch.setenv("HISTORY_FILE_PATH", "/tmp/from-env.json")
    # Documented consequence, not an accident: setting this env var disables
    # per-evaluator history entirely, since it's checked before the evaluator
    # branch.
    assert resolve_history_file_path(None, "Someone") == Path("/tmp/from-env.json")


def test_falls_back_to_project_root_history_json_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    assert resolve_history_file_path() == store.PROJECT_ROOT / "history.json"


def test_routes_to_evaluators_dir_ignoring_case_and_punctuation(monkeypatch):
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    assert resolve_history_file_path(None, "  Aviv Cohen!  ") == (
        store.PROJECT_ROOT / "data" / "evaluators" / "avivcohen.json"
    )


def test_treats_a_blank_evaluator_as_no_evaluator_at_all(monkeypatch):
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    assert resolve_history_file_path(None, "   ") == store.PROJECT_ROOT / "history.json"
