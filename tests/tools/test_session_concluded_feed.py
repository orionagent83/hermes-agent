"""Contract tests for the authenticated concluded-session feed."""
import ast
import json
from pathlib import Path
import pytest
from hermes_state import SessionDB
from tools.session_search_tool import SESSION_SEARCH_SCHEMA, session_search

@pytest.fixture
def db(tmp_path):
    value = SessionDB(tmp_path / "state.db")
    yield value
    value.close()

def _session(db, sid, *, ended_at=None, reason="done", source="cli", parent=None, model_config=None):
    db.create_session(sid, source=source, parent_session_id=parent, model_config=model_config)
    mid = db.append_message(sid, role="user", content=f"message {sid}")
    if ended_at is not None:
        db._conn.execute("UPDATE sessions SET ended_at = ?, end_reason = ? WHERE id = ?", (ended_at, reason, sid))
        db._conn.commit()
    return mid

def test_concluded_feed_orders_by_compound_cursor_and_authenticates_closure(db):
    first_mid = _session(db, "a", ended_at=10.0)
    second_mid = _session(db, "b", ended_at=10.0)
    _session(db, "active")
    first = json.loads(session_search(db=db, concluded_only=True, limit=1))
    assert [row["session_id"] for row in first["results"]] == ["a"]
    assert first["results"][0]["last_message_id"] == first_mid
    assert first["results"][0]["end_reason"] == "done"
    assert first["has_more"] is True
    cursor = first["next_cursor"]
    second = json.loads(session_search(db=db, concluded_only=True, after_ended_at=cursor["ended_at"], after_session_id=cursor["session_id"]))
    assert [row["session_id"] for row in second["results"]] == ["b"]
    assert second["results"][0]["last_message_id"] == second_mid

def test_concluded_feed_excludes_non_conclusions_and_projects_compression_tip(db):
    _session(db, "root", ended_at=5.0, reason="compression")
    _session(db, "tip", ended_at=12.0, parent="root")
    _session(db, "shutdown", ended_at=13.0, reason="agent_close")
    _session(db, "worker", ended_at=14.0, source="kanban")
    _session(db, "delegate", ended_at=15.0, model_config={"_delegate_from": "parent"})
    result = json.loads(session_search(db=db, concluded_only=True))
    assert [row["session_id"] for row in result["results"]] == ["tip"]
    assert result["results"][0]["lineage_root"] == "root"

def test_reopen_reclose_is_cursor_monotone_and_stable_empty(db):
    _session(db, "reopen", ended_at=20.0)
    cursor = json.loads(session_search(db=db, concluded_only=True))["next_cursor"]
    db._conn.execute("UPDATE sessions SET ended_at = NULL, end_reason = NULL WHERE id = 'reopen'")
    db._conn.commit()
    empty = json.loads(session_search(db=db, concluded_only=True, after_ended_at=cursor["ended_at"], after_session_id=cursor["session_id"]))
    assert empty["results"] == []
    assert empty["next_cursor"] == cursor
    db._conn.execute("UPDATE sessions SET ended_at = 21.0, end_reason = 'done' WHERE id = 'reopen'")
    db._conn.commit()
    reclosed = json.loads(session_search(db=db, concluded_only=True, after_ended_at=cursor["ended_at"], after_session_id=cursor["session_id"]))
    assert [row["session_id"] for row in reclosed["results"]] == ["reopen"]
    assert reclosed["next_cursor"]["ended_at"] == 21.0

@pytest.mark.parametrize("kwargs", [
    {"after_ended_at": 1.0}, {"after_session_id": "a"},
    {"after_ended_at": -1.0, "after_session_id": "a"},
    {"after_ended_at": float("nan"), "after_session_id": "a"},
    {"after_ended_at": True, "after_session_id": "a"},
    {"after_ended_at": 1.0, "after_session_id": 2},
])
def test_malformed_cursor_fails_closed(db, kwargs):
    assert json.loads(session_search(db=db, concluded_only=True, **kwargs))["success"] is False

def test_regressive_backend_cursor_fails_closed():
    class RegressiveDB:
        def list_concluded_session_tips_after(self, *_args):
            return [{"session_id": "a", "ended_at": 1.0}]
    result = json.loads(session_search(db=RegressiveDB(), concluded_only=True, after_ended_at=2.0, after_session_id="z"))
    assert result["success"] is False

def test_read_metadata_authenticates_closure(db):
    last_mid = _session(db, "closed", ended_at=30.0, reason="user_exit")
    meta = json.loads(session_search(db=db, session_id="closed"))["session_meta"]
    assert meta["status"] == "concluded"
    assert meta["ended_at"] == 30.0
    assert meta["end_reason"] == "user_exit"
    assert meta["last_message_id"] == last_mid

def test_schema_and_both_executor_paths_forward_concluded_cursor():
    properties = SESSION_SEARCH_SCHEMA["parameters"]["properties"]
    assert {"concluded_only", "after_ended_at", "after_session_id"} <= properties.keys()
    root = Path(__file__).resolve().parents[2]
    required = {"profile", "concluded_only", "after_ended_at", "after_session_id"}
    for relative in ("agent/tool_executor.py", "agent/agent_runtime_helpers.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and any(kw.arg == "current_session_id" for kw in node.keywords)]
        assert any(required <= {kw.arg for kw in call.keywords} for call in calls), relative
