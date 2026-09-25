PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_members_upload_download_and_delete_files(
    client, signup, create_project, create_task
):
    _, headers = signup()
    _, outsider_headers = signup()
    task = create_task(headers, create_project(headers))

    uploaded = client.post(
        f"/api/tasks/{task['id']}/attachments",
        headers=headers,
        files={"file": ("diagram.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    url = f"/api/attachments/{uploaded.json()['data']['attachment']['id']}"

    download = client.get(url, headers=headers)
    assert download.status_code == 200
    assert download.content == PNG
    assert client.get(url, headers=outsider_headers).status_code == 404
    assert client.delete(url, headers=headers).status_code == 200
    assert client.get(url, headers=headers).status_code == 404


def test_uploads_are_checked_for_type_and_size(client, signup, create_project, create_task):
    _, headers = signup()
    task = create_task(headers, create_project(headers))
    url = f"/api/tasks/{task['id']}/attachments"

    html_file = client.post(url, headers=headers, files={"file": ("page.html", b"<html>", "text/html")})
    too_big = client.post(
        url, headers=headers, files={"file": ("big.txt", b"x" * (1024 * 1024 + 1), "text/plain")}
    )

    assert html_file.status_code == 415
    assert too_big.status_code == 413
