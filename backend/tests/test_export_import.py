def test_a_json_export_can_be_imported_back(client, signup, create_project, create_task):
    _, headers = signup()
    project = create_project(headers)
    create_task(headers, project, "First")
    create_task(headers, project, "Second")

    exported = client.get("/api/export", headers=headers, params={"format": "json"})
    imported = client.post(
        "/api/import",
        headers=headers,
        files={"file": ("export.json", exported.content, "application/json")},
    )

    assert imported.json()["data"]["imported_count"] == 2
    tasks = client.get(f"/api/projects/{project['id']}", headers=headers).json()["data"]["tasks"]
    assert sorted(task["title"] for task in tasks) == ["First", "First", "Second", "Second"]


def test_csv_export_neutralizes_spreadsheet_formulas(client, signup, create_project, create_task):
    _, headers = signup()
    create_task(headers, create_project(headers), "=SUM(A1:A9)")

    exported = client.get("/api/export", headers=headers, params={"format": "csv"})

    assert exported.status_code == 200
    assert "'=SUM(A1:A9)" in exported.text


def test_import_rejects_a_file_that_is_not_json_or_csv(client, signup):
    _, headers = signup()

    response = client.post(
        "/api/import", headers=headers, files={"file": ("tasks.exe", b"MZ", "application/octet-stream")}
    )

    assert response.status_code == 415
