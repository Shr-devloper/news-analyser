def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
