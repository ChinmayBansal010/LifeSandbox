from fastapi.testclient import TestClient

from app.main import app


def test_admin_traces_recorded_on_chat():
    with TestClient(app) as client:
        # Clear existing traces
        del_resp = client.delete("/api/v1/admin/traces")
        assert del_resp.status_code == 204

        # Send a chat message
        resp = client.post("/api/v1/chat", json={"message": "Help me choose a laptop"})
        assert resp.status_code == 200
        body = resp.json()
        assert "trace_id" in body
        trace_id = body["trace_id"]
        assert "tools_accessed" in body

        # Query admin traces
        traces_resp = client.get("/api/v1/admin/traces")
        assert traces_resp.status_code == 200
        traces = traces_resp.json()["items"]
        assert len(traces) >= 1

        target_trace = next((t for t in traces if t["id"] == trace_id), None)
        assert target_trace is not None
        assert target_trace["status"] == "completed"
        assert target_trace["started_at"] is not None
        assert target_trace["completed_at"] is not None
        assert target_trace["total_duration_ms"] >= 0

        # Check tool accesses inside target trace
        tools = target_trace["tools_accessed"]
        tool_names = [t["tool_name"] for t in tools]
        assert "intent_classifier" in tool_names
        assert "llm_completion" in tool_names

        # Verify timestamps on tool events
        for tool in tools:
            assert "started_at" in tool
            assert "completed_at" in tool
            assert "duration_ms" in tool
            assert tool["status"] == "success"

        # Query single trace by ID
        single_resp = client.get(f"/api/v1/admin/traces/{trace_id}")
        assert single_resp.status_code == 200
        assert single_resp.json()["id"] == trace_id

        # Query stats
        stats_resp = client.get("/api/v1/admin/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_prompts"] >= 1
        assert stats["total_tool_calls"] >= 2
        assert "intent_classifier" in stats["tool_breakdown"]


def test_admin_traces_filter_and_search():
    with TestClient(app) as client:
        client.delete("/api/v1/admin/traces")
        client.post("/api/v1/chat", json={"message": "UniqueSearchQueryXYZ"})

        # Search matching
        search_resp = client.get("/api/v1/admin/traces?search=UniqueSearchQueryXYZ")
        assert search_resp.status_code == 200
        assert len(search_resp.json()["items"]) == 1

        # Search non-matching
        no_match = client.get("/api/v1/admin/traces?search=NonExistentQuery123")
        assert no_match.status_code == 200
        assert len(no_match.json()["items"]) == 0

        # Filter by tool
        tool_match = client.get("/api/v1/admin/traces?tool_filter=intent_classifier")
        assert tool_match.status_code == 200
        assert len(tool_match.json()["items"]) >= 1
