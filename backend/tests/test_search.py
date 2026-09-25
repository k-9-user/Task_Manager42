def test_search_filters_sorts_and_pages_only_visible_tasks(
    client, signup, create_project, create_task
):
    _, headers = signup()
    _, other_headers = signup()
    project = create_project(headers)
    create_task(headers, project, "alpha report")
    beta = create_task(headers, project, "beta report")
    create_task(headers, project, "gamma notes")
    client.put(f"/api/tasks/{beta['id']}", headers=headers, json={"status": "done"})
    create_task(other_headers, create_project(other_headers), "alpha report (hidden)")

    def search(**params):
        response = client.get("/api/search/tasks", headers=headers, params=params)
        return response.json()["data"]

    first_page = search(q="report", sort="title", direction="asc", limit=1, page=1)
    second_page = search(q="report", sort="title", direction="asc", limit=1, page=2)
    done = search(status="done")

    assert first_page["total"] == 2
    assert [task["title"] for task in first_page["tasks"]] == ["alpha report"]
    assert [task["title"] for task in second_page["tasks"]] == ["beta report"]
    assert [task["title"] for task in done["tasks"]] == ["beta report"]
