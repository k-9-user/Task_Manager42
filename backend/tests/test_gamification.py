def test_first_project_unlocks_an_achievement_and_xp(client, signup, create_project):
    _, headers = signup()

    create_project(headers)
    progress = client.get("/api/gamification/me", headers=headers).json()["data"]

    projects = next(track for track in progress["tracks"] if track["key"] == "projects")
    assert projects["count"] == 1
    assert projects["achievements"][0]["unlocked_at"] is not None
    assert progress["progress"]["xp"] == 35
