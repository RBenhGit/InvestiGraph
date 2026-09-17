"""Route contract tests for /api/evaluators.

Deliberately NOT using `history_route_test.py`'s `client` fixture: that one sets
`HISTORY_FILE_PATH`, which `store.resolve_history_file_path` honors ahead of the
evaluator branch, so the per-evaluator directory these routes are about would
never be touched. These monkeypatch `store.PROJECT_ROOT` instead, the same way
`store_test.py` does.
"""

import json

import pytest

import investigraph.history.store as store
from investigraph.web.app import create_app
from investigraph.web.chart_set_store import ChartSetStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("HISTORY_FILE_PATH", raising=False)
    return create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()


def test_get_returns_the_defaults_on_a_fresh_install(client):
    body = client.get("/api/evaluators").get_json()

    assert body["ok"] is True
    assert body["data"] == {"evaluators": ["Aviv", "Ran"], "selected": "Aviv"}


def test_post_adds_an_evaluator_and_returns_the_new_list(client):
    response = client.post("/api/evaluators", json={"name": "Dana"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["evaluators"] == ["Aviv", "Ran", "Dana"]


def test_a_posted_evaluator_is_visible_to_every_other_client(client, tmp_path):
    client.post("/api/evaluators", json={"name": "Dana"})

    # A second client is a second browser: same server, same list. This is the
    # behavior the whole change exists to provide.
    other = create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()
    assert "Dana" in other.get("/api/evaluators").get_json()["data"]["evaluators"]


def test_post_rejects_a_blank_name_with_400(client):
    response = client.post("/api/evaluators", json={"name": "   "})

    assert response.status_code == 400
    assert response.get_json()["error"]["type"] == "INVALID_INPUT"


def test_post_rejects_a_name_with_no_usable_characters_with_400(client):
    response = client.post("/api/evaluators", json={"name": "נדב"})

    assert response.status_code == 400


def test_post_with_no_body_is_a_400_not_a_500(client):
    response = client.post("/api/evaluators")

    assert response.status_code == 400


def test_delete_removes_an_evaluator(client):
    client.post("/api/evaluators", json={"name": "Dana"})
    response = client.delete("/api/evaluators/Dana")

    assert response.status_code == 200
    assert "Dana" not in response.get_json()["data"]["evaluators"]


def test_delete_does_not_remove_saved_valuations(client, tmp_path):
    client.post("/api/history", json={"ticker": "AAPL", "evaluator": "Dana"})
    client.delete("/api/evaluators/Dana")

    on_disk = json.loads((tmp_path / "data" / "evaluators" / "dana.json").read_text())
    assert len(on_disk) == 1


def test_put_selected_round_trips(client):
    response = client.put("/api/evaluators/selected", json={"name": "Ran"})

    assert response.status_code == 200
    assert response.get_json()["data"]["selected"] == "Ran"
    assert client.get("/api/evaluators").get_json()["data"]["selected"] == "Ran"


def test_put_selected_rejects_an_unknown_evaluator_with_400(client):
    response = client.put("/api/evaluators/selected", json={"name": "Nobody"})

    assert response.status_code == 400


def test_the_selection_is_shared_across_clients(client, tmp_path):
    client.put("/api/evaluators/selected", json={"name": "Ran"})

    # No user/session model exists, so the selection is deliberately global --
    # pinning it here so the behavior is a decision, not an accident.
    other = create_app(chart_set_store=ChartSetStore(tmp_path)).test_client()
    assert other.get("/api/evaluators").get_json()["data"]["selected"] == "Ran"


def test_the_index_page_renders_the_evaluator_options_server_side(client):
    html = client.get("/").get_data(as_text=True)

    assert '<option value="Aviv" selected>Aviv</option>' in html
    assert '<option value="Ran">Ran</option>' in html


def test_the_index_page_reflects_a_newly_added_evaluator(client):
    client.post("/api/evaluators", json={"name": "Dana"})

    assert "Dana" in client.get("/").get_data(as_text=True)


def test_the_index_page_still_renders_when_the_registry_is_corrupt(client, tmp_path):
    path = tmp_path / "data" / "evaluators.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ truncated")

    # A bad registry degrades the picker; it must not 500 the whole page.
    assert client.get("/").status_code == 200
