def _add_member(client, owner_headers, project, user, role):
    response = client.post(
        f"/api/projects/{project['id']}/members",
        headers=owner_headers,
        json={"user_id": user["id"], "role": role},
    )
    assert response.status_code == 201, response.text


def test_project_roles_decide_who_can_read_and_write(client, signup, create_project):
    _, owner_headers = signup()
    viewer, viewer_headers = signup()
    _, outsider_headers = signup()
    project = create_project(owner_headers)
    _add_member(client, owner_headers, project, viewer, "viewer")

    assert client.get(f"/api/projects/{project['id']}", headers=viewer_headers).status_code == 200
    viewer_write = client.post(
        f"/api/projects/{project['id']}/tasks", headers=viewer_headers, json={"title": "No"}
    )
    assert viewer_write.status_code == 403
    assert client.get(f"/api/projects/{project['id']}", headers=outsider_headers).status_code == 404


def test_editors_update_tasks_but_only_owners_delete_them(
    client, signup, create_project, create_task
):
    _, owner_headers = signup()
    editor, editor_headers = signup()
    project = create_project(owner_headers)
    _add_member(client, owner_headers, project, editor, "editor")
    task = create_task(editor_headers, project, "Write the tests")
    task_url = f"/api/tasks/{task['id']}"

    updated = client.put(task_url, headers=editor_headers, json={"status": "done"})
    assert updated.json()["data"]["task"]["status"] == "done"
    assert client.delete(task_url, headers=editor_headers).status_code == 403
    assert client.delete(task_url, headers=owner_headers).status_code == 200
    assert client.put(task_url, headers=owner_headers, json={"status": "todo"}).status_code == 404


def test_assigning_a_task_notifies_the_assignee(client, signup, create_project, create_task):
    _, owner_headers = signup()
    member, member_headers = signup()
    project = create_project(owner_headers)
    _add_member(client, owner_headers, project, member, "editor")

    create_task(owner_headers, project, "Review", assignee_id=member["id"])
    notifications = client.get("/api/notifications", headers=member_headers).json()["data"]

    contents = [notification["content"] for notification in notifications["notifications"]]
    assert 'You were assigned to the task "Review"' in contents
