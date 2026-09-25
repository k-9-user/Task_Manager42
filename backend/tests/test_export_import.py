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


def test_an_export_imported_by_another_account_recreates_the_project(
    client, signup, create_project, create_task
):
    _, owner_headers = signup()
    project = create_project(owner_headers)
    create_task(owner_headers, project, "Shared task")
    exported = client.get("/api/export", headers=owner_headers, params={"format": "json"})

    _, other_headers = signup()
    imported = client.post(
        "/api/import",
        headers=other_headers,
        files={"file": ("export.json", exported.content, "application/json")},
    )

    assert imported.status_code == 200, imported.text
    assert imported.json()["data"] == {"imported_count": 1, "created_projects": 1}
    projects = client.get("/api/projects", headers=other_headers).json()["data"]["projects"]
    assert [item["name"] for item in projects] == [project["name"]]
    assert projects[0]["id"] != project["id"]


def test_export_can_be_scoped_to_one_project(client, signup, create_project, create_task):
    _, headers = signup()
    kept = create_project(headers)
    create_task(headers, kept, "Kept")
    create_task(headers, create_project(headers), "Other")

    exported = client.get(
        "/api/export", headers=headers, params={"format": "json", "project_id": kept["id"]}
    ).json()

    assert [project["id"] for project in exported["projects"]] == [kept["id"]]
    assert [task["title"] for task in exported["projects"][0]["tasks"]] == ["Kept"]


def test_export_refuses_a_project_that_is_not_visible(client, signup, create_project):
    _, owner_headers = signup()
    project = create_project(owner_headers)
    _, other_headers = signup()

    response = client.get(
        "/api/export", headers=other_headers, params={"format": "json", "project_id": project["id"]}
    )

    assert response.status_code == 404
