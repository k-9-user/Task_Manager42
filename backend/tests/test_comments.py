"""Comment responses name their author."""

from tests.conftest import member_client as client


def test_comment_responses_include_author_username(client):
    project = client.post("/api/projects", json={"name": "Commented project"})
    assert project.status_code == 201, project.text
    task = client.post(
        f"/api/projects/{project.json()['data']['project']['id']}/tasks",
        json={"title": "Commented task"},
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["data"]["task"]["id"]
    username = client.current_user.username

    created = client.post(f"/api/tasks/{task_id}/comments", json={"content": "First"})
    assert created.status_code == 201, created.text
    assert created.json()["data"]["comment"]["author_username"] == username

    listed = client.get(f"/api/tasks/{task_id}/comments")
    assert listed.status_code == 200, listed.text
    assert [c["author_username"] for c in listed.json()["data"]["comments"]] == [username]
