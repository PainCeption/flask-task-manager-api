# Task Manager API contract

This document describes the HTTP interface implemented in [backend/app.py](./backend/app.py), with task persistence in [backend/database.py](./backend/database.py). The [README](./README.md) covers local setup.

## Conventions

- Paths are relative to the API server. The local development server normally uses `http://127.0.0.1:5000`.
- Registration, login, task creation, and task updates expect a JSON **object**. Send `Content-Type: application/json` with these requests. A JSON array or scalar is rejected.
- All `/api/tasks` operations require `Authorization: Bearer <access_token>`. Registration and login do not require a token.
- Task IDs in paths are SQLite-generated integers. Clients do not supply an ID or owner when creating a task.
- Successful resource responses are JSON. A successful deletion has no response body.

## Data shapes

An account request uses:

```json
{"username": "Harry", "password": "password123"}
```

Both values must be strings containing at least one non-whitespace character. Registration stores a password hash, and neither the password nor its hash is returned. The implementation does not set a password-length or strength rule. Extra account request fields are ignored.

A task returned by the API has this shape (IDs are examples):

```json
{
  "id": 1,
  "title": "Study Python",
  "description": "Practice REST APIs",
  "category": "Programming",
  "completed": false,
  "user_id": 1
}
```

`title` must be a string containing at least one non-whitespace character. `description` and `category` must be strings and may be empty. `completed` must be a JSON boolean (`true` or `false`), not a string or number. Creation defaults omitted `description` and `category` to `""` and omitted `completed` to `false`. The only accepted task input keys are `title`, `description`, `category`, and `completed`; `id` and `user_id` are response fields, not writable fields. Titles are checked for blank content but are stored without trimming.

## Endpoints

### `POST /api/register`

Creates an account from `username` and `password`. Returns `201 Created` with:

```json
{"id": 1, "username": "Harry"}
```

A username already in the database returns `409 Conflict`. Missing, blank, or incorrectly typed required values return `400 Bad Request` after JSON parsing.

### `POST /api/login`

Checks the same two account fields against a registered user. Returns `200 OK` with:

```json
{"message": "Login successful", "access_token": "<JWT>"}
```

An unknown username or incorrect password returns `401 Unauthorized`. Use the returned token in the `Authorization` header for task requests.

### `GET /api/tasks`

Returns `200 OK` with an array of the authenticated user's tasks; an empty collection is `[]`. Optional query parameters are:

| Parameter | Accepted form | Effect |
| --- | --- | --- |
| `category` | Repeatable string value | Selects tasks matching **any** supplied category |
| `completed` | Exactly `true` or `false`, in lowercase | Selects tasks with that completion status |

For example, `GET /api/tasks?category=Work&category=Home&completed=false` selects the caller's incomplete tasks in either category. Omit `completed` to include both completion states. An unsupported completion value returns `400 Bad Request`. Category matching uses the stored string value; the API does not normalize case or whitespace. No ordering or pagination is defined.

### `POST /api/tasks`

Creates a task owned by the authenticated user. A minimal body is:

```json
{"title": "Study Python"}
```

Returns `201 Created` with the complete task, including its generated `id`, defaults, and `user_id`. Missing or invalid `title`, unsupported task keys, and invalid optional field types return `400 Bad Request`.

### `GET /api/tasks/<int:task_id>`

Returns `200 OK` with one task owned by the authenticated user. An absent task or another user's task returns `404 Not Found`.

### `PATCH /api/tasks/<int:task_id>`

Updates only the fields supplied in a nonempty JSON object. For example:

```json
{"completed": true}
```

Omitted fields keep their current values. The accepted fields and type rules are the same as for creation, except `title` is optional. Returns `200 OK` with the updated complete task. An empty object, invalid value, or unsupported key returns `400 Bad Request`; an absent or unowned task returns `404 Not Found` after valid input is processed.

### `DELETE /api/tasks/<int:task_id>`

Deletes one owned task and returns `204 No Content` with an empty body. An absent or unowned task returns `404 Not Found`.

## Authentication, ownership, and errors

The API takes the user ID from the JWT, not from task request data. Collection queries filter by that ID, and individual read, update, and delete queries match both task ID and user ID. This is why a task belonging to another account appears as `404 Not Found` to the caller.

The application uses Flask's `abort()` for its validation, credential, conflict, and not-found errors. It has **no custom JSON error handler**, so clients should not assume those error bodies are JSON; Flask normally returns an HTML error page for them. Authentication errors generated by Flask-JWT-Extended have that extension's JSON error format. Flask's JSON parser can also reject malformed JSON or a request with the wrong content type before the route's own validation runs. Clients should branch on HTTP status and handle the response content type accordingly.
