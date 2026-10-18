
# Helpers used by our tests

def register_user(client, username="Harry", password="password123"):
    return client.post(
        "/api/register",
        json={"username": username, "password": password}
    )


def login_user(client, username="Harry", password="password123"):
    response = client.post(
        "/api/login",
        json={"username": username, "password": password}
    )

    assert response.status_code == 200

    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_task(client, headers, title="Study Python", **fields):
    data = {"title": title, **fields}

    return client.post(
        "/api/tasks",
        headers=headers,
        json=data
    )


# 1. Registration

def test_registration(client):
    response = register_user(client)

    assert response.status_code == 201
    assert response.get_json()["username"] == "Harry"
    assert "password" not in response.get_json()
    assert "password_hash" not in response.get_json()


def test_duplicate_username(client):
    register_user(client)

    response = register_user(client)

    assert response.status_code == 409


# 2. Login

def test_successful_login(client):
    register_user(client)

    response = client.post(
        "/api/login",
        json={"username": "Harry", "password": "password123"}
    )

    assert response.status_code == 200
    assert "access_token" in response.get_json()


def test_incorrect_password(client):
    register_user(client)

    response = client.post(
        "/api/login",
        json={"username": "Harry", "password": "wrongpassword"}
    )

    assert response.status_code == 401


def test_nonexistent_user(client):
    response = client.post(
        "/api/login",
        json={"username": "Nobody", "password": "password123"}
    )

    assert response.status_code == 401


# 3. JWT authentication

def test_tasks_require_login(client):
    response = client.get("/api/tasks")

    assert response.status_code == 401


def test_create_requires_login(client):
    response = client.post(
        "/api/tasks",
        json={"title": "Unauthorized task"}
    )

    assert response.status_code == 401


# 4. Task creation and retrieval

def test_create_task(client):
    register_user(client)
    headers = login_user(client)

    response = create_task(client, headers)

    assert response.status_code == 201

    task = response.get_json()

    assert task["title"] == "Study Python"
    assert task["completed"] is False
    assert task["user_id"] == 1


def test_get_tasks(client):
    register_user(client)
    headers = login_user(client)

    create_task(client, headers, "First task")
    create_task(client, headers, "Second task")

    response = client.get("/api/tasks", headers=headers)

    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_get_task_by_id(client):
    register_user(client)
    headers = login_user(client)

    created = create_task(client, headers)
    task_id = created.get_json()["id"]

    response = client.get(
        f"/api/tasks/{task_id}",
        headers=headers
    )

    assert response.status_code == 200
    assert response.get_json()["id"] == task_id


# 5. Filtering

def test_category_filter(client):
    register_user(client)
    headers = login_user(client)

    create_task(client, headers, "Python", category="Programming")
    create_task(client, headers, "Laundry", category="Home")

    response = client.get(
        "/api/tasks?category=Programming",
        headers=headers
    )

    tasks = response.get_json()

    assert response.status_code == 200
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Python"


def test_completed_filter(client):
    register_user(client)
    headers = login_user(client)

    create_task(client, headers, "Finished", completed=True)
    create_task(client, headers, "Unfinished", completed=False)

    response = client.get(
        "/api/tasks?completed=true",
        headers=headers
    )

    tasks = response.get_json()

    assert response.status_code == 200
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Finished"


# 6. Updating and deleting

def test_update_task(client):
    register_user(client)
    headers = login_user(client)

    created = create_task(client, headers)
    task_id = created.get_json()["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={"completed": True}
    )

    assert response.status_code == 200
    assert response.get_json()["completed"] is True


def test_delete_task(client):
    register_user(client)
    headers = login_user(client)

    created = create_task(client, headers)
    task_id = created.get_json()["id"]

    response = client.delete(
        f"/api/tasks/{task_id}",
        headers=headers
    )

    assert response.status_code == 204

    check = client.get(
        f"/api/tasks/{task_id}",
        headers=headers
    )

    assert check.status_code == 404


# 7. Validation

def test_missing_title(client):
    register_user(client)
    headers = login_user(client)

    response = client.post(
        "/api/tasks",
        headers=headers,
        json={"description": "Missing title"}
    )

    assert response.status_code == 400


def test_invalid_completed_value(client):
    register_user(client)
    headers = login_user(client)

    response = create_task(
        client, headers, completed="yes"
    )

    assert response.status_code == 400


def test_invalid_field(client):
    register_user(client)
    headers = login_user(client)

    response = create_task(
        client, headers, secret_field="unexpected"
    )

    assert response.status_code == 400


# 8. Ownership security

def test_users_only_see_their_own_tasks(client):
    register_user(client, "Harry")
    register_user(client, "Sera")

    harry_headers = login_user(client, "Harry")
    sera_headers = login_user(client, "Sera")

    create_task(client, harry_headers, "Harry's task")

    response = client.get(
        "/api/tasks",
        headers=sera_headers
    )

    assert response.status_code == 200
    assert response.get_json() == []


def test_cross_user_access_blocked(client):
    register_user(client, "Harry")
    register_user(client, "Sera")

    harry_headers = login_user(client, "Harry")
    sera_headers = login_user(client, "Sera")

    created = create_task(
        client, harry_headers, "Harry's private task"
    )
    task_id = created.get_json()["id"]

    # Another user attempts to read the task.
    read_response = client.get(
        f"/api/tasks/{task_id}",
        headers=sera_headers
    )

    # Another user attempts to change the task.
    update_response = client.patch(
        f"/api/tasks/{task_id}",
        headers=sera_headers,
        json={"title": "Hacked"}
    )

    # Another user attempts to delete the task.
    delete_response = client.delete(
        f"/api/tasks/{task_id}",
        headers=sera_headers
    )

    assert read_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404

    # Verify the original owner still has their task.
    original = client.get(
        f"/api/tasks/{task_id}",
        headers=harry_headers
    )

    assert original.status_code == 200
    assert original.get_json()["title"] == "Harry's private task"
