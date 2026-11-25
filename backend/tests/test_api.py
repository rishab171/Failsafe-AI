import os
import tempfile
import uuid

os.environ.update(
    LLM_API_KEYS="fake-a,fake-b",
    DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/test.db",
    ENABLE_FAILURE_SIMULATION="true",
    MOCK_LLM="true",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def sid():
    return "s-" + uuid.uuid4().hex[:8]


def chat(session, msg, headers=None, **extra):
    return client.post("/chat", json={"session_id": session, "message": msg, **extra}, headers=headers or {})


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


def test_chat_live_then_cache_across_sessions():
    msg = "unique question " + uuid.uuid4().hex
    a = chat(sid(), msg).json()
    assert a["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert a["metadata"]["key_id"] == "key_1" and a["metadata"]["fallback_attempts"] == 0
    b = chat(sid(), msg).json()
    assert b["metadata"]["resolution_source"] == "LLM_CACHE"
    assert b["reply"] == a["reply"]
    assert b["metadata"]["key_id"] is None and b["metadata"]["fallback_attempts"] == 0
    assert b["metadata"]["input_tokens"] == a["metadata"]["input_tokens"]
    assert b["metadata"]["latency_ms"] <= a["metadata"]["latency_ms"]


def test_different_message_not_cached():
    chat(sid(), "same prefix one " + uuid.uuid4().hex)
    r = chat(sid(), "totally different " + uuid.uuid4().hex).json()
    assert r["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_multi_turn_history_and_isolation():
    s1, s2 = sid(), sid()
    chat(s1, "first " + uuid.uuid4().hex)
    second = chat(s1, "second " + uuid.uuid4().hex).json()
    chat(s2, "other " + uuid.uuid4().hex)
    h = client.get(f"/sessions/{s1}/messages").json()
    assert [m["role"] for m in h["messages"]] == ["user", "assistant", "user", "assistant"]
    assert h["messages"][1]["metadata"]["resolution_source"] in ("LIVE_INFERENCE", "LLM_CACHE")
    assert len(client.get(f"/sessions/{s2}/messages").json()["messages"]) == 2
    assert second["metadata"]["input_tokens"] > 0


def test_unknown_session_404():
    r = client.get("/sessions/nope-" + uuid.uuid4().hex + "/messages")
    assert r.status_code == 404 and r.json() == {"detail": "session not found"}


def test_validation_422():
    for body in ({"session_id": "x", "message": ""}, {"session_id": "x", "message": "   "},
                 {"session_id": "", "message": "hi"}, {"message": "hi"}, {"session_id": "x"},
                 {"session_id": "x", "message": "a" * 4001}):
        r = client.post("/chat", json=body)
        assert r.status_code == 422 and "detail" in r.json()
    r = client.post("/chat", content="{bad json", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_failover_key1_429_and_500():
    for h in ("key_1=429", "key_1=500"):
        r = chat(sid(), "failover " + uuid.uuid4().hex, {"X-Simulate-Failure": h})
        assert r.status_code == 200
        m = r.json()["metadata"]
        assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1


def test_all_keys_fail_503_not_persisted():
    s = sid()
    for h in ("*=429", "key_1=429,key_2=503"):
        r = chat(s, "doomed " + uuid.uuid4().hex, {"X-Simulate-Failure": h})
        assert r.status_code == 503 and r.json() == {"detail": "all providers unavailable"}
    assert client.get(f"/sessions/{s}/messages").status_code == 404


def test_system_prompt_persists_in_session():
    s = sid()
    r = chat(s, "hello " + uuid.uuid4().hex, system_prompt="You are a pirate.")
    assert r.status_code == 200
    h = client.get(f"/sessions/{s}/messages").json()["messages"]
    assert all(m["role"] != "system" for m in h)
