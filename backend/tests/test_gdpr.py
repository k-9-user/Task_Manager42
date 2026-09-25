def test_export_contains_personal_data_without_secrets(client, signup, create_project):
    user, headers = signup()
    create_project(headers, "My project")

    response = client.get("/api/gdpr/export", headers=headers)

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    export = response.json()
    assert export["profile"]["email"] == user["email"]
    assert export["projects"][0]["name"] == "My project"
    assert "$argon2" not in response.text


def test_account_deletion_needs_the_exact_username(client, signup, password):
    user, headers = signup()

    def delete_account(username):
        return client.request(
            "DELETE",
            "/api/gdpr/account",
            headers=headers,
            json={"confirm": True, "confirm_username": username},
        )

    assert delete_account("someone_else").status_code == 400
    assert delete_account(user["username"]).status_code == 200
    login = client.post("/api/auth/login", json={"identifier": user["email"], "password": password})
    assert login.status_code == 401
