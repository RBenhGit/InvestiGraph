"""Tests for the evaluator registry.

Like `store_test.py`, these monkeypatch `store.PROJECT_ROOT` to a pytest
`tmp_path` rather than touching real project data -- `evaluators.py` derives both
the registry path and the evaluators directory from it at call time precisely so
this works. `HISTORY_FILE_PATH` is cleared in the fixture because `store.py`
honors it ahead of the evaluator branch; several tests below then set it back
deliberately, to pin that the registry does *not* inherit that collapse.
"""

import json

import pytest

import investigraph.history.store as store
from investigraph.history import evaluators
from investigraph.history.models import InvalidHistoryInput, SavedValuation
from investigraph.history.store import save_valuation


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    return tmp_path


def _registry(project_root) -> dict:
    return json.loads((project_root / "data" / "evaluators.json").read_text())


def _saved(evaluator: str, ticker: str = "ZZTEST") -> SavedValuation:
    return SavedValuation(ticker=ticker, current_price=100, evaluator=evaluator)


# --- reading a registry that isn't there, or isn't usable --------------------


def test_lists_the_defaults_when_no_registry_and_no_files_exist(project_root):
    assert evaluators.list_evaluators() == {
        "evaluators": ["Aviv", "Ran"],
        "selected": "Aviv",
    }


def test_a_corrupt_registry_falls_back_to_the_defaults_instead_of_raising(
    project_root,
):
    path = project_root / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json at all")

    assert evaluators.list_evaluators()["evaluators"] == ["Aviv", "Ran"]


def test_a_non_object_registry_falls_back_to_the_defaults(project_root):
    path = project_root / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text('["Aviv"]')

    assert evaluators.list_evaluators()["evaluators"] == ["Aviv", "Ran"]


def test_ignores_non_string_and_blank_entries_in_a_hand_edited_registry(project_root):
    path = project_root / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"evaluators": ["Aviv", 7, "", "  ", None, "Dana"]}))

    assert evaluators.list_evaluators()["evaluators"] == ["Aviv", "Dana"]


# --- the union with what's on disk (no migration step) -----------------------


def test_finds_an_evaluator_that_has_valuations_but_no_registry_entry(project_root):
    # The pre-existing installation: aviv.json/ran.json on disk, no sidecar yet.
    save_valuation(_saved("Dana"))

    assert "Dana" in evaluators.list_evaluators()["evaluators"]


def test_recovers_the_display_casing_from_the_record_not_the_filename(project_root):
    save_valuation(_saved("Aviv Cohen"))

    # The file is avivcohen.json; the pretty name lives inside it.
    assert (project_root / "data" / "evaluators" / "avivcohen.json").exists()
    assert "Aviv Cohen" in evaluators.list_evaluators()["evaluators"]


def test_a_deleted_registry_rebuilds_itself_from_the_valuation_files(project_root):
    evaluators.add_evaluator("Dana")
    save_valuation(_saved("Dana"))
    (project_root / "data" / "evaluators.json").unlink()

    assert "Dana" in evaluators.list_evaluators()["evaluators"]


def test_an_empty_file_falls_back_to_its_slug_for_a_display_name(project_root):
    path = project_root / "data" / "evaluators" / "dana.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]")

    assert "dana" in evaluators.list_evaluators()["evaluators"]


def test_a_corrupt_valuation_file_still_lists_its_evaluator_under_its_slug(
    project_root,
):
    path = project_root / "data" / "evaluators" / "dana.json"
    path.parent.mkdir(parents=True)
    path.write_text("{{{ truncated")

    assert "dana" in evaluators.list_evaluators()["evaluators"]


def test_the_registry_casing_wins_over_the_on_disk_name(project_root):
    save_valuation(_saved("aviv"))

    # "Aviv" is a registry default and shares a slug with the on-disk "aviv",
    # so it must appear once, spelled the registry's way.
    names = evaluators.list_evaluators()["evaluators"]
    assert names.count("Aviv") == 1
    assert "aviv" not in names


# --- adding ------------------------------------------------------------------


def test_add_persists_the_name_and_creates_an_empty_valuation_file(project_root):
    result = evaluators.add_evaluator("Dana")

    assert "Dana" in result["evaluators"]
    assert _registry(project_root)["evaluators"] == ["Aviv", "Ran", "Dana"]
    # The empty file is what makes Dana visible to every other terminal before
    # she has saved anything -- the whole point of the move off localStorage.
    assert (project_root / "data" / "evaluators" / "dana.json").read_text() == "[]"


def test_add_trims_surrounding_whitespace(project_root):
    evaluators.add_evaluator("  Dana  ")

    assert "Dana" in evaluators.list_evaluators()["evaluators"]


