def _api_key_headers(client, headers):
    issued = client.post("/api/api-keys", headers=headers)
    assert issued.status_code == 201, issued.text
    return {"X-API-Key": issued.json()["data"]["api_key"]["key"]}


def test_the_five_public_endpoints_work_with_an_api_key(client, signup, create_project):
    _, headers = signup()
    project = create_project(headers)
    key = _api_key_headers(client, headers)

    created = client.post(
        "/api/v1/public/tasks", headers=key, json={"project_id": project["id"], "title": "From the API"}
    )
    task_id = created.json()["data"]["task"]["id"]
    listed = client.get("/api/v1/public/tasks", headers=key).json()["data"]["tasks"]
    updated = client.put(f"/api/v1/public/tasks/{task_id}", headers=key, json={"status": "done"})
    projects = client.get("/api/v1/public/projects", headers=key).json()["data"]["projects"]
    deleted = client.delete(f"/api/v1/public/tasks/{task_id}", headers=key)

    assert [task["id"] for task in listed] == [task_id]
    assert updated.json()["data"]["task"]["status"] == "done"
    assert [item["id"] for item in projects] == [project["id"]]
    assert deleted.status_code == 200


def test_missing_invalid_or_revoked_keys_are_refused(client, signup):
    _, headers = signup()
    key = _api_key_headers(client, headers)
    key_id = client.get("/api/api-keys", headers=headers).json()["data"]["api_keys"][0]["id"]
    client.delete(f"/api/api-keys/{key_id}", headers=headers)

    assert client.get("/api/v1/public/projects").status_code == 401
    assert client.get("/api/v1/public/projects", headers={"X-API-Key": "not-a-key"}).status_code == 401
    assert client.get("/api/v1/public/projects", headers=key).status_code == 401


def test_each_key_is_limited_to_60_requests_per_minute(client, signup):
    _, headers = signup()
    key = _api_key_headers(client, headers)

    statuses = [client.get("/api/v1/public/projects", headers=key).status_code for _ in range(61)]

    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
