def test_health_runs_a_real_database_query(client):
    assert client.get("/health").json() == {"status": "ok", "db": "ok"}


def test_status_page_reports_each_component(client):
    body = client.get("/api/status").json()

    assert body["api"] == "ok"
    assert body["database"] == "ok"
    assert body["backups"]["state"] == "missing"
    assert body["status"] == "degraded"