def test_adding_an_existing_name_is_a_no_op_not_a_duplicate(project_root):
    evaluators.add_evaluator("Dana")
    evaluators.add_evaluator("dana")
    evaluators.add_evaluator("D.A.N.A.")

    assert _registry(project_root)["evaluators"].count("Dana") == 1
    assert len(evaluators.list_evaluators()["evaluators"]) == 3


def test_add_never_overwrites_an_existing_evaluators_valuations(project_root):
    save_valuation(_saved("Dana"))
    evaluators.add_evaluator("Dana")

    on_disk = json.loads(
        (project_root / "data" / "evaluators" / "dana.json").read_text()
    )
    assert len(on_disk) == 1


def test_add_rejects_a_blank_name(project_root):
    with pytest.raises(InvalidHistoryInput):
        evaluators.add_evaluator("   ")


def test_add_rejects_a_name_that_sanitizes_away_entirely(project_root):
    # Would otherwise land in data/evaluators/.json -- a file no name can
    # address, shared by every such evaluator.
    with pytest.raises(InvalidHistoryInput):
        evaluators.add_evaluator("נדב")

    assert not (project_root / "data" / "evaluators" / ".json").exists()


# --- removing ----------------------------------------------------------------


def test_remove_drops_the_name_and_its_empty_file(project_root):
    evaluators.add_evaluator("Dana")
    result = evaluators.remove_evaluator("Dana")

    assert "Dana" not in result["evaluators"]
    assert not (project_root / "data" / "evaluators" / "dana.json").exists()


def test_remove_never_deletes_saved_valuations(project_root):
    save_valuation(_saved("Dana"))
    evaluators.remove_evaluator("Dana")

    # The confirm text has always promised this ("History files are not
    # deleted"), and hiding real data would be worse than showing the name.
    on_disk = json.loads(
        (project_root / "data" / "evaluators" / "dana.json").read_text()
    )
    assert len(on_disk) == 1


def test_an_evaluator_with_valuations_reappears_after_removal(project_root):
    save_valuation(_saved("Dana"))
    evaluators.remove_evaluator("Dana")

    assert "Dana" in evaluators.list_evaluators()["evaluators"]


def test_remove_leaves_an_unparseable_file_in_place(project_root):
    path = project_root / "data" / "evaluators" / "dana.json"
    path.parent.mkdir(parents=True)
    path.write_text("{{{ truncated")
    evaluators.remove_evaluator("Dana")

    assert path.exists()


def test_remove_rejects_a_blank_name(project_root):
    with pytest.raises(InvalidHistoryInput):
        evaluators.remove_evaluator("  ")


# --- selection ---------------------------------------------------------------


def test_the_selection_round_trips(project_root):
    evaluators.set_selected("Ran")

    assert evaluators.list_evaluators()["selected"] == "Ran"
    assert _registry(project_root)["selected"] == "Ran"


def test_the_first_evaluator_is_selected_when_nothing_is_stored(project_root):
    assert evaluators.list_evaluators()["selected"] == "Aviv"


def test_set_selected_rejects_an_unknown_evaluator(project_root):
    with pytest.raises(InvalidHistoryInput):
        evaluators.set_selected("Nobody")


def test_set_selected_accepts_an_evaluator_known_only_from_disk(project_root):
    save_valuation(_saved("Dana"))

    assert evaluators.set_selected("Dana")["selected"] == "Dana"


def test_a_stale_selection_falls_back_to_the_first_evaluator(project_root):
    path = project_root / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"evaluators": ["Aviv", "Ran"], "selected": "Ghost"}))

    # Never hand the template a selected value that isn't one of its options.
    assert evaluators.list_evaluators()["selected"] == "Aviv"


def test_removing_the_selected_evaluator_moves_the_selection(project_root):
    evaluators.add_evaluator("Dana")
    evaluators.set_selected("Dana")
    result = evaluators.remove_evaluator("Dana")

    assert result["selected"] == "Aviv"


def test_selection_is_none_when_every_evaluator_is_gone(project_root):
    path = project_root / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"evaluators": [], "selected": None}))

    assert evaluators.list_evaluators() == {"evaluators": [], "selected": None}


# --- HISTORY_FILE_PATH must not collapse identities --------------------------


def test_identities_survive_the_history_file_path_env_var(project_root, monkeypatch):
    # That env var collapses every evaluator's *records* into one shared file,
    # which is documented behavior. It must not also collapse who exists: the
    # registry is about identity, not storage location.
    monkeypatch.setenv("HISTORY_FILE_PATH", str(project_root / "shared.json"))

    evaluators.add_evaluator("Dana")
    result = evaluators.list_evaluators()

    assert result["evaluators"] == ["Aviv", "Ran", "Dana"]
    assert (project_root / "data" / "evaluators" / "dana.json").exists()


# --- atomicity ---------------------------------------------------------------


def test_writing_the_registry_leaves_no_temp_file_behind(project_root):
    evaluators.add_evaluator("Dana")

    leftovers = list((project_root / "data").glob("*.tmp-*"))
    assert leftovers == []
